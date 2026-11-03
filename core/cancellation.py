"""Cooperative local cancellation shared by the runner and provider adapters."""
from threading import Event


class SearchCancelled(Exception):
    pass


class CancellationToken:
    def __init__(self):
        self.signal = Event()

    def cancel(self):
        self.signal.set()

    def is_cancelled(self):
        return self.signal.is_set()

    def check(self):
        if self.is_cancelled():
            raise SearchCancelled('Search stopped by you.')

    def wait(self, seconds):
        self.signal.wait(seconds)
        self.check()


def stopped_result(request, events):
    """Keep only evidence already emitted before the stop request."""
    matches, review, excluded, requirements, rounds = {}, {}, [], [], 0
    for item in events:
        data = item.get('data', {})
        if item['type'] == 'job_matched': matches[data['job']['id']] = data['job']
        if item['type'] == 'job_unknown': review[data['job']['id']] = data['job']
        if item['type'] == 'job_excluded': excluded.append(data)
        if item['type'] == 'plan_ready':
            requirements = data.get('requirements', [])
            rounds = max(rounds, data.get('round', 1))
    jobs = list(matches.values())[:request.count]
    return {'kind': 'job_search', 'incomplete': True, 'jobs': jobs, 'unknowns': list(review.values()),
            'excluded': excluded, 'requirements': requirements, 'rounds': rounds, 'warnings': [],
            'requested': request.count, 'shortfall': max(0, request.count - len(jobs)), 'next_question': None,
            'mode': 'synthetic demo' if request.demo else 'live'}
