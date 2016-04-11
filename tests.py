import os
import unittest
import tempfile

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

if __name__ == '__main__':
    unittest.main()