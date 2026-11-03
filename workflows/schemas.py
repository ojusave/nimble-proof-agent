"""Schemas are task-specific. APIs and framework runners do not own them."""

def obj(properties,required=None):
    return {'type':'object','properties':properties,'required':required or list(properties)}

def array(item): return {'type':'array','items':item}
S={'type':'string'}
B={'type':'boolean'}
STRENGTH=obj({'reason':S,'resume_quote':S,'job_quote':S})
ASSESS=obj({'title':S,'company':S,'employer_url':S,
    'location':S,'is_specific_opening':B,'open_status':{'type':'string','enum':['open','closed','unknown']},
    'open_evidence':S,'relevance':{'type':'string','enum':['strong','possible','weak']},
    'summary':S,'strengths':array(STRENGTH),'gaps':array(S)})


def assessment_schema(requirements):
    from copy import deepcopy
    schema=deepcopy(ASSESS)
    if requirements:
        schema['properties']['checks']=obj({r['id']:obj({'status':{'type':'string','enum':['met','conflict','unknown']},'evidence':S}) for r in requirements})
        schema['required'].append('checks')
    return schema
