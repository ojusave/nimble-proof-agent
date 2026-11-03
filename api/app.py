"""HTTP transport and SSE. Workflow and provider choices are injected here."""
import json
import asyncio
import threading
import time
from fastapi import FastAPI,UploadFile,File,HTTPException,Request,Response
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel,Field,ConfigDict
from adapters.storage.sqlite import Repository
from adapters.resume.parser import MAX_FILE
from core.errors import ProviderError
from adapters.demo import SAMPLE_RESUME
from core.exporting import shortlist_markdown
from core.models import SearchRequest,event
from core.settings import Settings
from core.urls import public_url
from core.text import professional_text
from workflows.job_matcher import JobWorkflow
from runners.langgraph import LangGraphRunner
from core.services import Services
from core.cancellation import CancellationToken, SearchCancelled, stopped_result
from composition import build_services,ingest_resume
from api.agent import register_agent_routes


class SearchBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    resume_id:str
    query:str=Field(default='',max_length=1500)
    count:int=Field(default=5,ge=1,le=20,strict=True)
    demo:bool=False
    public_urls:list[str]=Field(default_factory=list,max_length=20)


class ResumeDraftBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    job_id:str=Field(min_length=1,max_length=128)
    edits:list[int]=Field(min_length=1,max_length=100)

class TailorBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    job_id:str=Field(min_length=1,max_length=128)


