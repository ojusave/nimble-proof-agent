"""Replace providers or the runner here; workflow and UI stay unchanged."""
from adapters.nimble.client import NimbleAdapter
from adapters.demo import DemoAdapter
from core.services import Services
from runners.langgraph import LangGraphRunner


def build_services(settings,demo=False):
    adapter=DemoAdapter() if demo else NimbleAdapter(settings)
    return Services(search=adapter,extract=adapter,reasoner=adapter,runner=LangGraphRunner())
