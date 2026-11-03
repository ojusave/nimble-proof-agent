"""Implement these protocols to replace APIs without changing the workflow."""
from typing import Callable, Protocol
from .models import ResearchResult

Emit = Callable[[dict], None]


class SearchProvider(Protocol):
    def search(self, query: str, limit: int) -> list[dict]: ...


class ExtractProvider(Protocol):
    def extract(self, url: str) -> str: ...


class Reasoner(Protocol):
    def structured(self, task: str, schema: dict, purpose: str, emit: Emit, continuation: dict | None = None) -> ResearchResult: ...


class WorkflowRunner(Protocol):
    def run(self, workflow, state: dict) -> dict: ...
    def run_tailoring(self, worker, state: dict) -> dict: ...


class ResumeParser(Protocol):
    def parse(self, filename: str, content: bytes) -> dict: ...
