"""Actual framework-node spans with allowlisted inputs and outputs, never model reasoning."""
import time
from uuid import uuid4
from .models import event
from contextvars import ContextVar

current_span=ContextVar('proof_current_span',default=None)


def summary(value):
    result={}
    for key in ('query','count','round','search_location','public_urls'):
        if key in value: result[key]=value[key]
    if 'content' in value: result['file_bytes']=len(value['content'])
    if 'filename' in value: result['filename']=value['filename']
    if 'resume_text' in value: result['resume_characters']=len(value['resume_text'])
    if 'resume_metadata' in value:
        metadata=value['resume_metadata']
        result['saved_parser']={key:metadata[key] for key in ('parser','parser_version','parse_job_id') if key in metadata}
    if isinstance(value.get('profile'),dict): result['profile']=value['profile']
    if 'plan' in value and value['plan']: result['plan']=value['plan']
    if 'parsed' in value:
        parsed=value['parsed'];result['parsed']={key:parsed[key] for key in ('parser','parser_version','parse_job_id') if key in parsed}
        result['parsed'].update(characters=len(parsed['text']),pages=len(parsed.get('pages',[])))
    for key in ('candidates','matches','unknowns','excluded'):
        if key in value: result[key]={'count':len(value[key]),'items':[{k:item[k] for k in ('id','title','url','reason') if k in item} for item in value[key]]}
    if 'public_research' in value:
        research=value['public_research'];result['public_research']={'status':research.get('status'),'source_checked_facts':len(research.get('facts',[]))}
    if 'result' in value:
        record=value['result']
        if record and all(isinstance(item,dict) and 'edits' in item for item in record.values()):
            result['result']={'roles':len(record),'resume_proposals':sum(len(item['edits']) for item in record.values())}
        else:
            result['result']={'matches':len(record.get('jobs',[])),'needs_review':len(record.get('unknowns',[])),
                'resume_proposals':sum(len(p.get('edits',[])) for p in record.get('resume_proposals',{}).values())}
    return result


def traced_node(name,fn,emit,graph,parent_id=None):
    def invoke(state):
        span=uuid4().hex;started=time.monotonic()
        fields={'span_id':span,'parent_id':parent_id,'framework':'LangGraph','graph':graph,'node':name}
        emit(event('node_started','graph',name+' started',**fields,input=summary(state)))
        token=current_span.set(span)
        try: output=fn(state)
        except Exception as error:
            from .cancellation import SearchCancelled
            if not isinstance(error,SearchCancelled):
                emit(event('node_failed','graph',name+' failed',**fields,duration_ms=round((time.monotonic()-started)*1000),error=type(error).__name__))
            raise
        finally: current_span.reset(token)
        emit(event('node_completed','graph',name+' completed',**fields,duration_ms=round((time.monotonic()-started)*1000),output=summary(output)))
        return output
    return invoke
