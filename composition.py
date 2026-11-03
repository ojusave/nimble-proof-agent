"""Replace providers or the runner here; workflow and UI stay unchanged."""
from adapters.nimble.client import NimbleClient
from adapters.nimble.search import NimbleSearch
from adapters.nimble.extract import NimbleExtract
from adapters.nimble.agent import NimbleAgent
from adapters.demo import DemoAdapter
from core.services import Services
from runners.langgraph import LangGraphRunner


def build_services(settings,demo=False,cancellation=None):
    if demo:
        sample = DemoAdapter()
        return Services(search=sample, extract=sample, reasoner=sample, runner=LangGraphRunner())
    client = NimbleClient(settings,cancellation)
    return Services(search=NimbleSearch(client), extract=NimbleExtract(client),
                    reasoner=NimbleAgent(client,cancellation), runner=LangGraphRunner())
