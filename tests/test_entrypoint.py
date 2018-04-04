from testing import DatabaseTest
from nose.tools import (
    assert_raises_regexp,
    eq_,
    set_trace,
)
from model import (
    Edition,
)
from entry point import (
    EntryPoint,
    EbooksEntryPoint,
    AudiobooksEntryPoint,
    MediumEntryPoint,
)

class TestEntryPoint(object):

    def test_defaults(self):
        ebooks, audiobooks = EntryPoint.ENTRY_POINTS
        eq_(EbooksEntryPoint, ebooks)
        eq_(AudiobooksEntryPoint, audiobooks)

        display = EntryPoint.DISPLAY_TITLES
        eq_("Books", display[ebooks])
        eq_("Audiobooks", display[audiobooks])

        eq_(Edition.BOOK_MEDIUM, EbooksEntryPoint.INTERNAL_NAME)
        eq_(Edition.AUDIO_MEDIUM, AudiobooksEntryPoint.INTERNAL_NAME)

    def test_register(self):

        class Mock(object):
            pass

        args = [Mock, "Mock!"]

        assert_raises_regexp(
            ValueError, "must define INTERNAL_NAME", EntryPoint.register, *args
        )

        # Test successful registration.
        Mock.INTERNAL_NAME = "a name"
        EntryPoint.register(*args)
        assert Mock in EntryPoint.ENTRY_POINTS
        eq_("Mock!", EntryPoint.DISPLAY_TITLES[Mock])
        assert Mock not in EntryPoint.DEFAULT_ENABLED

        # Can't register twice.
        assert_raises_regexp(
            ValueError, "Duplicate entry point internal name: a name",
            EntryPoint.register, *args
        )

        EntryPoint.unregister(Mock)

        # Test successful registration as a default-enabled entry point.
        EntryPoint.register(*args, default_enabled=True)
        assert Mock in EntryPoint.DEFAULT_ENABLED


class TestMediumEntryPoint(DatabaseTest):

    def test_apply(self):
        # Create a video, and a entry point that contains videos.
        work = self._work(with_license_pool=True)
        work.license_pools[0].presentation_edition.medium = Edition.VIDEO_MEDIUM
        self.add_to_materialized_view([work])

        class Videos(MediumEntryPoint):
            INTERNAL_NAME = Edition.VIDEO_MEDIUM

        from model import MaterializedWorkWithGenre
        qu = self._db.query(MaterializedWorkWithGenre)

        # The default entry points filter out the video.
        for entry point in EbooksEntryPoint, AudiobooksEntryPoint:
            modified = entry point.apply(qu)
            eq_([], modified.all())

        # But the video entry point includes it.
        videos = Videos.apply(qu)
        eq_([work.id], [x.works_id for x in videos])


    def test_modified_search_arguments(self):

        class Mock(MediumEntryPoint):
            INTERNAL_NAME = object()

        kwargs = dict(media="something else", other_argument="unaffected")
        new_kwargs = Mock.modified_search_arguments(**kwargs)
        eq_(dict(media=[Mock.INTERNAL_NAME], other_argument="unaffected"),
            new_kwargs)
