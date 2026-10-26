"""Implement these protocols to replace APIs without changing the workflow."""
from typing import Callable, Protocol

Emit = Callable[[dict], None]


class SearchProvider(Protocol):
    def search(self, query: str, limit: int) -> list[dict]: ...


class ExtractProvider(Protocol):
    def extract(self, url: str) -> str: ...


class Reasoner(Protocol):
    def structured(self, task: str, schema: dict, purpose: str, emit: Emit) -> dict: ...


class WorkflowRunner(Protocol):
    def run(self, workflow, state: dict) -> dict: ...
