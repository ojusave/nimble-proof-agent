"""Provider-neutral records shared by workflows, storage, and UI."""
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class SearchRequest:
    resume_id: str
    query: str = ''
    count: int = 5
    max_rounds: int = 2
    demo: bool = False

    def validate(self):
        if type(self.count) is not int or not 1 <= self.count <= 20:
            raise ValueError('Choose 1–20 jobs.')
        if not isinstance(self.query, str) or len(self.query) > 1500:
            raise ValueError('Keep preferences under 1,500 characters.')
        if not 1 <= self.max_rounds <= 3:
            raise ValueError('Search rounds must be between 1 and 3.')


@dataclass
class Job:
    id: str
    title: str
    company: str
    url: str
    location: str = ''
    fit: str = 'possible'
    checks: list[dict] = field(default_factory=list)
    strengths: list[dict] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    summary: str = ''
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    provisional: bool = True

    def to_dict(self):
        return asdict(self)


def event(kind: str, step: str, message: str, **data: Any):
    return {'id': uuid4().hex, 'type': kind, 'step': step, 'message': message,
            'data': data, 'at': datetime.now(timezone.utc).isoformat()}
