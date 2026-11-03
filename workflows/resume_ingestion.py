"""Parsing and profile nodes, independent of provider and graph libraries."""
from workflows.resume_profile import resume_profile


class ResumeIngestion:
    def __init__(self, parser):
        self.parser = parser

    def parse(self, state):
        return {'parsed': self.parser.parse(state['filename'], state['content'])}

    def profile(self, state):
        return {'profile': resume_profile(state['parsed']['text'])}
