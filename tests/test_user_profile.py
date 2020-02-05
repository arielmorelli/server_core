from nose.tools import (
    eq_,
    set_trace
)
import json
from ..user_profile import (
    ProfileController,
    MockProfileStorage,
)

class TestProfileController(object):

    def setup(self):
        self.read_only_settings = dict(key="value")
        self.writable_settings = dict(writable_key="old_value")
        self.storage = MockProfileStorage(self.read_only_settings, self.writable_settings)
        self.controller = ProfileController(self.storage)

    def test_profile_document(self):
        """Test that the default setup becomes a dictionary ready for
        conversion to JSON.
        """
        eq_({'key': 'value', 'settings': {'writable_key': 'old_value'}},
            self.storage.profile_document)

    def test_get_success(self):
        """Test that sending a GET request to the controller results in the
        expected profile_document.
        """
        body, status_code, headers = self.controller.get()
        eq_(200, status_code)
        eq_(ProfileController.MEDIA_TYPE, headers['Content-Type'])
        eq_(json.dumps(self.storage.profile_document), body)

    def test_put_success(self):
        """Test that sending a new dictionary of key-value pairs
        leads to changes in the writable part of the store, but not in
        the read-only part.
        """
        headers = {"Content-Type" : ProfileController.MEDIA_TYPE}
        expected_new_state = dict(writable_key="new value")
        old_read_only = dict(self.storage.read_only_settings)
        body = json.dumps(dict(settings=expected_new_state))
        body, status_code, headers = self.controller.put(headers, body)
        eq_(200, status_code)
        eq_(expected_new_state, self.storage.writable_settings)
        eq_(old_read_only, self.storage.read_only_settings)

    def test_put_noop(self):
        """Test that sending an empty dictionary of key-value pairs
        succeeds but does nothing.
        """
        headers = {"Content-Type" : ProfileController.MEDIA_TYPE}
        expected_new_state = dict(self.storage.writable_settings)
        body, status_code, headers = self.controller.put(
            headers, json.dumps({})
        )
        eq_(200, status_code)
        eq_(expected_new_state, self.storage.writable_settings)

    def test_get_exception_during_profile_document(self):
        """Test what happens if an exception is raised during the
        creation of a profile_document.
        """

        class BadStorage(MockProfileStorage):
            @property
            def profile_document(self):
                raise Exception("Oh no")

        self.controller.storage = BadStorage()
        problem = self.controller.get()
        eq_(500, problem.status_code)
        eq_("Oh no", problem.debug_message)

    def test_get_non_dictionary_profile_document(self):
        """Test what happens if the profile_document is not a dictionary.
        """

        class BadStorage(MockProfileStorage):
            @property
            def profile_document(self):
                return "Here it is!"

        self.controller.storage = BadStorage()
        problem = self.controller.get()
        eq_(500, problem.status_code)
        eq_("Profile profile_document is not a JSON object: u'Here it is!'.",
            problem.debug_message)

    def test_get_non_dictionary_profile_document(self):
        """Test what happens if the profile_document cannot be converted to JSON.
        """

        class BadStorage(MockProfileStorage):
            @property
            def profile_document(self):
                return dict(key=object())

        self.controller.storage = BadStorage()
        problem = self.controller.get()
        eq_(500, problem.status_code)
        assert problem.debug_message.startswith(
            "Could not convert profile document to JSON: {'key': <object object"
        )

    def test_put_bad_media_type(self):
        """You must send the proper media type with your PUT request."""
        headers = {"Content-Type" : "application/json"}
        body = json.dumps(dict(settings={}))
        problem = self.controller.put(headers, body)
        eq_(415, problem.status_code)
        eq_('Expected vnd.librarysimplified/user-profile+json',
            problem.detail)

    def test_put_invalid_json(self):
        """You can't send any random string that's not JSON."""
        headers = {"Content-Type" : ProfileController.MEDIA_TYPE}
        problem = self.controller.put(headers, "blah blah")
        eq_(400, problem.status_code)
        eq_("Submitted profile document was not valid JSON.", problem.detail)

    def test_put_non_object(self):
        """You can't send any random JSON string, it has to be an object."""
        headers = {"Content-Type" : ProfileController.MEDIA_TYPE}
        problem = self.controller.put(headers, json.dumps("blah blah"))
        eq_(400, problem.status_code)
        eq_('Submitted profile document was not a JSON object.',
            problem.detail)

    def test_attempt_to_set_read_only_setting(self):
        """You can't change the value of a setting that's not
        writable.
        """
        headers = {"Content-Type" : ProfileController.MEDIA_TYPE}
        body = json.dumps(dict(settings=dict(key="new value")))
        problem = self.controller.put(headers, body)
        eq_(400, problem.status_code)
        eq_('"key" is not a writable setting.', problem.detail)

    def test_update_raises_exception(self):

        class BadStorage(MockProfileStorage):
            def update(self, settable, full):
                raise Exception("Oh no")
        self.controller.storage = BadStorage(self.read_only_settings, self.writable_settings)
        headers = {"Content-Type" : ProfileController.MEDIA_TYPE}
        body = json.dumps(dict(settings=dict(writable_key="new value")))
        problem = self.controller.put(headers, body)
        eq_(500, problem.status_code)
        eq_("Oh no", problem.debug_message)
