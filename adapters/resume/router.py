"""Select a document parser through its port; no cloud-provider imports."""
from .parser import validate_upload,LocalResumeParser


class RoutedResumeParser:
    def __init__(self, pdf=None):
        self.pdf = pdf
        self.local = LocalResumeParser()

    def parse(self, filename, content):
        suffix = validate_upload(filename, content)
        return (self.pdf if suffix == '.pdf' and self.pdf else self.local).parse(filename, content)
