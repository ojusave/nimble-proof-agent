"""Job-matching business logic. No LangGraph or Nimble SDK imports."""
import hashlib
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.models import Job,event
from core.cancellation import SearchCancelled
from core.urls import public_url,employer_host,host,belongs,AGGREGATORS
from workflows.application_links import application_link
from core.text import professional_text,shared_skill_evidence
from .schemas import assessment_schema
from .planning import plan_search
from .prompts import assessment_task
from .resume_profile import resume_profile,resolve_location
from .discovery import is_index,linked_openings
from .applicant_research import ApplicantResearch
from .resume_tailoring import ResumeTailoring


def contains(quote,text):
    norm=lambda s: re.sub(r'\s+',' ',s.translate(str.maketrans({'’':"'",'‘':"'",'“':'\"','”':'\"'}))).strip().casefold()
    return isinstance(quote,str) and len(quote.strip())>=8 and norm(quote) in norm(text)


class JobWorkflow:
    def __init__(self,search,extract,reasoner,settings,emit,cancel=None):
        self.search_provider=search;self.extractor=extract;self.reasoner=reasoner
        self.settings=settings;self.emit=emit;self.cancel=cancel or (lambda:False)
        self.link_lock=threading.Lock();self.queued=set();self.followed=0

    def send(self,kind,step,message,**data):
        self.check_cancelled()
        self.emit(event(kind,step,message,**data))

    def check_cancelled(self):
        if self.cancel(): raise SearchCancelled('Search stopped by you.')

    def prepare(self,state):
        metadata=state.get('resume_metadata',{})
        self.send('step_started','resume','Loading the parsed résumé',tool='Stored résumé',parser=metadata.get('parser','local'))
        if metadata.get('ingestion_events'):
            self.send('saved_ingestion','resume','Reusing the earlier parse; no parsing API call was made for this search',
                      parser=metadata.get('parser'),parser_version=metadata.get('parser_version'),parse_job_id=metadata.get('parse_job_id'),events=metadata['ingestion_events'])
        text=professional_text(state['resume_text'])
        location=resolve_location(resume_profile(state['resume_text']),state['query'])
        self.send('step_completed','resume','Résumé ready for matching',tool='Stored résumé',characters=len(text),parser=metadata.get('parser','local'))
        return {'profile':text,'search_location':location,'round':0,'seen':[],'matches':[],'unknowns':[],'excluded':[], 'warnings':[],'plan':None}

    def plan(self,state):
        round_no=state['round']+1
        self.send('step_started','plan','Planning search round %s'%round_no,tool='Local planner',round=round_no)
        plan=plan_search(state['profile'],state['query'],round_no,state.get('plan'),state.get('search_location'))
        self.send('plan_ready','plan','Search plan ready',tool='Local planner',queries=plan['queries'],
                  requirements=plan['requirements'],roles=plan.get('roles',[]),skills=plan.get('skills',[]),round=round_no,search_location=state.get('search_location'))
        return {'plan':plan,'round':round_no}

    def public_worker(self):
        return ApplicantResearch(self.reasoner,self.extractor,self.emit,self.send,self.check_cancelled)

    def tailoring_worker(self):
        return ResumeTailoring(self.reasoner,self.extractor,self.emit,self.send,self.check_cancelled)

    def research_profile(self,state):
        return {'public_research':self.public_worker().research(state)}

    def finalize(self,state):
        self.check_cancelled()
        result={**state['result'],'public_research':state.get('public_research',{}),'resume_proposals':{}}
        return {'result':result}

    def discover(self,state):
        seen=set(state['seen']);candidates=[];warnings=list(state['warnings'])
        cap=min(self.settings.candidates_per_round,max(state['count']+2,4))
        for query in state['plan']['queries']:
            self.check_cancelled()
            self.send('tool_started','search','Searching employer openings',tool='Nimble Search API',query=query)
            try: rows=self.search_provider.search(query,min(20,max(8,state['count']*2)))
            except SearchCancelled: raise
            except Exception as error:
                warnings.append(str(error));self.send('tool_failed','search',str(error),tool='Nimble Search API');continue
            found=[]
            for row in rows:
                try: url=public_url(row.get('url'))
                except (ValueError,AttributeError): continue
                if url in seen or belongs(host(url),AGGREGATORS): continue
                seen.add(url)
                item={'id':hashlib.sha256(url.encode()).hexdigest()[:16], 'url':url,
                      'title':str(row.get('title') or url)[:250],'snippet':str(row.get('description') or '')[:1000]}
                candidates.append(item);found.append({k:item[k] for k in ('id','url','title')})
                if len(candidates)<=cap:
                    self.send('candidate_discovered','search','Found a page to check',candidate=item)
            self.send('search_results','search','Found %s new candidate pages'%len(found),tool='Nimble Search API',query=query,
                      candidates=found,total_returned=len(rows))
        selected=candidates[:cap]
        with self.link_lock: self.queued.update(item['url'] for item in selected)
        # Only mark inspected/queued URLs seen; unused candidates may be found again in round two.
        checked=set(state['seen'])|{c['url'] for c in selected}
        return {'candidates':selected,'seen':sorted(checked),'warnings':warnings}

    def follow_index(self,item,text,state):
        links=linked_openings(text,item['url'],state['plan'].get('roles',[]))
        selected=[]
        with self.link_lock:
            for link in links:
                if link['url'] in self.queued or self.followed>=self.settings.linked_candidates: continue
                self.queued.add(link['url']);self.followed+=1;selected.append(link)
        self.send('listing_links_found','search','Following individual openings from a listing index',
                  candidate_id=item['id'],url=item['url'],links=selected)
        for link in selected: self.send('candidate_discovered','search','Found a linked opening',candidate=link)
        matches=[];unknowns=[];excluded=[]
        for link in selected:
            good,review,rejected=self.screen_batch([link],state,follow=False)
            matches.extend(good);unknowns.extend(review);excluded.extend(rejected)
        record={'url':item['url'],'title':item['title'],'candidate_id':item['id'],
                'reason':('Listing index; followed %s individual openings.'%len(selected)) if selected else 'Listing index; no new relevant employer links were found.',
                'category':'index'}
        self.send('job_excluded','verify',record['reason'],**record)
        return matches,unknowns,excluded+[record]

    def screen_batch(self,candidates,state,follow=True):
        readable=[];excluded=[]
        for item in candidates:
            self.check_cancelled()
            self.send('tool_started','extract','Reading '+item['title'],tool='Nimble Extract API',url=item['url'],candidate_id=item['id'])
            try:
                text=self.extractor.extract(item['url'])
                self.send('extraction_ready','extract','Listing text received',tool='Nimble Extract API',url=item['url'],
                          candidate_id=item['id'],characters=len(text),preview=text[:260])
                if re.search(r'(this (?:job|position) is no longer available|position has been filled|job has been closed)',text,re.I):
                    raise ValueError('Listing says the position is closed.')
                if len(text.strip())<100: raise ValueError('Not enough readable listing content.')
                if follow and is_index(item['url'],text): return self.follow_index(item,text,state)
                readable.append({**item,'text':text})
            except SearchCancelled: raise
            except Exception as error:
                record={'url':item['url'],'title':item['title'],'candidate_id':item['id'],'reason':str(error),
                        'category':'closed' if str(error).startswith('Listing says') else 'provider_error'};excluded.append(record)
                self.send('job_excluded','verify',record['reason'],**record)
        self.check_cancelled()
        if not readable: return [],[],excluded
        self.send('tool_started','match','Checking listing against your résumé',tool='Nimble Agent API',
                  candidate_ids=[r['id'] for r in readable])
        try:
            task,evidence,resume_passages=assessment_task(state['profile'],state['query'],state['plan']['requirements'],readable[0])
            self.send('evidence_selected','extract','Select evidence excerpts',tool='Local evidence selection',
                      candidate_id=readable[0]['id'],url=readable[0]['url'],evidence=evidence)
            research=self.reasoner.structured(task,assessment_schema(state['plan']['requirements']),'match',lambda item:self.emit({**item,'data':{**item.get('data',{}),'candidate_ids':[r['id'] for r in readable],'round':state.get('round',1)}}))
            assessment=research.content
            # Preserve provenance even for excluded listings in the saved activity.
            provenance={'trust':research.trust,'run_id':research.run_id,'agent_id':research.agent_id}
            self.send('research_completed','match','Research returned; checking quotations',
                      tool='Nimble Agent API',candidate_id=readable[0]['id'],url=readable[0]['url'],research=provenance)
            if isinstance(assessment,dict):
                assessment={**assessment,'candidate_id':readable[0]['id'],
                            '_research':provenance,'_evidence':evidence,'_resume_passages':resume_passages}
                checks=assessment.get('checks',{})
                if isinstance(checks,dict):
                    assessment['checks']=[{**value,'id':key} for key,value in checks.items() if isinstance(value,dict)]
            assessments=[assessment]
        except SearchCancelled: raise
        except Exception as error:
            for item in readable:
                record={'url':item['url'],'title':item['title'],'candidate_id':item['id'],'reason':'Matching failed: '+str(error),'category':'provider_error'};excluded.append(record)
                self.send('job_excluded','match',record['reason'],**record)
            return [],[],excluded
        if not isinstance(assessments,list): assessments=[]
        by_id={a.get('candidate_id'):a for a in assessments if isinstance(a,dict) and isinstance(a.get('candidate_id'),str)}
        matches=[];unknowns=[]
        for item in readable:
            assessment=by_id.get(item['id'])
            decision,value=self.validate(item,assessment,state)
            if follow and decision=='exclude' and value=='Not a specific job opening.':
                return self.follow_index(item,item['text'],state)
            if decision=='match':
                matches.append(value);self.send('job_matched','match','Checked match: '+value['title'],job=value)
            elif decision=='unknown':
                unknowns.append(value);self.send('job_unknown','verify','Needs confirmation: '+value['title'],job=value)
            else:
                record={'url':item['url'],'title':item['title'],'candidate_id':item['id'],'reason':value,'category':'excluded'};excluded.append(record)
                self.send('job_excluded','verify',value,**record)
        return matches,unknowns,excluded

    def validate(self,item,a,state):
        if not isinstance(a,dict): return 'exclude','No structured assessment returned.'
        for key in ('strengths','checks','gaps'):
            if a.get(key) is not None and not isinstance(a[key],list):
                return 'exclude','Invalid assessment field: '+key
        if a.get('is_specific_opening') is not True: return 'exclude','Not a specific job opening.'
        try: employer=public_url(a.get('employer_url'))
        except ValueError: return 'exclude','Employer website could not be established.'
        if not employer_host(item['url'],employer): return 'exclude','Could not establish an employer-hosted listing.'
        if a.get('open_status')=='closed': return 'exclude','Listing is closed.'
        further_research=bool(state.get('public_urls'))
        if a.get('relevance') not in ('strong','possible') and not (further_research and a.get('relevance')=='weak'):
            return 'exclude','Insufficient professional fit.'
        for key in ('title','company','location','summary'):
            if not isinstance(a.get(key),str) or (key in ('title','company') and not a[key].strip()):
                return 'exclude','Missing listing details.'
        strengths=[]
        page_passages=a.get('_evidence',{}).get('passages',[{'text':item['text']}])
        resume_passages=a.get('_resume_passages',[{'text':state['profile']}])
        in_page=lambda quote:any(contains(quote,p['text']) for p in page_passages)
        in_resume=lambda quote:any(contains(quote,p['text']) for p in resume_passages)
        for strength in a.get('strengths') or []:
            if isinstance(strength,dict) and isinstance(strength.get('reason'),str) and in_resume(strength.get('resume_quote')) and in_page(strength.get('job_quote')):
                strengths.append(strength)
            elif isinstance(strength,dict) and not strength.get('resume_quote') and in_page(strength.get('job_quote')):
                paired=shared_skill_evidence(strength['job_quote'],'\n'.join(p['text'] for p in resume_passages))
                if paired and paired not in strengths: strengths.append(paired)
        if not strengths and not further_research: return 'exclude','No résumé-to-listing evidence could be checked.'
        supplied={c.get('id'):c for c in (a.get('checks') or []) if isinstance(c,dict)}
        checks=[];uncertain=[]
        if not strengths or a.get('relevance')=='weak': uncertain.append('Professional fit beyond the résumé needs confirmation')
        for requirement in state['plan']['requirements']:
            check=supplied.get(requirement['id'],{})
            status=check.get('status','unknown');quote=check.get('evidence','')
            if status not in ('met','conflict','unknown'): status='unknown'
            if status!='unknown' and not in_page(quote): status='unknown'
            checks.append({'id':requirement['id'],'requirement':requirement['text'],'status':status,'evidence':quote if in_page(quote) else ''})
            if status=='conflict': return 'exclude','Conflicts with: '+requirement['text']
            if status=='unknown': uncertain.append(requirement['text'])
        if a.get('open_status')!='open' or not in_page(a.get('open_evidence')):
            uncertain.append('Current application availability')
        gaps=[g for g in (a.get('gaps') or []) if isinstance(g,str)]
        job=Job(id=item['id'],title=a['title'],company=a['company'],url=item['url'],location=a['location'],
                fit=a['relevance'],checks=checks,strengths=strengths,gaps=gaps,summary=a['summary']).to_dict()
        job['open_evidence']=a.get('open_evidence','') if in_page(a.get('open_evidence')) else ''
        job['research']=a.get('_research',{})
        job['evidence']=a.get('_evidence',{})
        job['unknown_requirements']=uncertain
        application=application_link(item['text'],item['url'],employer)
        job['application_url']=application['url']
        job['application_link_source']=application['source']
        if state.get('demo'): job['sample_listing']=item['text']
        return ('unknown' if uncertain else 'match'),job

    def screen(self,state):
        self.check_cancelled()
        items=state['candidates'];size=1  # One result belongs to one known listing; no model-generated identity mapping.
        batches=[items[i:i+size] for i in range(0,len(items),size)]
        matches=list(state['matches']);unknowns=list(state['unknowns']);excluded=list(state['excluded'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(self.screen_batch,batch,state) for batch in batches]
            for future in as_completed(futures):
                new,unknown,rejected=future.result();matches.extend(new);unknowns.extend(unknown);excluded.extend(rejected)
        self.send('round_completed','search','Round %s: %s checked matches'%(state['round'],len(matches)),round=state['round'],
                  matched=len(matches),requested=state['count'],unknown=len(unknowns),excluded=len(excluded))
        return {'matches':matches,'unknowns':unknowns,'excluded':excluded}

    def next_step(self,state):
        if len(state['matches'])>=state['count'] or state['round']>=state['max_rounds'] or self.cancel(): return 'finish'
        return 'plan'

    def finish(self,state):
        self.check_cancelled()
        matches=sorted(state['matches'],key=lambda j:(j['fit']!='strong',len(j['gaps']),-len(j['strengths']),j['id']))
        selected=matches[:state['count']]
        for rank,job in enumerate(selected,1): job.update(rank=rank,provisional=False)
        missing=max(0,state['count']-len(selected))
        result={'kind':'job_search','jobs':selected,'unknowns':state['unknowns'],'excluded':state['excluded'],
                'warnings':state['warnings'],'requested':state['count'],'rounds':state['round'],'shortfall':missing,
                'requirements':state['plan']['requirements'],
                'search_location':state.get('search_location'),
                'next_question':('Some pages could not be checked. Review those sources or try another search.' if any(x.get('category')=='provider_error' for x in state['excluded']) else 'Try a different role or location to broaden the search.') if missing else None,
                'mode':'synthetic demo' if state.get('demo') else 'live'}
        self.send('job_research_completed','finish','Job checks finished; keeping received results available',matched=len(selected))
        return {'result':result}
