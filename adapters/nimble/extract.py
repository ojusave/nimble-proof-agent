"""Read a known URL with POST /v2/extract and JavaScript rendering."""
from .client import NimbleClient, ProviderError


class NimbleExtract:
    def __init__(self, client: NimbleClient):
        self.client = client

    def extract(self, url: str) -> str:
        response = self.client.request('POST', 'extract', {
            'url': url, 'formats': ['markdown'], 'render': True,
        })
        data = response.get('data')
        status=response.get('status_code')
        if isinstance(status,int) and status>=400:
            raise ProviderError('Source returned HTTP %s; this opening could not be verified.'%status)
        text = data.get('markdown') if isinstance(data, dict) else None
        if response.get('status') != 'success' or not isinstance(text, str) or not text.strip():
            raise ProviderError('This page could not be read.')
        # Keep the returned page. The workflow selects bounded passages explicitly.
        return text
