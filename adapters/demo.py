"""Clearly fictional examples, using the same workflow as live searches."""
import json

SAMPLE_RESUME='''Jordan Example — Developer Advocate
Eight years building developer tools and teaching technical audiences.
Built Python integrations and JavaScript SDK examples for APIs.
Led developer workshops, wrote technical tutorials, and worked with engineering on documentation.
Experienced with public speaking, community programs, Python, JavaScript, APIs, and open-source contributions.
Seeking developer advocacy roles. This is a fictional demonstration résumé.
'''

# Each example makes a different match or tradeoff visible. These are not real employers.
JOBS = [
    dict(company='Northstar Data', title='Python Developer Advocate', location='Remote · US',
         work='Build Python integrations and teach developers.',
         reason='Your Python integrations match their developer tooling work.',
         resume_quote='Built Python integrations',
         summary='Build Python examples and help developers integrate a data API.',
         gap='Production experience with data pipelines is not shown on your résumé.'),
    dict(company='Relay Cloud', title='Senior API Advocate', location='Remote · US',
         work='Create JavaScript SDK examples for APIs and lead developer workshops.',
         reason='Your SDK examples and workshops fit their API education team.',
         resume_quote='JavaScript SDK examples for APIs',
         summary='Own SDK examples, technical workshops, and the developer feedback loop.',
         gap='The listing asks for ownership of a developer program budget.'),
    dict(company='Fieldnote', title='Technical Educator', location='Remote · US',
         work='Write technical tutorials and documentation for developers.',
         reason='Your tutorials and documentation experience fit this teaching role.',
         resume_quote='wrote technical tutorials',
         summary='Turn complex product features into approachable developer lessons.',
         gap='Video course production experience is not shown on your résumé.'),
    dict(company='Orbit Tools', title='Developer Experience Engineer', location='Remote · US',
         work='Build Python integrations, improve SDKs, and write technical documentation.',
         reason='Your Python and documentation work carry over to developer experience.',
         resume_quote='Built Python integrations',
         summary='Improve the first-run experience for developers using a Python SDK.',
         gap='The role includes SDK release engineering beyond the experience shown.'),
    dict(company='Latticework AI', title='Developer Relations Engineer', location='Remote · region not stated',
         work='Run Python workshops and create tutorials for an AI developer platform.',
         reason='Your Python workshops fit their developer education work.',
         resume_quote='Led developer workshops',
         summary='Teach developers to build with an AI platform through workshops and tutorials.',
         gap='Hands-on experience deploying AI models is not shown on your résumé.'),
    dict(company='Cedar Systems', title='Developer Advocate', location='Onsite · London',
         work='Build Python integrations and speak at developer events.',
         reason='Your Python work fits, but the role conflicts with remote US requirements.',
         resume_quote='Built Python integrations',
         summary='Support a London developer community with examples and events.',
         gap='Requires working onsite in London.'),
]


class DemoAdapter:
    def search(self,query,limit):
        return [{'url':'https://jobs.example.org/careers/%s'%i,
                 'title':job['title']+' — '+job['company'],'description':job['summary']}
                for i,job in enumerate(JOBS,1)][:limit]

    def extract(self,url):
        number=int(url.rsplit('/',1)[-1]);job=JOBS[number-1]
        role=f"{job['company']} is hiring a {job['title']} for its developer advocacy team."
        location=('Work remotely within the United States.' if number<=4 else
                  'Work location is not specified.' if number==5 else 'This role is onsite in London.')
        qualifications=[
            'Preferred: experience running production data pipelines.',
            'You will own the developer program budget.',
            'Experience producing video courses is preferred.',
            'You will manage SDK releases and package publishing.',
            'Hands-on experience deploying AI models is preferred.',
            'You must work onsite in our London office.',
        ]
        return ' '.join([role,job['work'],location,qualifications[number-1],'Apply for this job using our application form.'])

    def structured(self,task,schema,purpose,emit):
        if purpose=='plan':
            return {'roles':['Developer Advocate','Technical Educator','Developer Experience Engineer'],
                    'skills':['Python','JavaScript','APIs','Developer education'],
                    'queries':['developer advocate remote US employer careers','developer educator Python remote US jobs'],
                    'requirements':[{'id':'R1','text':'Remote within the United States'}]}
        payload=json.loads(task.split('\n',1)[1]);item=payload['candidates'][0]
        n=int(item['url'].rsplit('/',1)[-1]);job=JOBS[n-1]
        status='met' if n<=4 else 'unknown' if n==5 else 'conflict'
        evidence='Work remotely within the United States.' if n<=4 else '' if n==5 else 'This role is onsite in London.'
        role=f"{job['company']} is hiring a {job['title']} for its developer advocacy team."
        checks={}
        for requirement in payload['requirements']:
            text=requirement['text'].lower()
            is_location=any(term in text for term in ('remote','united states')) or text.strip()=='us'
            checks[requirement['id']]={'status':status if is_location else 'met','evidence':evidence if is_location else role}
        return {'title':job['title'],'company':job['company'],'employer_url':'https://example.org',
                'location':job['location'],'is_specific_opening':True,'open_status':'open',
                'open_evidence':'Apply for this job using our application form.',
                'relevance':'strong' if n<=2 else 'possible','summary':job['summary'],'checks':checks,
                'strengths':[{'reason':job['reason'],'resume_quote':job['resume_quote'],'job_quote':job['work']}],
                'gaps':[job['gap']]}
