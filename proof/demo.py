"""Synthetic fixtures, not a recorded live API run. No network or keys required."""
QUESTION = 'Compare scheduled exports and private networking in the fictional Atlas and Beacon platforms.'
PAGES = {
    'https://atlas.example.com/docs/exports': 'Atlas example documentation. Scheduled CSV exports run every day. Private networking is available on the Enterprise plan.',
    'https://beacon.example.com/docs/exports': 'Beacon example documentation. Scheduled CSV exports run every week. Private networking is not currently available.'
}


class DemoWeb:
    def search(self, query):
        return [{'url': url, 'title': url.split('//')[1].split('.')[0].title() + ' — synthetic documentation',
                 'description': 'Fictional documentation for the offline demo.'} for url in PAGES]

    def extract(self, url):
        return PAGES[url]


class DemoModel:
    def __init__(self):
        self.turn = 0

    def next(self, messages, tools, system, first):
        self.turn += 1
        if self.turn == 1:
            calls = [('search_web', {'query': 'Atlas Beacon scheduled exports private networking'})]
        elif self.turn == 2:
            calls = [('read_source', {'source_id': 'S1'}), ('read_source', {'source_id': 'S2'})]
        else:
            calls = [('finish_brief', {
                'title': 'Atlas vs Beacon',
                'summary': 'In this synthetic scenario, Atlas exports daily and offers private networking on Enterprise; Beacon exports weekly and does not offer private networking.',
                'findings': [
                    {'claim': 'Atlas supports daily CSV exports.', 'source_id': 'S1', 'quote': 'Scheduled CSV exports run every day.'},
                    {'claim': 'Atlas limits private networking to Enterprise.', 'source_id': 'S1', 'quote': 'Private networking is available on the Enterprise plan.'},
                    {'claim': 'Beacon supports weekly CSV exports.', 'source_id': 'S2', 'quote': 'Scheduled CSV exports run every week.'},
                    {'claim': 'Beacon does not currently offer private networking.', 'source_id': 'S2', 'quote': 'Private networking is not currently available.'}],
                'gaps': ['Fictional demo data; no live API calls.',
                         'Scripted demo; live model reasoning has not been tested.']})]
        return [{'type': 'tool_use', 'id': 'demo_%s_%s' % (self.turn, index), 'name': name, 'input': args}
                for index, (name, args) in enumerate(calls)]
