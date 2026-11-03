"""Export the same evidence and uncertainty the browser displays."""
import json


def shortlist_markdown(result):
    lines = ['# Job shortlist', '',
             f"{len(result['jobs'])} of {result['requested']} requested matches.",
             'Mode: ' + result['mode'], '']
    if result.get('incomplete'):
        lines.extend(['Stopped early. These are partial results received before stopping.', ''])
    for label, jobs in [('Matches', result['jobs']), ('Needs review', result['unknowns'])]:
        if not jobs:
            continue
        lines.extend(['## ' + label, ''])
        for job in jobs:
            lines.extend([f"### {job['title']} — {job['company']}", job['url'], job['summary'],
                          'Checked: ' + job['checked_at'], ''])
            for strength in job['strengths']:
                lines.extend(['- ' + strength['reason'], '  - Résumé quote: ' + strength['resume_quote'],
                              '  - Listing quote: ' + strength['job_quote']])
            for check in job['checks']:
                lines.append('- Requirement: %s — %s. %s' % (check['requirement'], check['status'], check['evidence']))
            lines.extend('- Not confirmed: ' + item for item in job.get('unknown_requirements', []))
            lines.extend('- Gap: ' + gap for gap in job['gaps'])
            lines.append('- Application evidence: ' + (job.get('open_evidence') or 'Not confirmed'))
            research = job.get('research') or {}
            if research.get('run_id'):
                lines.extend(['', 'Research run: ' + research['run_id'],
                              'Provider-reported citations and confidence; separate from local quote checks:', '',
                              '````json', json.dumps(research.get('trust', {}), ensure_ascii=False, indent=2), '````'])
            lines.append('')
    if result['warnings']:
        lines.extend(['## Provider issues', ''] + ['- ' + warning for warning in result['warnings']] + [''])
    for label, unverified in [('Unverified sources',True),('Not included',False)]:
        items=[item for item in result.get('excluded',[]) if
               (item.get('category') in ('provider_error','unverified'))==unverified]
        if items:
            lines.extend(['## '+label,''])
            for item in items:
                lines.extend(['- '+item['title']+' — '+item['reason'],'  '+item['url']])
            lines.append('')
    if result['next_question']:
        lines.append(result['next_question'])
    return '\n'.join(lines)
