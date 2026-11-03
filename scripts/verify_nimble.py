"""Opt-in, bounded paid integration check using only a fictional résumé."""
import argparse
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from adapters.demo import SAMPLE_RESUME
from api.app import create_app
from core.settings import Settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Allow paid Nimble API calls')
    parser.add_argument('--query', default='Python developer advocate')
    parser.add_argument('--candidates', type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    if not args.live:
        parser.error('Pass --live to allow two discovery searches and at most two paid research runs.')
    settings = Settings.load()
    if not settings.api_key:
        parser.error('Configure NIMBLE_API_KEY in .env first.')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = ROOT / 'work' / ('nimble-verification-' + stamp)
    output.mkdir(parents=True)
    # Separate from the user's résumé/history database. The saved report is ignored by Git.
    with tempfile.TemporaryDirectory(prefix='proof-verify-') as directory:
        settings = replace(settings, data_dir=Path(directory), max_rounds=1,
                           candidates_per_round=args.candidates)
        with TestClient(create_app(settings)) as client:
            upload = client.post('/api/resumes', files={'file': ('fictional-resume.txt', SAMPLE_RESUME.encode(), 'text/plain')})
            upload.raise_for_status()
            started = client.post('/api/searches', json={'resume_id': upload.json()['id'], 'query': args.query, 'count': 1})
            started.raise_for_status()
            rid = started.json()['id']; cursor = 0
            print('Live run ' + rid + ': one round, at most ' + str(args.candidates) + ' research tasks.', flush=True)
            while True:
                run = client.get('/api/searches/' + rid).json()
                for item in client.app.state.repository.events(rid, cursor):
                    cursor = item['seq']
                    if item['type'] in ('search_results', 'extraction_ready', 'provider_started', 'provider_status', 'research_completed', 'job_matched', 'job_unknown', 'job_excluded', 'run_failed'):
                        print(item['type'] + ': ' + item['message'], flush=True)
                if run['status'] != 'running':
                    break
                time.sleep(2)
            events = client.app.state.repository.events(rid)
            stream = client.get('/api/searches/' + rid + '/events')
            exported = client.get('/api/searches/' + rid + '/export')
            counts = Counter(item['type'] for item in events)
            result = run.get('result') or {}
            passed = (run['status'] == 'complete' and counts['search_results'] > 0 and
                      counts['extraction_ready'] > 0 and counts['research_completed'] > 0 and
                      bool(result.get('jobs') or result.get('unknowns')) and
                      'event: done' in stream.text and exported.status_code == 200)
            report = {'verified_at': stamp, 'passed': passed, 'limits': {'rounds': 1, 'candidates': args.candidates},
                      'event_counts': dict(counts), 'run': run, 'events': events,
                      'sse_replay_ok': 'event: done' in stream.text, 'export_status': exported.status_code}
            (output / 'report.json').write_text(json.dumps(report, indent=2))
            if exported.status_code == 200:
                (output / 'shortlist.md').write_text(exported.text)
            print(('PASS' if passed else 'INCOMPLETE') + ': ' + str(output), flush=True)
            print('Matches: %s; needs review: %s; excluded: %s' %
                  (len(result.get('jobs', [])), len(result.get('unknowns', [])), len(result.get('excluded', []))), flush=True)
            return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
