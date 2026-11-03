"""Deterministic query planning: no hosted research call for routine string work."""
import re

from core.text import SKILLS

ROLES = ('developer advocate', 'developer relations', 'developer experience engineer',
         'software engineer', 'software developer', 'data engineer', 'data scientist',
         'product manager', 'product designer', 'technical writer', 'technical educator')


def plan_search(profile, preferences, round_number, previous=None):
    """Preserve every explicit preference; only discovery queries change on retry."""
    text = (preferences + '\n' + profile).lower()
    roles = [role for role in ROLES if role in text]
    skills = [skill for skill in SKILLS
              if re.search(r'(?<!\w)' + re.escape(skill) + r'(?!\w)', text)][:6]
    requirements = [{'id': 'R' + str(index + 1), 'text': part}
                    for index, part in enumerate(dict.fromkeys(
                        part.strip() for part in re.split(r'[,;\n]+', preferences) if part.strip()))]
    if previous:
        requirements = previous['requirements']
    # Only a professional vocabulary is inferred from the résumé; names and contact
    # details are not turned into search queries. Full preferences stay in checks.
    terms = ' '.join(preferences.split())[:300] if preferences.strip() else ' '.join((roles[:1] + skills[:3]))
    terms = terms or 'job openings'
    suffixes = ('careers apply', 'job opening employer') if round_number == 1 else (
        '(site:jobs.ashbyhq.com OR site:boards.greenhouse.io)',
        '(site:jobs.lever.co OR site:myworkdayjobs.com)',
    )
    return {'roles': roles, 'skills': skills, 'requirements': requirements,
            'queries': [(terms + ' ' + suffix).strip() for suffix in suffixes]}
