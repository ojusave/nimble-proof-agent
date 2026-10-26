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


def post_json(url, payload, headers):
    request = Request(url, json.dumps(payload).encode(), {
        'Content-Type': 'application/json', **headers}, method='POST')
    for attempt in range(3):
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
            if error.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise ProviderError('Provider HTTP %s; check credentials, quota, and model access.' % error.code) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise ProviderError('Provider connection or JSON response failed.') from None


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


class Claude:
    def __init__(self):
        self.key = os.environ.get('ANTHROPIC_API_KEY', '')
        self.model = os.environ.get('ANTHROPIC_MODEL', 'claude-sonnet-4-6')
        if not self.key:
            raise ProviderError('Set ANTHROPIC_API_KEY in .env before starting a live run.')

    def next(self, messages, tools, system, first):
        payload = {'model': self.model, 'max_tokens': 3000, 'system': system,
                   'messages': messages, 'tools': tools,
                   'tool_choice': {'type': 'tool', 'name': 'search_web'} if first else {'type': 'any'}}
        result = post_json('https://api.anthropic.com/v1/messages', payload,
                          {'x-api-key': self.key, 'anthropic-version': '2023-06-01'})
        if result.get('stop_reason') == 'max_tokens':
            raise ProviderError('Model output was truncated. Narrow the research question.')
        blocks = result.get('content')
        if not isinstance(blocks, list):
            raise ProviderError('Model response has no content blocks.')
        return blocks
