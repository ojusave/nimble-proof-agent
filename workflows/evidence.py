"""Select verbatim passages across a bounded document, retaining source offsets."""
import re

MAX_SCAN = 120000
GROUPS = (
    ('remote', 'hybrid', 'onsite', 'location', 'based', 'united states', 'country'),
    ('salary', 'compensation', 'pay range', 'per year', 'usd', '$'),
    ('apply', 'application', 'hiring', 'closed', 'filled', 'no longer available'),
    ('requirements', 'qualifications', 'experience', 'responsibilities', 'skills'),
)
STOP = {'with', 'that', 'this', 'from', 'your', 'have', 'will', 'the', 'and', 'for', 'are'}


def passages(text):
    bounded = text[:MAX_SCAN]
    start = 0
    while start < len(bounded):
        end = min(start + 650, len(bounded))
        if end < len(bounded):
            boundary = max(bounded.rfind('\n', start + 200, end),
                           bounded.rfind('. ', start + 200, end),
                           bounded.rfind(' ', start + 400, end))
            if boundary > start:
                end = boundary + 1
        raw = bounded[start:end]
        left = len(raw) - len(raw.lstrip())
        value = raw.strip()
        if value:
            yield {'id': 'P' + str(start + left), 'start': start + left,
                   'end': start + left + len(value), 'text': value}
        start = end


def select_passages(text, query, budget):
    candidates = list(passages(text))
    terms = {word.lower() for word in re.findall(r'[\w+#.-]{3,}', query) if word.lower() not in STOP}

    def score(item):
        lower = item['text'].lower()
        matches = sum(bool(re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', lower)) for term in terms)
        categories = sum(any(term in lower for term in group) for group in GROUPS)
        navigation = len(re.findall(r'\]\(https?://', lower))
        return matches * 3 + categories * 2 - navigation

    selected, used = [], 0
    # Retain the opening for identity, then rank passages from the entire scan.
    ranked = candidates[:1] + sorted(candidates[1:], key=lambda item: (-score(item), item['start']))
    for item in ranked:
        available = budget - used - (2 if selected else 0)
        if available < 80:
            break
        take = item['text'][:available]
        selected.append({**item, 'text': take, 'end': item['start'] + len(take)})
        used += len(take) + (2 if len(selected) > 1 else 0)
    selected.sort(key=lambda item: item['start'])
    # Merge adjacent slices so a real quotation across a chunk boundary still
    # validates. Never join nonadjacent passages into fabricated evidence.
    merged = []
    for item in selected:
        if merged and item['start'] - merged[-1]['end'] <= 2:
            previous = merged[-1]
            previous['end'] = item['end']
            previous['text'] = text[previous['start']:item['end']]
        else:
            merged.append(dict(item))
    return merged


def evidence_summary(text, selected):
    return {'source_characters': len(text), 'scanned_characters': min(len(text), MAX_SCAN),
            'selected_characters': sum(len(item['text']) for item in selected),
            'scan_limited': len(text) > MAX_SCAN, 'passages': selected}
