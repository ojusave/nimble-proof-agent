"""The only workflow module that depends on LangGraph."""
from typing import TypedDict
from langgraph.graph import StateGraph,START,END
from core.tracing import traced_node,current_span
from core.models import event


class State(TypedDict,total=False):
    resume_text:str
    resume_metadata:dict
    query:str
    count:int
    max_rounds:int
    demo:bool
    profile:str
    search_location:dict
    public_urls:list
    public_research:dict
    round:int
    seen:list
    matches:list
    unknowns:list
    excluded:list
    warnings:list
    plan:dict
    candidates:list
    result:dict


class LangGraphRunner:
    def run(self,workflow,state):
        def search_jobs(inputs):
            jobs=StateGraph(State);parent=current_span.get()
            for name in ('plan','discover','screen','finish'):
                jobs.add_node(name,traced_node(name,getattr(workflow,name),workflow.emit,'job-search',parent))
            jobs.add_edge(START,'plan');jobs.add_edge('plan','discover');jobs.add_edge('discover','screen')
            jobs.add_conditional_edges('screen',workflow.next_step,{'plan':'plan','finish':'finish'})
            jobs.add_edge('finish',END)
            return {'result':jobs.compile().invoke(inputs,config={'recursion_limit':30})['result']}
        # A whole subgraph is one parallel branch: parent superstep barriers must
        # not make slow applicant research hold up the job-discovery node.
        graph=StateGraph(State)
        for name in ('prepare','research_profile','finalize'):
            graph.add_node(name,traced_node(name,getattr(workflow,name),workflow.emit,'research'))
        graph.add_node('jobs',traced_node('jobs',search_jobs,workflow.emit,'research'))
        graph.add_edge(START,'prepare');graph.add_edge('prepare','jobs');graph.add_edge('prepare','research_profile')
        graph.add_edge(['jobs','research_profile'],'finalize')
        graph.add_edge('finalize',END)
        result=graph.compile().invoke(state,config={'recursion_limit':30})['result']
        workflow.emit(event('search_completed','finish','Found %s of %s checked matches'%(len(result['jobs']),state['count']),result=result))
        return result

    def run_tailoring(self,worker,state):
        graph=StateGraph(State)
        graph.add_node('connect_role',traced_node('connect_role',lambda value:{'result':worker.tailor(value)},worker.emit,'role-tailoring'))
        graph.add_edge(START,'connect_role');graph.add_edge('connect_role',END)
        return graph.compile().invoke(state)['result']
