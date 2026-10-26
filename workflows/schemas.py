"""Schemas are task-specific. APIs and framework runners do not own them."""

def obj(properties,required=None):
    return {'type':'object','properties':properties,'required':required or list(properties)}

def array(item): return {'type':'array','items':item}
S={'type':'string'}
B={'type':'boolean'}
PLAN=obj({'roles':array(S),'skills':array(S),'queries':array(S),
          'requirements':array(obj({'id':S,'text':S}))})
CHECK=obj({'id':S,'status':{'type':'string','enum':['met','conflict','unknown']},'evidence':S})
STRENGTH=obj({'reason':S,'resume_quote':S,'job_quote':S})
ASSESS=obj({'jobs':array(obj({'candidate_id':S,'title':S,'company':S,'employer_url':S,
    'location':S,'is_specific_opening':B,'open_status':{'type':'string','enum':['open','closed','unknown']},
    'open_evidence':S,'relevance':{'type':'string','enum':['strong','possible','weak']},
    'summary':S,'checks':array(CHECK),'strengths':array(STRENGTH),'gaps':array(S)}))})


def assessment_schema(requirements):
    from copy import deepcopy
    schema=deepcopy(ASSESS['properties']['jobs']['items'])
    del schema['properties']['candidate_id']
    schema['required'].remove('candidate_id')
    if requirements:
        schema['properties']['checks']=obj({r['id']:obj({'status':{'type':'string','enum':['met','conflict','unknown']},'evidence':S}) for r in requirements})
    else:
        del schema['properties']['checks']
        schema['required'].remove('checks')
    return schema
