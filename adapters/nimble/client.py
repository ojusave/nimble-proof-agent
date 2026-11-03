"""Shared HTTP transport; endpoint-specific behavior lives in adjacent modules."""
import time

import httpx

from core.settings import Settings
from core.cancellation import CancellationToken
from core.errors import ProviderError


class NimbleClient:
    def __init__(self, settings: Settings, cancellation=None):
        if not settings.api_key:
            raise ProviderError('Add NIMBLE_API_KEY to .env to run a live search.')
        self.settings = settings
        self.cancellation = cancellation or CancellationToken()
        self.headers = {
            'Authorization': 'Bearer ' + settings.api_key,
            'X-Client-Source': 'proof-job-matcher',
        }

    def request(self, method, path, payload=None, retries=1):
        """Retry transient HTTP failures only when the caller permits it."""
        for attempt in range(retries + 1):
            self.cancellation.check()
            try:
                with httpx.Client(timeout=self.settings.request_timeout,
                                  follow_redirects=False, trust_env=False) as client:
                    response = client.request(method, self.settings.api_base + '/' + path,
                                              headers=self.headers, json=payload)
            except httpx.HTTPError:
                self.cancellation.check()
                raise ProviderError('Nimble connection failed. The request was not resubmitted.') from None
            self.cancellation.check()
            if response.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                self.cancellation.wait(2 ** attempt)
                continue
            if response.status_code >= 300:
                hint = ''
                if response.status_code == 422:
                    try:
                        hint = '; '.join(self._messages(response.json()))[:500]
                    except ValueError:
                        pass
                raise ProviderError('Nimble returned HTTP %s. %s' %
                                    (response.status_code, hint or 'Check API access or quota.'))
            if len(response.content) > 5_000_000:
                raise ProviderError('Nimble response exceeded 5 MB.')
            try:
                value = response.json()
            except ValueError:
                raise ProviderError('Nimble returned invalid JSON.') from None
            if not isinstance(value, dict):
                raise ProviderError('Unexpected Nimble response.')
            return value

    @staticmethod
    def _messages(value):
        # Never expose validation input, which can contain the user's résumé.
        if isinstance(value, str):
            return [value[:300]]
        if isinstance(value, list):
            return [message for item in value for message in NimbleClient._messages(item)]
        if isinstance(value, dict):
            return [message for key, item in value.items()
                    if key in ('detail', 'error', 'message', 'msg')
                    for message in NimbleClient._messages(item)]
        return []
