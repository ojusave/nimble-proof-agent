"""Synthetic fixtures exercise the real workflow without calling a provider."""
import json

SAMPLE_RESUME='''Jordan Example — Developer Advocate
Eight years building developer tools and teaching technical audiences.
Built Python integrations and JavaScript SDK examples for APIs.
Led developer workshops, wrote technical tutorials, and worked with engineering on documentation.
Experienced with public speaking, community programs, Python, JavaScript, APIs, and open-source contributions.
Seeking developer advocacy roles. This is a fictional demonstration résumé.
'''


class DemoAdapter:
    def search(self,query,limit):
        return [{'url':'https://jobs.example.org/careers/%s'%i,'title':title+' — Example '+str(i),'description':'Synthetic employer vacancy'}
                for i,title in enumerate(['Developer Advocate','Senior Developer Advocate','Developer Educator','Developer Advocate','Developer Advocate','Developer Advocate'],1)][:limit]

    def extract(self,url):
        number=int(url.rsplit('/',1)[-1])
        return ('Example %s is hiring a Developer Advocate. Build Python integrations and teach developers. '
                'Requirements: Python, JavaScript, APIs, workshops, and technical writing. '%number)+(
                'Work remotely within the United States. ' if number<=4 else 'Work location is not specified. ' if number==5 else 'This role is onsite in London. ')+ 'Apply for this job using our application form.'

    def structured(self,task,schema,purpose,emit,input_data=None):
        if purpose=='plan':
            return {'roles':['Developer Advocate'],'skills':['Python','JavaScript','APIs'],
                    'queries':['developer advocate remote US employer careers','developer educator Python remote US jobs'],
                    'requirements':[{'id':'R1','text':'Remote within the United States'}]}
        payload=json.loads(task.split('\n',1)[1])
        jobs=[]
        for item in payload['candidates']:
            n=int(item['url'].rsplit('/',1)[-1]);status='met' if n<=4 else 'unknown' if n==5 else 'conflict'
            evidence='Work remotely within the United States.' if n<=4 else '' if n==5 else 'This role is onsite in London.'
            jobs.append({'candidate_id':item['candidate_id'],'title':'Developer Advocate','company':'Example '+str(n),
                'employer_url':'https://example.org','location':'Remote · US' if n<=4 else 'Not specified' if n==5 else 'London',
                'is_specific_opening':True,'open_status':'open','open_evidence':'Apply for this job using our application form.',
                'relevance':'strong' if n<=2 else 'possible','summary':'Python integrations and developer education align with your experience.',
                'checks':[{'id':r['id'],'status':status if any(t in r['text'].lower() for t in ('remote','united states')) or r['text'].strip().lower()=='us' else 'met', 'evidence':evidence if any(t in r['text'].lower() for t in ('remote','united states')) or r['text'].strip().lower()=='us' else 'Example %s is hiring a Developer Advocate.'%n} for r in payload['requirements']],
                'strengths':[{'reason':'Relevant Python integration experience.','resume_quote':'Built Python integrations',
                              'job_quote':'Build Python integrations and teach developers.'}],
                'gaps':['Confirm team scope during an interview.']})
        job=jobs[0]
        job['checks']={check['id']:{k:v for k,v in check.items() if k!='id'} for check in job['checks']}
        return job