def create_app(settings=None,repository=None,provider=None,resume_parser=None):
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
    def config(): return {'live_ready':bool(settings.api_key),'framework':'LangGraph','default_count':5,'max_rounds':settings.max_rounds,
                          'pdf_parser':'llamaparse' if settings.llama_api_key else 'local'}

    @app.get('/api/health')
    def health():
        # A fast database read confirms storage is available; no provider calls.
        repository.recent()
        return {'status':'ok'}

    @app.get('/api/resumes')
    def resumes(): return repository.list_resumes()

    @app.post('/api/resumes',status_code=201)
    async def upload(request:Request,file:UploadFile=File(...)):
        content=await file.read(MAX_FILE+1)
        await file.close()
        def parse_and_save(emit=None):
            parsed=ingest_resume(settings,file.filename or '',content,resume_parser,emit)
            return repository.save_resume(file.filename or 'resume.txt',content,parsed['text'],
                                          {key:value for key,value in parsed.items() if key!='text'})
        if 'text/event-stream' in request.headers.get('accept',''):
            async def parsing_events():
                queue=asyncio.Queue();loop=asyncio.get_running_loop()
                def publish(kind,value): loop.call_soon_threadsafe(queue.put_nowait,(kind,value))
                def work():
                    try: publish('resume',parse_and_save(lambda item:publish('activity',item)))
                    except Exception as error: publish('error',{'detail':str(error) if isinstance(error,ValueError) else 'PDF parsing failed unexpectedly.'})
                threading.Thread(target=work,daemon=True).start()
                while True:
                    try: kind,value=await asyncio.wait_for(queue.get(),10)
                    except asyncio.TimeoutError:
                        yield ': parsing\n\n';continue
                    yield 'event: '+kind+'\ndata: '+json.dumps(value)+'\n\n'
                    if kind in ('resume','error'): return
            return StreamingResponse(parsing_events(),media_type='text/event-stream',headers={'X-Accel-Buffering':'no'})
        try:
            return await run_in_threadpool(parse_and_save)
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

    def execute(rid,request,resume_text,control,public_urls,resume_metadata):
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
                                                  'max_rounds':request.max_rounds,'demo':request.demo,'public_urls':public_urls,'resume_metadata':resume_metadata})
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
        try: public_urls=list(dict.fromkeys(public_url(url) for url in body.public_urls))
        except ValueError as error: raise HTTPException(400,str(error))
        if body.demo and public_urls: raise HTTPException(400,'Public-work research is available only for live searches.')
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
            repository.emit(rid,event('run_started','start','Search started',requested=body.count,demo=body.demo,framework='LangGraph',public_urls=public_urls))
            threading.Thread(target=execute,args=(rid,request,resume['text'],control,public_urls,json.loads(resume.get('metadata') or '{}')),daemon=True).start()
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

    @app.post('/api/searches/{rid}/resume-draft')
    def resume_draft(rid:str,body:ResumeDraftBody):
        run=repository.run(rid)
        if run is None: raise HTTPException(404,'Search not found.')
        resume=repository.resume(run['resume_id'])
        if resume is None: raise HTTPException(410,'The original résumé was removed.')
        proposals=(run.get('result') or {}).get('resume_proposals',{})
        for item in repository.events(rid):
            if item['type']=='resume_proposals_ready': proposals[item['data']['candidate_id']]=item['data']['proposal']
        proposal=proposals.get(body.job_id)
        if not proposal: raise HTTPException(404,'No résumé suggestions are available for this role.')
        indexes=list(dict.fromkeys(body.edits));edits=proposal.get('edits',[])
        if any(index<0 or index>=len(edits) for index in indexes): raise HTTPException(400,'Select valid résumé suggestions.')
        selected=[edits[index] for index in indexes]
        markdown=resume['text']+'\n\n## Selected professional work\n\n'+'\n'.join('- '+edit['wording'] for edit in selected)
        return {'markdown':markdown+'\n'}

    @app.post('/api/searches/{rid}/tailor',status_code=202)
    def tailor(rid:str,body:TailorBody):
        current=repository.run(rid)
        if current is None: raise HTTPException(404,'Search not found.')
        original=current.get('result') or {}
        proposal=original.get('resume_proposals',{}).get(body.job_id)
        if proposal and not proposal.get('error'): return current
        if current['status'] in ('running','stopping'): raise HTTPException(409,'Wait for the current research to finish.')
        if not original.get('public_research',{}).get('facts'): raise HTTPException(400,'Include your public professional links in a search first.')
        job=next((job for job in original.get('jobs',[])+original.get('unknowns',[]) if job['id']==body.job_id),None)
        if job is None: raise HTTPException(404,'This role was not in the shortlist.')
        resume=repository.resume(current['resume_id'])
        if resume is None: raise HTTPException(410,'The original résumé was removed.')
        if not slot.acquire(blocking=False): raise HTTPException(409,'Another research task is running.')
        control=CancellationToken()
        with control_lock: controls[rid]=control
        def execute_tailoring():
            def emit(item):
                with control_lock:
                    control.check();repository.emit(rid,item)
            try:
                services=build_services(settings,False,control)
                workflow=JobWorkflow(services.search,services.extract,services.reasoner,settings,emit,control.is_cancelled)
                proposals=services.runner.run_tailoring(workflow.tailoring_worker(),{
                    'profile':professional_text(resume['text']),'query':current['query'],
                    'public_research':original['public_research'],'result':{'jobs':[job],'unknowns':[]}})
                with control_lock:
                    control.check()
                    result={**original,'resume_proposals':{**original.get('resume_proposals',{}),**proposals}}
                    repository.emit(rid,event('tailoring_completed','tailor','Role-specific research finished',candidate_id=job['id']))
                    repository.finish(rid,result=result)
            except SearchCancelled:
                with control_lock:
                    repository.emit(rid,event('run_stopped','tailor','Résumé research stopped. Existing job results were kept.'))
                    repository.finish(rid,result=original,status='stopped')
            except Exception:
                with control_lock:
                    repository.emit(rid,event('tailoring_failed','tailor','Résumé research could not finish. Existing results were kept.',candidate_id=job['id']))
                    repository.finish(rid,result=original)
            finally:
                with control_lock: controls.pop(rid,None)
                slot.release()
        try:
            repository.finish(rid,result=original,status='running')
            repository.emit(rid,event('tailoring_requested','tailor','Research requested for '+job['title'],candidate_id=job['id'],url=job['url']))
            threading.Thread(target=execute_tailoring,daemon=True).start()
        except Exception:
            with control_lock: controls.pop(rid,None)
            slot.release();repository.finish(rid,result=original);raise
        return repository.run(rid)

    @app.get('/')
    def index(): return {'service':'Proof API','ui':'http://127.0.0.1:8765','start':'npm run dev'}

    @app.get('/sample-resume.txt')
    def sample(): return Response(SAMPLE_RESUME,media_type='text/plain')

    return app
