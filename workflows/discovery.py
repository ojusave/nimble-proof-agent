"""Follow captured career-page links, never model-invented job URLs."""
import hashlib
import re
from urllib.parse import urljoin,urlsplit
from core.urls import public_url,host,belongs,ATS,AGGREGATORS


def is_index(url, text=''):
    path=urlsplit(url).path.rstrip('/')
    return bool(re.search(r'^#{1,2}\s+(?:Current openings|Open positions|All jobs)\b',text,re.I|re.M) or
                re.search(r'/jobs/(?:q-|dev-engineering/)',path) or
                re.fullmatch(r'/(?:remote-jobs|jobs)/(?:typescript|javascript|python)',path))


def linked_openings(text, source, roles):
    found={}
    for title,target in re.findall(r'\[([^\]\n]{3,200})\]\(([^\s)]+)\)',text):
        try: url=public_url(urljoin(source,target))
        except ValueError: continue
        path=urlsplit(url).path
        if url==source or belongs(host(url),AGGREGATORS) or is_index(url): continue
        if not (belongs(host(url),ATS) or host(url)==host(source)): continue
        if not re.search(r'/(?:jobs?|careers|positions?|openings?)/[^/]+|/[0-9a-f]{8}-[0-9a-f-]{27,}',path,re.I): continue
        words={word for role in roles for word in role.lower().split() if len(word)>3}
        score=sum(word in title.lower() for word in words)
        if words and not score: continue
        found[url]={'id':hashlib.sha256(url.encode()).hexdigest()[:16],'url':url,'title':title,
                    'snippet':'Discovered on '+source,'parent_url':source,'score':score}
    return sorted(found.values(),key=lambda item:-item['score'])
