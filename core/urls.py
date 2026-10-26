import ipaddress
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

AGGREGATORS = {'linkedin.com','indeed.com','glassdoor.com','ziprecruiter.com','jooble.org','simplyhired.com','talent.com','remoteok.com','wellfound.com','builtin.com'}
ATS = {'greenhouse.io','greenhouse.com','lever.co','ashbyhq.com','workdayjobs.com','myworkdayjobs.com','smartrecruiters.com','workable.com','jobvite.com','icims.com','bamboohr.com','recruitee.com','applytojob.com','teamtailor.com'}


def host(url):
    return (urlsplit(url).hostname or '').lower().removeprefix('www.')


def belongs(domain, roots):
    return any(domain == root or domain.endswith('.' + root) for root in roots)


def public_url(value):
    if not isinstance(value, str):
        raise ValueError('Missing source URL.')
    parsed = urlsplit(value)
    domain = parsed.hostname or ''
    if parsed.scheme != 'https' or not domain or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError('A public HTTPS URL is required.')
    try:
        ip = ipaddress.ip_address(domain)
    except ValueError:
        ip = None
    if (ip is not None and not ip.is_global) or '.' not in domain or domain.endswith(('.local','.internal','.localhost')):
        raise ValueError('Local addresses are not sources.')
    query = [(k,v) for k,v in parse_qsl(parsed.query) if not k.lower().startswith('utm_') and k not in ('gh_src','source','ref')]
    return urlunsplit(('https',parsed.netloc.lower(),parsed.path.rstrip('/') or '/',urlencode(query),''))


def employer_host(listing_url, employer_url):
    domain = host(listing_url)
    if belongs(domain, AGGREGATORS):
        return False
    if belongs(domain, ATS):
        return True
    employer = host(employer_url)
    return bool(employer and not belongs(employer, AGGREGATORS | ATS) and
                (domain == employer or domain.endswith('.'+employer)))
