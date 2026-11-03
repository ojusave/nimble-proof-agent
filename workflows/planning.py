"""Deterministic query planning: no hosted research call for routine string work."""
import re

from core.text import SKILLS

ROLES = ('developer advocate', 'developer relations', 'developer experience engineer',
         'software engineer', 'software developer', 'data engineer', 'data scientist',
         'product manager', 'product designer', 'technical writer', 'technical educator')


def plan_search(profile, preferences, round_number, previous=None, location=None):
    """Preserve every explicit preference; only discovery queries change on retry."""
    text = (preferences + '\n' + profile).lower()
    if re.search(r'\bdevrel\b',text): text += ' developer relations'
    roles = [role for role in ROLES if role in text]
    skills = [skill for skill in SKILLS
              if re.search(r'(?<!\w)' + re.escape(skill) + r'(?!\w)', text)][:6]
    requirements = [{'id': 'R' + str(index + 1), 'text': part}
                    for index, part in enumerate(dict.fromkeys(
                        part.strip() for part in re.split(r'[,;\n]+', preferences) if part.strip()))]
    if previous:
        requirements = previous['requirements']
    elif location and location.get('source') == 'resume':
        requirements.append({'id':'R'+str(len(requirements)+1),
                             'text':'Work in or remotely from '+location['text']})
    # Only a professional vocabulary is inferred from the résumé; names and contact
    # details are not turned into search queries. Full preferences stay in checks.
    explicit_roles = [role for role in ROLES if role in preferences.lower()]
    target = explicit_roles[:1] or roles[:1]
    # Keep the role prominent. Stacking every programming language drowned it out.
    terms = ' '.join('"'+role+'"' for role in target)
    if not target: terms = ' '.join(skills[:2])
    if preferences.strip(): terms += ' ' + ' '.join(preferences.split())[:300]
    if location and location['text'] != 'Anywhere' and location.get('source') == 'resume':
        terms += ' ' + location['text']
    terms = terms or 'job openings'
    suffixes = (
        '(site:jobs.ashbyhq.com OR site:boards.greenhouse.io)',
        '(site:jobs.lever.co OR site:myworkdayjobs.com)',
    ) if round_number == 1 else ('careers apply job', 'hiring opening employer -inurl:jobs/q-')
    return {'roles': roles, 'skills': skills, 'requirements': requirements,
            'location':location,'queries': list(dict.fromkeys((terms + ' ' + suffix).strip() for suffix in suffixes))}
