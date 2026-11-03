"""LlamaIndex LlamaParse v2 adapter. Credentials and document bytes stay server-side."""
import json
import time
from urllib.parse import quote

import httpx
from core.models import event

from adapters.resume.parser import clean_text, validate_upload


class LlamaParsePDF:
    def __init__(self, settings, transport=None,emit=None):
        self.settings = settings
        self.transport = transport
        self.emit=emit or (lambda item:None)

    def parse(self, filename, content):
        validate_upload(filename, content)
        settings = self.settings
        configuration = {
            'tier': 'agentic', 'version': settings.llama_parse_version,
            'page_ranges': {'max_pages': 10},
            'processing_control': {'timeouts': {'base_in_seconds': settings.llama_parse_timeout}},
        }
        deadline = time.monotonic() + settings.llama_parse_timeout
        job_id = None
        try:
            with httpx.Client(base_url=settings.llama_api_base, transport=self.transport,
                              headers={'Authorization': 'Bearer ' + settings.llama_api_key},
                              timeout=40, trust_env=False) as client:
                # Submit once: a lost response may still have created a billable job.
                created = client.post('/api/v2/parse/upload',
                                      files={'file': ('resume.pdf', content, 'application/pdf')},
                                      data={'configuration': json.dumps(configuration)})
                self.check_response(created)
                job_id = created.json().get('id')
                if not isinstance(job_id, str) or not job_id: raise ValueError('LlamaParse did not return a parse job ID.')
                self.emit(event('parser_submitted','parse','LlamaParse accepted the PDF',tool='LlamaIndex LlamaParse',job_id=job_id,tier='agentic',version=settings.llama_parse_version))
                previous=None
                while time.monotonic() < deadline:
                    response = client.get('/api/v2/parse/' + quote(job_id, safe=''), params={'expand': 'markdown'})
                    self.check_response(response)
                    payload = response.json()
                    job = payload.get('job', {})
                    status = job.get('status')
                    if status!=previous:
                        self.emit(event('parser_status','parse','LlamaParse: '+str(status),tool='LlamaIndex LlamaParse',job_id=job_id,status=status))
                        previous=status
                    if status == 'COMPLETED':
                        pages = payload.get('markdown', {}).get('pages', [])
                        if not isinstance(pages, list) or not pages: raise ValueError('LlamaParse returned no readable pages.')
                        kept = [{'page': index + 1, 'text': p['markdown']} for index, p in enumerate(pages)
                                if isinstance(p, dict) and isinstance(p.get('markdown'), str)]
                        if len(kept) != len(pages): raise ValueError('LlamaParse returned an incomplete page result.')
                        return {'text': clean_text('\n\n'.join(p['text'] for p in kept)),
                                'parser': 'llamaparse', 'pages': kept, 'parse_job_id': job_id,
                                'parser_version': settings.llama_parse_version}
                    if status in ('FAILED', 'CANCELLED'):
                        raise ValueError('LlamaParse could not parse this PDF. Try a clearer PDF, DOCX, or TXT.')
                    if status not in ('PENDING', 'RUNNING', 'QUEUED'):
                        raise ValueError('LlamaParse returned an unexpected job status.')
                    time.sleep(1)
                raise ValueError('PDF parsing timed out. The remote parse may continue; try DOCX or TXT instead.')
        except httpx.HTTPError:
            raise ValueError('LlamaParse connection failed. The PDF was not automatically resubmitted. Try again or use DOCX/TXT.') from None
        except (KeyError, TypeError, json.JSONDecodeError):
            raise ValueError('LlamaParse returned an unreadable response.') from None

    @staticmethod
    def check_response(response):
        if response.status_code in (401, 403): raise ValueError('PDF parsing access is unavailable. Check the server’s LlamaCloud key.')
        if response.status_code in (402, 429): raise ValueError('PDF parsing quota is unavailable. Try again later or use DOCX/TXT.')
        if response.status_code >= 300: raise ValueError('LlamaParse could not process this PDF (HTTP %s).' % response.status_code)

