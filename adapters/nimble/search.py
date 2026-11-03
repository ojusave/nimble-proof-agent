"""Discover candidate URLs with POST /v2/search."""
from .client import NimbleClient, ProviderError


class NimbleSearch:
    def __init__(self, client: NimbleClient):
        self.client = client

    def search(self, query: str, limit: int) -> list[dict]:
        response = self.client.request('POST', 'search', {
            'query': query,
            'max_results': limit,
            'search_depth': 'standard',
            'output_format': 'markdown',
        })
        results = response.get('results')
        if not isinstance(results, list):
            raise ProviderError('Search returned no result list.')
        return [row for row in results if isinstance(row, dict)]
