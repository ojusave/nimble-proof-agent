"""HTTP transport and SSE. Workflow and provider choices are injected here."""
import json
import asyncio
import threading
import time
from pathlib import Path
from uuid import UUID
from fastapi import FastAPI,UploadFile,File,HTTPException,Request,Response
from fastapi.responses import FileResponse,StreamingResponse
from pydantic import BaseModel,Field,ConfigDict
from adapters.storage.sqlite import Repository
from adapters.resume.parser import parse_resume,MAX_FILE
from adapters.nimble.client import NimbleAdapter,ProviderError
from adapters.demo import DemoAdapter,SAMPLE_RESUME
from core.models import SearchRequest,event
from core.settings import Settings,ROOT
from workflows.job_matcher import JobWorkflow
from runners.langgraph import LangGraphRunner
from core.services import Services
from composition import build_services


class SearchBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    resume_id:str
    query:str=Field(default='',max_length=1500)
    count:int=Field(default=5,ge=1,le=20,strict=True)
    demo:bool=False


def create_app(settings=None,repository=None,provider=None):
    settings=settings or Settings.load()
    repository=repository or Repository(settings.data_dir)
    app=FastAPI(title='Proof Job Matcher',docs_url=None,redoc_url=None,openapi_url=None)
    app.state.repository=repository
    slot=threading.BoundedSemaphore(1)

    @app.middleware('http')
    async def local_only(request:Request,call_next):
        host=request.url.hostname
        origin=request.headers.get('origin')
        if host not in ('localhost','127.0.0.1','testserver') or (origin and origin!=str(request.base_url).rstrip('/')):
            return Response('Local origin required.',status_code=403)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Cache-Control']='no-store'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.get('/api/config')
    def config(): return {'live_ready':bool(settings.api_key),'framework':'LangGraph','default_count':5,'max_rounds':settings.max_rounds}

    @app.get('/api/resumes')
    def resumes(): return repository.list_resumes()

    @app.post('/api/resumes',status_code=201)
    async def upload(file:UploadFile=File(...)):
        content=await file.read(MAX_FILE+1)
        await file.close()
        try:
            text=parse_resume(file.filename or '',content)
            return repository.save_resume(file.filename or 'resume.txt',content,text)
        except ValueError as error: raise HTTPException(400,str(error))

    @app.delete('/api/resumes/{rid}')
    def remove_resume(rid:str):
        try:
            if not repository.delete_resume(rid): raise HTTPException(404,'Résumé not found.')
        except ValueError as error: raise HTTPException(409,str(error))
        return {'removed':True}

    @app.get('/api/searches')
    def searches(): return repository.recent()

    @app.get('/api/searches/{rid}')
    def run(rid:str):
        value=repository.run(rid)
        if value is None: raise HTTPException(404,'Search not found.')
        return value

    def execute(rid,request,resume_text):
        emit=lambda item:repository.emit(rid,item)
        try:
            services=Services(provider,provider,provider,LangGraphRunner()) if provider and not request.demo else build_services(settings,request.demo)
            workflow=JobWorkflow(services.search,services.extract,services.reasoner,settings,emit)
            result=services.runner.run(workflow,{'resume_text':resume_text,'query':request.query,'count':request.count,
                                                  'max_rounds':request.max_rounds,'demo':request.demo})
            repository.finish(rid,result=result)
        except Exception as error:
            message=str(error) if isinstance(error,(ValueError,ProviderError)) else 'Search failed unexpectedly. Check the server log.'
            emit(event('run_failed','finish',message))
            repository.finish(rid,error=message)
            if not isinstance(error,(ValueError,ProviderError)):
                import traceback;traceback.print_exc()
        finally: slot.release()

    @app.post('/api/searches',status_code=202)
    def start(body:SearchBody):
        request=SearchRequest(body.resume_id,body.query,body.count,settings.max_rounds,body.demo)
        request.validate()
        resume=repository.resume(body.resume_id)
        if resume is None: raise HTTPException(400,'Upload or select a résumé first.')
        if not body.demo and not settings.api_key and provider is None: raise HTTPException(400,'Add NIMBLE_API_KEY to .env first.')
        if not slot.acquire(blocking=False): raise HTTPException(409,'A search is already running.')
        try:
            rid=repository.create(request)
            repository.emit(rid,event('run_started','start','Search started',requested=body.count,demo=body.demo,framework='LangGraph'))
            threading.Thread(target=execute,args=(rid,request,resume['text']),daemon=True).start()
        except Exception:
            slot.release();raise
        return {'id':rid}

    @app.post('/api/demo',status_code=202)
    def demo():
        resume=repository.save_resume('Demo resume.txt',SAMPLE_RESUME.encode(),SAMPLE_RESUME)
        return start(SearchBody(resume_id=resume['id'],query='Developer advocate, remote, US',count=5,demo=True))

    @app.get('/api/searches/{rid}/events')
    def stream(rid:str,request:Request):
        if repository.run(rid) is None: raise HTTPException(404,'Search not found.')
        try: after=max(0,int(request.headers.get('last-event-id','0')))
        except ValueError: after=0
        async def packets():
            cursor=after;last_heartbeat=time.monotonic()
            while True:
                if await request.is_disconnected(): return
                current=repository.run(rid)
                rows=repository.events(rid,cursor)
                for item in rows:
                    cursor=item['seq']
                    yield 'id: %s\nevent: activity\ndata: %s\n\n'%(cursor,json.dumps(item))
                if current['status']!='running':
                    yield 'event: done\ndata: %s\n\n'%json.dumps(current)
                    return
                if time.monotonic()-last_heartbeat>10:
                    yield ': heartbeat\n\n';last_heartbeat=time.monotonic()
                await asyncio.sleep(.25)
        return StreamingResponse(packets(),media_type='text/event-stream',headers={'X-Accel-Buffering':'no'})

    @app.get('/api/searches/{rid}/export')
    def export(rid:str):
        value=repository.run(rid)
        if value is None or not value['result']: raise HTTPException(404,'No completed shortlist.')
        result=value['result'];lines=['# Job shortlist','',f"{len(result['jobs'])} of {result['requested']} requested matches.",'']
        for job in result['jobs']:
            lines.extend([f"## {job['rank']}. {job['title']} — {job['company']}",job['url'],job['summary'],''])
            lines.extend('- '+strength['reason'] for strength in job['strengths'])
            lines.extend('- Gap: '+gap for gap in job['gaps']);lines.append('')
        if result['next_question']: lines.append(result['next_question'])
        return Response('\n'.join(lines),media_type='text/markdown',headers={'Content-Disposition':'attachment; filename="job-shortlist.md"'})

    @app.get('/')
    def index(): return FileResponse(ROOT/'web/index.html')

    @app.get('/app.js')
    def javascript(): return FileResponse(ROOT/'web/app.js',media_type='text/javascript')

    @app.get('/style.css')
    def css(): return FileResponse(ROOT/'web/style.css',media_type='text/css')

    @app.get('/sample-resume.txt')
    def sample(): return Response(SAMPLE_RESUME,media_type='text/plain')

    return app
