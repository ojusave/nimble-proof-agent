"""Small HTTP adapters. Credentials never enter a model prompt or run log."""
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler


class ProviderError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward authorization headers to another host.


def request_json(url, headers, payload=None, method='GET', retries=2):
    request = Request(url, json.dumps(payload).encode() if payload is not None else None, {
        'Content-Type': 'application/json', **headers}, method=method)
    for attempt in range(retries + 1):
        try:
            with build_opener(NoRedirect()).open(request, timeout=90) as response:
                raw = response.read(4_000_001)
            if len(raw) > 4_000_000:
                raise ProviderError('Provider response exceeded the 4 MB limit.')
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ProviderError('Provider returned an unexpected JSON shape.')
            return result
        except HTTPError as error:
            if error.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise ProviderError('Provider HTTP %s; check credentials, quota, and API access.' % error.code) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise ProviderError('Provider connection or JSON response failed.') from None


def post_json(url, payload, headers, retries=2):
    return request_json(url, headers, payload, 'POST', retries)


def get_json(url, headers):
    return request_json(url, headers)


class Nimble:
    def __init__(self):
        self.key = os.environ.get('NIMBLE_API_KEY', '')
        if not self.key:
            raise ProviderError('Set NIMBLE_API_KEY in .env before starting a live run.')

    def call(self, path, payload):
        return post_json('https://sdk.nimbleway.com/v2/' + path, payload,
                         {'Authorization': 'Bearer ' + self.key})

    def search(self, query):
        result = self.call('search', {'query': query, 'max_results': 5,
                                     'search_depth': 'standard', 'output_format': 'markdown'})
        if not isinstance(result.get('results'), list):
            raise ProviderError('Nimble search response has no results list.')
        return result['results']

    def extract(self, url):
        result = self.call('extract', {'url': url, 'formats': ['markdown']})
        if result.get('status') != 'success':
            raise ProviderError('Nimble could not extract this source.')
        content = result.get('data', {}).get('markdown')
        if not isinstance(content, str) or not content.strip():
            raise ProviderError('Nimble returned no readable Markdown for this source.')
        return content[:20000]
