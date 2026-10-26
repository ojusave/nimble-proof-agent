from dataclasses import dataclass
from .ports import SearchProvider,ExtractProvider,Reasoner,WorkflowRunner


@dataclass
class Services:
    search: SearchProvider
    extract: ExtractProvider
    reasoner: Reasoner
    runner: WorkflowRunner
