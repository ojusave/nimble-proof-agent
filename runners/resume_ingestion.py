"""LangGraph boundary for file ingestion: parse once, then derive a grounded profile."""
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from core.tracing import traced_node


class IngestionState(TypedDict, total=False):
    filename: str
    content: bytes
    parsed: dict
    profile: dict


class ResumeIngestionRunner:
    def run(self, workflow, filename, content,emit=lambda item:None):
        graph = StateGraph(IngestionState)
        graph.add_node('parse',traced_node('parse',workflow.parse,emit,'resume-ingestion'))
        graph.add_node('profile',traced_node('profile',workflow.profile,emit,'resume-ingestion'))
        graph.add_edge(START, 'parse'); graph.add_edge('parse', 'profile'); graph.add_edge('profile', END)
        state = graph.compile().invoke({'filename': filename, 'content': content})
        return {**state['parsed'], 'profile': state['profile']}
