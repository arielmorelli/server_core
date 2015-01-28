# encoding: utf-8
import os
from nose.tools import (
    set_trace, eq_,
    assert_raises,
)
import datetime
import json

from . import DatabaseTest
from nyt import (
    NYTBestSellerAPI,
)
from model import (
    Contributor,
    Edition,
    Identifier,
)

class DummyNYTBestSellerAPI(NYTBestSellerAPI):

    def sample_json(self, filename):
        base_path = os.path.split(__file__)[0]
        resource_path = os.path.join(base_path, "files", "nyt")
        path = os.path.join(resource_path, filename)
        data = open(path).read()
        return json.loads(data)

    def list_of_lists(self):
        return self.sample_json("bestseller_list_list.json")

    def best_seller_list(self, list_name):
        return self._make_list(self.sample_json("list_%s.json" % list_name))

class TestNYTBestSellerAPI(DatabaseTest):
    
    def setup(self):
        super(TestNYTBestSellerAPI, self).setup()
        self.api = DummyNYTBestSellerAPI(self._db)

    def test_list_of_lists(self):

        all_lists = self.api.list_of_lists()
        eq_([u'copyright', u'num_results', u'results', u'status'],
            sorted(all_lists.keys()))
        eq_(47, len(all_lists['results']))

    def test_best_seller_list(self):
        
        l = self.api.best_seller_list("combined-print-and-e-book-fiction")
        
