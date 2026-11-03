import unittest
from workflows.application_links import application_link


class ApplicationLinkTests(unittest.TestCase):
    listing='https://careers.example.com/jobs/123'
    employer='https://example.com'

    def test_relative_link_preserves_required_parameters_and_anchor(self):
        result=application_link('[Apply now](/jobs/123/apply?source=listing#application)',self.listing,self.employer)
        self.assertEqual(result,{'url':'https://careers.example.com/jobs/123/apply?source=listing#application','source':'listing_link'})

    def test_captured_ats_form_and_html_links_are_supported(self):
        result=application_link('<a href="https://jobs.lever.co/example/123/apply">Apply for this job</a>',self.listing,self.employer)
        self.assertEqual(result['url'],'https://jobs.lever.co/example/123/apply')

    def test_untrusted_or_unrelated_links_fall_back_to_original_listing(self):
        for target in ['javascript:alert(1)','https://evil.example.net/apply','https://127.0.0.1/apply','https://example.com@evil.example.net/apply','https://linkedin.com/jobs/123']:
            self.assertEqual(application_link('[Apply]('+target+')',self.listing,self.employer),{'url':self.listing,'source':'job_page'})
        self.assertEqual(application_link('[Application tips](https://example.com/help)',self.listing,self.employer)['source'],'job_page')

    def test_plain_application_instructions_do_not_invent_a_form_url(self):
        self.assertEqual(application_link('Apply for this job using our application form.',self.listing,self.employer)['url'],self.listing)
