from nose.tools import set_trace
import datetime
from .config import CannotLoadConfiguration

class MirrorUploader():
    """Handles the job of uploading a representation's content to
    a mirror that we control.
    """

    STORAGE_GOAL = 'storage'

    # Depending on the .protocol of an ExternalIntegration with
    # .goal=STORAGE, a different subclass might be initialized by
    # sitewide() or for_collection(). A subclass that wants to take
    # advantage of this should add a mapping here from its .protocol
    # to itself.
    IMPLEMENTATION_REGISTRY = {}

    @classmethod
    def mirror(cls, _db, storage_name=None, integration=None):
        """Create a MirrorUploader from an integration or storage name.

        :param storage_name: The name of the storage integration.
        :param integration: The external integration.

        :return: A MirrorUploader.

        :raise: CannotLoadConfiguration if no integration with
            goal==STORAGE_GOAL is configured.
        """
        if not integration:
            integration = cls.integration_by_name(_db, storage_name)
        return cls.implementation(integration)

    @classmethod
    def integration_by_name(cls, _db, storage_name=None):
        """Find the ExternalIntegration for the mirror by storage name."""
        from .model import ExternalIntegration
        qu = _db.query(ExternalIntegration).filter(
            ExternalIntegration.goal==cls.STORAGE_GOAL,
            ExternalIntegration.name==storage_name
        )
        integrations = qu.all()
        if not integrations:
            raise CannotLoadConfiguration(
                "No storage integration with name '%s' is configured." % storage_name
            )

        [integration] = integrations
        return integration

    @classmethod
    def for_collection(cls, collection, purpose):
        """Create a MirrorUploader for the given Collection.

        :param collection: Use the mirror configuration for this Collection.
        :param purpose: Use the purpose of the mirror configuration.

        :return: A MirrorUploader, or None if the Collection has no
            mirror integration.
        """
        from .model import ExternalIntegration
        try:
            from .model import Session
            _db = Session.object_session(collection)
            integration = ExternalIntegration.for_collection_and_purpose(_db, collection, purpose)
        except CannotLoadConfiguration as e:
            return None
        return cls.implementation(integration)

    @classmethod
    def implementation(cls, integration):
        """Instantiate the appropriate implementation of MirrorUploader
        for the given ExternalIntegration.
        """
        if not integration:
            return None
        implementation_class = cls.IMPLEMENTATION_REGISTRY.get(
            integration.protocol, cls
        )
        return implementation_class(integration)

    def __init__(self, integration):
        """Instantiate a MirrorUploader from an ExternalIntegration.

        :param integration: An ExternalIntegration configuring the credentials
           used to upload things.
        """
        if integration.goal != self.STORAGE_GOAL:
            # This collection's 'mirror integration' isn't intended to
            # be used to mirror anything.
            raise CannotLoadConfiguration(
                "Cannot create an MirrorUploader from an integration with goal=%s" %
                integration.goal
            )

        # Subclasses will override this to further configure the client
        # based on the credentials in the ExternalIntegration.

    def do_upload(self, representation):
        raise NotImplementedError()

    def mirror_one(self, representation):
        """Mirror a single Representation."""
        now = datetime.datetime.utcnow()
        exception = self.do_upload(representation)
        representation.mirror_exception = exception
        if exception:
            representation.mirrored_at = None
        else:
            representation.mirrored_at = now

    def mirror_batch(self, representations):
        """Mirror a batch of Representations at once."""

        for representation in representations:
            self.mirror_one(representation)

    def book_url(self, identifier, extension='.epub', open_access=True,
                 data_source=None, title=None):
        """The URL of the hosted EPUB file for the given identifier.

        This does not upload anything to the URL, but it is expected
        that calling mirror() on a certain Representation object will
        make that representation end up at that URL.
        """
        raise NotImplementedError()

    def cover_image_url(self, data_source, identifier, filename=None,
                        scaled_size=None):
        """The URL of the hosted cover image for the given identifier.

        This does not upload anything to the URL, but it is expected
        that calling mirror() on a certain Representation object will
        make that representation end up at that URL.
        """
        raise NotImplementedError()
