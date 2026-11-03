"""Keep application links grounded in the captured employer listing, not model guesses."""
from html import unescape
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit, urlunsplit
from core.urls import public_url, employer_host


class _Links(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.href=None;self.label=[]
    def handle_starttag(self, tag, attrs):
        if tag=='a': self.href=dict(attrs).get('href');self.label=[]
    def handle_data(self, data):
        if self.href is not None:self.label.append(data)
    def handle_endtag(self, tag):
        if tag=='a' and self.href is not None:
            self.links.append((' '.join(self.label),self.href));self.href=None


def application_link(text, listing_url, employer_url):
    captured=text[:120000]
    links=re.findall(r'\[([^\]\n]{1,160})\]\(\s*<?([^\s)>]+)>?(?:\s+"[^"]*")?\s*\)',captured)
    parser=_Links();parser.feed(captured);links+=parser.links
    for label, href in links:
        if not re.search(r'\b(apply(?:\s+(?:now|here|for (?:this|the) (?:job|role|position)))?|(?:start|submit|begin) (?:your |an? )?application|application form)\b',label,re.I):continue
        if re.search(r'\b(do not|don.t|how to|tips|guide|help|withdraw|status)\b',label,re.I):continue
        target=urljoin(listing_url,unescape(href))
        try:
            public_url(target)
            if not employer_host(target,employer_url):continue
        except (TypeError,ValueError):continue
        # Preserve application parameters and fragments: ATS forms can require them.
        parsed=urlsplit(target)
        return {'url':urlunsplit(parsed),'source':'listing_link'}
    return {'url':listing_url,'source':'job_page'}
