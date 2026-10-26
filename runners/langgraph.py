"""The only workflow module that depends on LangGraph."""
from typing import TypedDict
from langgraph.graph import StateGraph,START,END


class State(TypedDict,total=False):
    resume_text:str
    query:str
    count:int
    max_rounds:int
    demo:bool
    profile:str
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
        graph=StateGraph(State)
        for name in ('prepare','plan','discover','screen','finish'):
            graph.add_node(name,getattr(workflow,name))
        graph.add_edge(START,'prepare');graph.add_edge('prepare','plan')
        graph.add_edge('plan','discover');graph.add_edge('discover','screen')
        graph.add_conditional_edges('screen',workflow.next_step,{'plan':'plan','finish':'finish'})
        graph.add_edge('finish',END)
        return graph.compile().invoke(state,config={'recursion_limit':30})['result']
