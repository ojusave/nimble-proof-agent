"""Replace providers or the runner here; workflow and UI stay unchanged."""
from adapters.nimble.client import NimbleClient
from adapters.nimble.search import NimbleSearch
from adapters.nimble.extract import NimbleExtract
from adapters.nimble.agent import NimbleAgent
from adapters.demo import DemoAdapter
from core.services import Services
from runners.langgraph import LangGraphRunner
from adapters.llamaindex.parser import LlamaParsePDF
from adapters.resume.router import RoutedResumeParser
from workflows.resume_ingestion import ResumeIngestion
from runners.resume_ingestion import ResumeIngestionRunner


def ingest_resume(settings, filename, content, parser=None, emit=None):
    events=[]
    def record(item):
        events.append(item)
        if emit: emit(item)
    parser = parser or RoutedResumeParser(LlamaParsePDF(settings,emit=record) if settings.llama_api_key else None)
    result=ResumeIngestionRunner().run(ResumeIngestion(parser), filename, content,record)
    return {**result,'ingestion_events':events}


def build_services(settings,demo=False,cancellation=None):
    if demo:
        sample = DemoAdapter()
        return Services(search=sample, extract=sample, reasoner=sample, runner=LangGraphRunner())
    client = NimbleClient(settings,cancellation)
    return Services(search=NimbleSearch(client), extract=NimbleExtract(client),
                    reasoner=NimbleAgent(client,cancellation), runner=LangGraphRunner())
