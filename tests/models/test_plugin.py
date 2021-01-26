# encoding: utf-8
from .. import DatabaseTest
from ...model import (create)

import unittest
from mock import MagicMock
from nose.tools import assert_raises

from ...model.plugin import Plugin
from ...model.library import Library

# Varibles for test cases
LIB_ID = 1

class TestPluginGetValues(DatabaseTest):
    def test_plugin_get_saved_values_lib_not_valid(self):
        class MockPlugin(Plugin):
            def __init__(self, *args, **kwargs):
                pass

            def _get_library_from_short_name(self, library_short_name):
                return Library(id=LIB_ID, short_name="T1")

        mocked_plugin = MockPlugin()
        assert_raises(Exception, mocked_plugin.get_saved_values, "a lib", "a plugin")

    def test_plugin_get_saved_values_error_querying_db(self):
        class MockPlugin(Plugin):
            def __init__(self, *args, **kwargs):
                pass

            def _get_saved_values(*args, **kwargs):
                raise Exception

            def _get_library_from_short_name(self, library_short_name):
                return Library(id=LIB_ID, short_name="T1")

        mocked_plugin = MockPlugin()
        assert_raises(Exception, mocked_plugin.get_saved_values, "a lib", "a plugin")


class TestPluginSaveValues(DatabaseTest):
    class MockPlugin(Plugin):
        def __init__(self, *args, **kwargs):
            pass

    def test_library_not_found(self):
        plugin = Plugin()
        assert_raises(Exception, plugin.save_values, "library", "plugin", {})

    def test_insert_value_db_empty(self):
        library, ignore = create(
            self._db, Library, id=LIB_ID, name="Lib", short_name="L1"
        )
        
        plugin_name = "plugin"
        key = "key-to-test"
        val = "value to test"
        data = {key: val}

        plugin = Plugin()
        plugin._perform_db_operations = MagicMock()
        plugin.save_values(self._db, library.short_name, plugin_name, data)

        plugin._perform_db_operations.assert_called_with(self._db,
                                                         [{
                                                             "lib_id": LIB_ID,
                                                             "key": plugin_name + "." + key,
                                                             "value": val
                                                          }],
                                                          [],
                                                          [],
                                                         )

    def test_insert_value_with_another_data_existing_in_db(self):
        library, ignore = create(
            self._db, Library, id=LIB_ID, name="Lib", short_name="L1"
        )
        
        pname = "plugin"
        new_key = "key-to-test"
        new_val = "value to test"
        key_to_keep = "key-to-keep"
        val_to_keep = "val to keep"

        data = {new_key: new_val, key_to_keep: val_to_keep}

        _, _ = create(
            self._db, Plugin, id=1, library_id=library.id, key=pname+"."+key_to_keep,
            _value=val_to_keep
        )

        plugin = Plugin()
        plugin._perform_db_operations = MagicMock()
        plugin.save_values(self._db, library.short_name, pname, data)

        plugin._perform_db_operations.assert_called_with(self._db,
                                                         [{
                                                             "lib_id": LIB_ID,
                                                             "key": pname + "." + new_key,
                                                             "value": new_val
                                                         }],
                                                         [],
                                                         [] )
    def test_update_value(self):
        library, ignore = create(
            self._db, Library, id=LIB_ID, name="Lib", short_name="L1"
        )
        
        pname = "plugin"
        key_to_update = "key-to-keep"
        new_val = "val to keep"
        
        data = {key_to_update: new_val}

        plugin_instance, _ = create(
            self._db, Plugin, id=1, library_id=library.id, key=pname+"."+key_to_update,
            _value=new_val+" old"
        )

        plugin = Plugin()
        plugin._perform_db_operations = MagicMock()
        plugin.save_values(self._db, library.short_name, pname, data)

        call_args = plugin._perform_db_operations.call_args
        _, to_insert, to_update, to_delete = call_args.args

        assert to_insert == []
        assert to_update[0][0].id == plugin_instance.id
        assert to_update[0][0].key == plugin_instance.key
        assert to_update[0][1] == new_val
        assert to_delete == []

    def test_delete_value(self):
        library, ignore = create(
            self._db, Library, id=LIB_ID, name="Lib", short_name="L1"
        )
        
        pname = "plugin"
        key_to_delete = "key-to-keep"
        val_to_delete = "val to keep"
        
        data = {}

        plugin_instance, _ = create(
            self._db, Plugin, id=1, library_id=library.id, key=pname+"."+key_to_delete,
            _value=val_to_delete
        )

        plugin = Plugin()
        plugin._perform_db_operations = MagicMock()
        plugin.save_values(self._db, library.short_name, pname, data)

        call_args = plugin._perform_db_operations.call_args
        _, to_insert, to_update, to_delete = call_args.args

        assert to_insert == []
        assert to_update == []
        assert to_delete[0].id == plugin_instance.id
        assert to_delete[0].key == plugin_instance.key

class TestPluginGetSavedValues(DatabaseTest):
    def test_plugin_empty_values(self):
        library, ignore = create(
            self._db, Library, id=LIB_ID, name="Lib", short_name="L1"
        )
        plugin = Plugin()
        saved_values = plugin._get_saved_values(self._db, library, "any_plugin")
        assert saved_values == {}

    def test_plugin_find_values(self):
        pname = "plugin_name"
        key1 = "key1"
        value1 = "value1"
        key2 = "key2"
        value2 = "value2"

        library, ignore = create(
            self._db, Library, id=LIB_ID, name="Lib", short_name="L1"
        )

        plugin1, ignore = create(
            self._db, Plugin, id=1, library_id=library.id, key=pname+"."+key1, _value=value1
        )
        plugin2, ignore = create(
            self._db, Plugin, id=2, library_id=library.id, key=pname+"."+key2, _value=value2
        )
        
        plugin = Plugin()
        saved_values = plugin._get_saved_values(self._db, library, pname)
        assert key1 in saved_values
        assert saved_values[key1]._value == value1
        assert key2 in saved_values
        assert saved_values[key2]._value == value2


class TestPluginFromShortName(DatabaseTest):
    def test_plugin_find_library(self):
        name = "Test Library Name"
        short_name = "T1"
        inserted_library, ignore = create(
            self._db, Library, id=LIB_ID, name=name, short_name=short_name
        )

        plugin = Plugin()
        library = plugin._get_library_from_short_name(self._db, short_name)
        assert library.name == inserted_library.name 
        assert library.id == inserted_library.id
        assert library.short_name == inserted_library.short_name

    def test_plugin_dont_find_library(self):
        plugin = Plugin()
        assert_raises(Exception, plugin._get_library_from_short_name, self._db, "any_name")

