import os
import unittest
import tempfile
import urllib.parse
import json

import server as GovReadyKBServer

class FlaskTestCase(unittest.TestCase):

    # based on http://flask.pocoo.org/docs/0.10/testing/
    def setUp(self):
        # Get a temporary path for the database.
        self.db_fd, db_fn = tempfile.mkstemp()
        GovReadyKBServer.app.config['DATABASE'] = db_fn
        self.app = GovReadyKBServer.app.test_client()
        GovReadyKBServer.create_db_tables(GovReadyKBServer.get_access_log())
    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(GovReadyKBServer.app.config['DATABASE'])

class GovReadyKBTests(FlaskTestCase):

    # Helper method to issue a query to the /api/search endpoint.
    def run_query(self, q):
        return json.loads(self.app.get('/api/search?q=' + urllib.parse.quote(q)).data.decode("utf8"))

    def get_resource_result(self, response, id):
        # Asserts that a resource with the given ID is present in
        # the results, and returns it.
        res = [r for r in response["results"] if r["resource"]["id"] == id]
        self.assertNotEqual(len(res), 0, msg="resource %s not in results" % id)
        return res[0]

    def test_document_by_id(self):
        # "nist-800-39" should match nist-800-39.
        rv = self.run_query("nist-800-39")
        r = self.get_resource_result(rv, "nist-800-39")
        self.assertEqual(r["resource"].get("url"), 'https://www.documentcloud.org/documents/2764682-SP800-39-Final.html')
        self.assertIn("thumbnail", r)
        self.assertIn("context", r)

    def test_document_by_title(self):
        # "Managing Information Security Risk" should match nist-800-39.
        rv = self.run_query("NIST Special Publication 800-39")
        self.get_resource_result(rv, "nist-800-39")

    def test_document_by_alt_title(self):
        # "Managing Information Security Risk" should match nist-800-39.
        rv = self.run_query("Managing Information Security Risk")
        self.get_resource_result(rv, "nist-800-39")

    def test_isso(self):
        # "isso" should match nist-800-39.
        rv = self.run_query("isso")
        r = self.get_resource_result(rv, "nist-800-39")
        self.assertIn("Information System Security Officer", r["context"][0]["html"])

    def test_information_system_security_officer(self):
        # "Information System Security Officer" should match nist-800-39 and 18f-policy-AC
        # because it has a term defined by ISSO elsewhere.
        rv = self.run_query("isso")
        
        r = self.get_resource_result(rv, "nist-800-39")
        self.assertIn("Information System Security Officer", r["context"][0]["html"])

        r = self.get_resource_result(rv, "18f-policy-AC")
        self.assertIn("term is defined by term “Information System Security Officer” in NIST SP 800-39", r["context"][0]["html"])


    def test_separation_of_duties(self):
        # "separation of duties" should match 18f-policy-AC and the context
        # of the match should draw text from the actual document text.
        rv = self.run_query("separation of duties")
        r = self.get_resource_result(rv, "18f-policy-AC")
        self.assertIn("Separates [Assignment: organization-defined duties of individuals];", r["context"][0]["html"])

if __name__ == '__main__':
    unittest.main()