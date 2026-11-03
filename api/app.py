"""HTTP transport and SSE. Workflow and provider choices are injected here."""
import json
import asyncio
import threading
import time
from fastapi import FastAPI,UploadFile,File,HTTPException,Request,Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel,Field,ConfigDict
from adapters.storage.sqlite import Repository
from adapters.resume.parser import parse_resume,MAX_FILE
from adapters.nimble.client import ProviderError
from adapters.demo import SAMPLE_RESUME
from core.exporting import shortlist_markdown
from core.models import SearchRequest,event
from core.settings import Settings
from workflows.job_matcher import JobWorkflow
from runners.langgraph import LangGraphRunner
from core.services import Services
from core.cancellation import CancellationToken, SearchCancelled, stopped_result
from composition import build_services
from api.agent import register_agent_routes


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
    register_agent_routes(app,repository)
    slot=threading.BoundedSemaphore(1)
    controls={}
    control_lock=threading.RLock()

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

    @app.get('/api/health')
    def health():
        # A fast database read confirms storage is available; no provider calls.
        repository.recent()
        return {'status':'ok'}

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

    def execute(rid,request,resume_text,control):
        def emit(item):
            with control_lock:
                control.check()
                repository.emit(rid,item)
        def finish_stopped():
            message='Search stopped. Results already received were kept.' if request.demo else 'Stopped locally. Requests already sent to Nimble may continue.'
            result=stopped_result(request,repository.events(rid))
            repository.emit(rid,event('run_stopped','finish',message,remote_cancellation='not_confirmed' if not request.demo else 'not_applicable'))
            repository.finish(rid,result=result,status='stopped')
        try:
            services=Services(provider,provider,provider,LangGraphRunner()) if provider and not request.demo else build_services(settings,request.demo,control)
            workflow=JobWorkflow(services.search,services.extract,services.reasoner,settings,emit,control.is_cancelled)
            result=services.runner.run(workflow,{'resume_text':resume_text,'query':request.query,'count':request.count,
                                                  'max_rounds':request.max_rounds,'demo':request.demo})
            with control_lock:
                if control.is_cancelled(): finish_stopped()
                else: repository.finish(rid,result=result)
        except SearchCancelled:
            with control_lock: finish_stopped()
        except Exception as error:
            message=str(error) if isinstance(error,(ValueError,ProviderError)) else 'Search failed unexpectedly. Check the server log.'
            with control_lock:
                if control.is_cancelled(): finish_stopped()
                else:
                    emit(event('run_failed','finish',message))
                    repository.finish(rid,error=message)
            if not isinstance(error,(ValueError,ProviderError)):
                import traceback;traceback.print_exc()
        finally:
            with control_lock: controls.pop(rid,None)
            slot.release()

    @app.post('/api/searches/{rid}/stop')
    def stop_search(rid:str):
        with control_lock:
            current=repository.run(rid)
            if current is None: raise HTTPException(404,'Search not found.')
            if current['status']!='running': return current
            control=controls.get(rid)
            if control is None: raise HTTPException(409,'This worker is unavailable. Reload the search status.')
            repository.request_stop(rid)
            repository.emit(rid,event('run_stopping','finish','Stop requested. Waiting for in-flight requests to return.'))
            control.cancel()
            return repository.run(rid)

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
            control=CancellationToken()
            with control_lock: controls[rid]=control
            repository.emit(rid,event('run_started','start','Search started',requested=body.count,demo=body.demo,framework='LangGraph'))
            threading.Thread(target=execute,args=(rid,request,resume['text'],control),daemon=True).start()
        except Exception:
            if 'rid' in locals():
                with control_lock: controls.pop(rid,None)
                repository.finish(rid,error='The search worker could not start.')
            slot.release();raise
        return {'id':rid}

    @app.post('/api/demo',status_code=202)
    def demo():
        # Reusing the sample should not fill the résumé picker with duplicate files.
        resume=next((row for row in repository.list_resumes()
                     if repository.resume(row['id'])['text']==SAMPLE_RESUME),None)
        if resume is None:
            resume=repository.save_resume('Sample résumé.txt',SAMPLE_RESUME.encode(),SAMPLE_RESUME)
        return start(SearchBody(resume_id=resume['id'],query='Developer advocate, remote, US',count=5,demo=True))

    @app.get('/api/searches/{rid}/events')
    def stream(rid:str,request:Request):
        if repository.run(rid) is None: raise HTTPException(404,'Search not found.')
        try: after=max(0,int(request.headers.get('last-event-id','0')))
        except ValueError: after=0
        async def packets():
            cursor=after;last_heartbeat=time.monotonic();last_status=None
            while True:
                if await request.is_disconnected(): return
                current=repository.run(rid)
                if current['status']!=last_status:
                    yield 'event: state\ndata: %s\n\n'%json.dumps(current)
                    last_status=current['status']
                rows=repository.events(rid,cursor)
                for item in rows:
                    cursor=item['seq']
                    yield 'id: %s\nevent: activity\ndata: %s\n\n'%(cursor,json.dumps(item))
                if current['status'] not in ('running','stopping'):
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
        return Response(shortlist_markdown(value['result']),media_type='text/markdown',headers={'Content-Disposition':'attachment; filename="job-shortlist.md"'})

    @app.get('/')
    def index(): return {'service':'Proof API','ui':'http://127.0.0.1:8765','start':'npm run dev'}

    @app.get('/sample-resume.txt')
    def sample(): return Response(SAMPLE_RESUME,media_type='text/plain')

    return app
