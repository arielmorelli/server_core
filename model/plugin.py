from configuration import ConfigurationSetting
from library import Library
from . import get_one


class Plugin(ConfigurationSetting):
    """ Plugin is a ConfigurationSetting with specific behavior. """

    def get_saved_values(self, _db, library_short_name, plugin_name):
        """ Get saved values from a plugin.
        
        Args:
            _db (object): a db instace
            library_short_name (str): library short name.
            plugin_name (str): plugin name.

        Returns:
            dict: dict representing the plugin config.

        """
        try:
            library = self._get_library_from_short_name(_db, library_short_name)
        except Exception as ex:
            logging.warning("Cannot find library. Ex: %s", ex)
            raise Exception("Cannot find library")

        try:
            return self._get_saved_values(_db, library, plugin_name)
        except Exception as ex:
            raise Exception("Something went wrong while quering saved plugin values.")

    def save_values(self, _db, library_short_name, plugin_name, new_values):
        """ Save values of a plugin.
        
        Args:
            _db (object): a db instace
            library_short_name (str): library short name.
            plugin_name (str): plugin name.
            new_values (dict): key/value pair to save in DB

        """
        try:
            library = self._get_library_from_short_name(_db, library_short_name)
        except Exception as ex:
            logging.warning("Cannot find library. Ex: %s", ex)
            raise Exception("Cannot find the library")

        try:
            fields_from_db = self._get_saved_values(_db, library, plugin_name)
        except Exception as ex:
            logging.warning("Cannot get plugin saved values. Ex: %s", ex)
            raise

        to_insert = [] # Expect list of {"id": <id>, "key": <key>, "value": <value>}
        to_update = [] # Expect list of tuples: (<ConfigurationSetting instance>, <new_value>)
        to_delete = [] # Expect list of ConfigurationSetting instaces

        for key, value in new_values.items():
            if key == None:
                continue
            elif not fields_from_db.get(key) and value is not None:
                to_insert.append({ "lib_id": library.id, "key": plugin_name+"."+key, "value": value})
            elif fields_from_db.get(key) and value is None:
                to_delete.append(fields_from_db.get(key))
            elif ( fields_from_db.get(key) and
                  fields_from_db[key]._value != value ):
                fields_from_db[key]._value = value
                to_update.append( (fields_from_db[key], value) )

        no_longer_exist_keys = set(fields_from_db.keys()) - set(new_values.keys())
        to_delete = to_delete + [fields_from_db[key] for key in no_longer_exist_keys]

        try:
            self._perform_db_operations(_db, to_insert, to_update, to_delete)
        except Exception as ex:
            logging.error("Cannot save plugin values. Ex: %s", ex)
            raise

    def _get_saved_values(self, _db, library, plugin_name):
        """ Get raw values from a plugin without formating it
        
        Args:
            _db (object): a db instace
            library_short_name (str): library short name.
            plugin_name (str): plugin name.

        Returns:
            dict: key/value pair with plugin values

        """
        response = _db.query(ConfigurationSetting).filter(
            ConfigurationSetting.library_id == library.id,
            ConfigurationSetting.key.startswith(plugin_name)
        ).all()

        values = {}
        for entry in response:
            values[entry.key[len(plugin_name)+1:]] = entry
        return values

    def _get_library_from_short_name(self, _db, library_short_name):
        """ Get a library object by this short name
        
        Args:
            _db (object): a db instace
            library_short_name (str): library short name.

        Returns:
            Library: a library instace

        """
        library = get_one(
            _db, Library, short_name=library_short_name,
        )
        if not library:
            raise Exception("Library not found")
        return library

    def _perform_db_operations(self, _db, to_insert, to_update, to_delete):
        """ Execute insert, update and delete operations
        
        Args:
            _db (object): a db instace
            to_insert (list): items to be inserted in DB
            to_update (list): items to be updated in DB
            to_delete (list): items to be deleted in DB

        """
        if not to_insert and not to_update and not to_delete:
            return
        try:
            # Insert
            [_db.add(ConfigurationSetting(library_id=entry["lib_id"],
                                               key=entry["key"],
                                               _value=entry["value"])
                ) for entry in to_insert
            ]
            # Update
            for entry in to_update:
                entry[0]._value = entry[1]

            # Delete
            [_db.delete(entry) for entry in to_delete]
        except Exception as ex:
            logging.error("Cannot perform db operations. Ex: %s", ex)
            raise

        try:
            _db.commit()
        except Exception as ex:
            logging.error("Error while commiting plugin changes. Ex: %s", ex)
            _db.rollback()
            raise

