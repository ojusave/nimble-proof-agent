import re

def professional_text(text: str) -> str:
    """Remove obvious email/phone contact strings before provider requests."""
    text = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[email removed]', text)
    return re.sub(r'\+?\d[\d ().-]{7,}\d', lambda m: '[phone removed]' if len(re.sub(r'\D','',m.group())) >= 10 else m.group(), text)


# Conservative professional vocabulary for local evidence pairing. Expand per workflow/domain.
SKILLS = ('python','javascript','typescript','java','golang','rust','sql','postgresql',
          'react','node.js','fastapi','django','kubernetes','docker','aws','azure',
          'graphql','rest','api','apis','sdk','sdks','documentation','tutorials',
          'workshops','public speaking','machine learning','data engineering')


def shared_skill_evidence(job_quote,resume):
    """Return an exact résumé line only when a named skill occurs in both texts."""
    for line in resume.splitlines():
        line=line.strip()
        if len(line)<8: continue
        for skill in SKILLS:
            pattern=r'(?<!\w)'+re.escape(skill)+r'(?!\w)'
            if re.search(pattern,job_quote,re.I) and re.search(pattern,line,re.I):
                return {'reason':'Shared skill: '+skill,'resume_quote':line,'job_quote':job_quote}
    return None
