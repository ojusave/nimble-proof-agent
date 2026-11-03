"""Conservative, offline location grounding. Never use employment history as home location."""
import re
import unicodedata
from functools import lru_cache

import geonamescache


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold()) if not unicodedata.combining(c))


@lru_cache(maxsize=1)
def geography():
    cache = geonamescache.GeonamesCache()
    # Retain names only, not coordinates, populations or personal addresses.
    cities = {normalized(c['name']): c['name'] for c in cache.get_cities().values() if len(c['name']) > 3}
    for noisy in ('reading', 'mobile', 'nice', 'orange', 'enterprise', 'remote', 'java'):
        cities.pop(noisy, None)
    countries = {normalized(c['name']): c['name'] for c in cache.get_countries().values()}
    countries.update({'usa': 'United States', 'united states of america': 'United States',
                      'uk': 'United Kingdom', 'uae': 'United Arab Emirates'})
    states = cache.get_us_states()
    return cities, countries, states


def location_in(text, explicit=False):
    cities, countries, states = geography()
    clean = re.sub(r'https?://\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', ' ', text)
    tokens = list(re.finditer(r"[\wÀ-ž]+(?:['’-][\wÀ-ž]+)*", clean))
    matches = []
    for size in range(5, 0, -1):
        for index in range(len(tokens) - size + 1):
            start, end = tokens[index].start(), tokens[index + size - 1].end()
            value = clean[start:end]
            key = normalized(value)
            if key in countries or key in cities:
                if any(start < m[1] and end > m[0] for m in matches): continue
                matches.append((start, end, value, 'country' if key in countries else 'city'))
    if re.search(r'\b(?:US|U\.S\.|USA)\b', clean):
        match = re.search(r'\b(?:US|U\.S\.|USA)\b', clean)
        matches.append((match.start(), match.end(), match.group(), 'country'))
    # Uppercase postal abbreviations only, so ordinary words such as "in" do not become Indiana.
    for match in re.finditer(r'\b[A-Z]{2}\b', clean):
        if match.group() in states:
            matches.append((match.start(), match.end(), match.group(), 'state'))
    for code, state in states.items():
        match = re.search(r'\b' + re.escape(state['name']) + r'\b', clean, re.I)
        if match: matches.append((match.start(), match.end(), match.group(), 'state'))
    if not matches: return None
    matches.sort()
    if not explicit and len({normalized(m[2]) for m in matches if m[3] == 'city'}) > 1: return None
    start, end = min(m[0] for m in matches), max(m[1] for m in matches)
    evidence = clean[start:end].strip(' ,|·')
    # Do not turn an entire paragraph, street address or work history into a location.
    if len(evidence) > 110 or re.search(r'\b(?:19|20)\d{2}\b', evidence): return None
    return {'text': evidence, 'evidence': evidence}


def resume_profile(text):
    lines = [re.sub(r'^[#>*\s]+', '', line).strip() for line in text.splitlines() if line.strip()]
    header = []
    for line in lines[:18]:
        if re.match(r'^(?:professional |work |employment |relevant )?(?:experience|history|education|projects|skills|certifications)\b', line, re.I): break
        header.append(line)
    # An explicit header label outranks an unlabeled city. Multiple alternatives remain unknown.
    for line in sorted(header, key=lambda s: not bool(re.match(r'^(?:current )?(?:location|based in|address)\s*[:—-]?', s, re.I))):
        if re.search(r'\b(?:19|20)\d{2}\b', line): continue
        for part in re.split(r'[|•·]|\s+[—–]\s+', line):
            if len(part.split()) > 12: continue
            found = location_in(part)
            if found:
                remainder=part.replace(found['evidence'],'').strip(' ,:—–-')
                labeled=bool(re.match(r'^(?:current )?(?:location|based in|address)\b',part,re.I))
                if not labeled and remainder: continue
                if line==lines[0] and not labeled and ',' not in part: continue
                return {'location': {**found, 'source': 'resume'}}
    return {'location': None}


def resolve_location(profile, preferences):
    if re.search(r'\b(anywhere|worldwide|any location|no location preference)\b', preferences, re.I):
        return {'text': 'Anywhere', 'source': 'preferences', 'evidence': ''}
    explicit = location_in(preferences, explicit=True)
    if explicit: return {**explicit, 'source': 'preferences'}
    return profile.get('location')
