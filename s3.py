import logging
import os
import boto3
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
)
import urllib
from flask_babel import lazy_gettext as _
from nose.tools import set_trace
from sqlalchemy.orm.session import Session
from urlparse import urlsplit
from mirror import MirrorUploader

from config import CannotLoadConfiguration
from model import ExternalIntegration
from requests.exceptions import (
    ConnectionError,
    HTTPError,
)

class S3Uploader(MirrorUploader):

    NAME = ExternalIntegration.S3

    S3_HOSTNAME = "s3.amazonaws.com"
    S3_BASE = "https://%s/" % S3_HOSTNAME

    BOOK_COVERS_BUCKET_KEY = u'book_covers_bucket'
    OA_CONTENT_BUCKET_KEY = u'open_access_content_bucket'

    URL_TEMPLATE_KEY = u'bucket_name_transform'
    URL_TEMPLATE_HTTP = u'http'
    URL_TEMPLATE_HTTPS = u'https'
    URL_TEMPLATE_DEFAULT = u'identity'

    URL_TEMPLATES_BY_TEMPLATE = {
        URL_TEMPLATE_HTTP: u'http://%(bucket)s/%(key)s',
        URL_TEMPLATE_HTTPS: u'https://%(bucket)s/%(key)s',
        URL_TEMPLATE_DEFAULT: S3_BASE + u'%(bucket)s/%(key)s',
    }

    SETTINGS = [
        { "key": ExternalIntegration.USERNAME, "label": _("Access Key") },
        { "key": ExternalIntegration.PASSWORD, "label": _("Secret Key") },
        { "key": BOOK_COVERS_BUCKET_KEY, "label": _("Book Covers Bucket"), "optional": True,
          "description" : _("All book cover images encountered will be mirrored to this S3 bucket. Large images will be scaled down, and the scaled-down copies will also be uploaded to this bucket. <p>The bucket must already exist&mdash;it will not be created automatically.</p>")
        },
        { "key": OA_CONTENT_BUCKET_KEY, "label": _("Open Access Content Bucket"), "optional": True,
          "description" : _("All open-access books encountered will be uploaded to this S3 bucket. <p>The bucket must already exist&mdash;it will not be created automatically.</p>")
        },
        { "key": URL_TEMPLATE_KEY, "label": _("URL format"),
          "type": "select",
          "options" : [
              { "key" : URL_TEMPLATE_DEFAULT,
                "label": _("S3 Default: https://s3.amazonaws.com/{bucket}/{file}"),
              },
              { "key" : URL_TEMPLATE_HTTPS,
                "label": _("HTTPS: https://{bucket}/{file}"),
              },
              { "key" : URL_TEMPLATE_HTTP,
                "label": _("HTTP: http://{bucket}/{file}"),
              },
          ],
          "default": URL_TEMPLATE_DEFAULT,
          "description" : _("A file mirrored to S3 is available at <code>http://s3.amazonaws.com/{bucket}/{filename}</code>. If you've set up your DNS so that http:///[bucket]/ or https://[bucket]/ points to the appropriate S3 bucket, you can configure this S3 integration to shorten the URLs. <p>If you haven't set up your S3 buckets, don't change this from the default -- you'll get URLs that don't work.</p>")
        },
    ]

    SITEWIDE = True

    def __init__(self, integration, client_class=None):
        """Instantiate an S3Uploader from an ExternalIntegration.

        :param integration: An ExternalIntegration

        :param client_class: Mock object (or class) to use (or instantiate)
            instead of boto3.client.
        """
        if not client_class:
            client_class = boto3.client

        if callable(client_class):
            access_key = integration.username
            secret_key = integration.password
            if not (access_key and secret_key):
                raise CannotLoadConfiguration(
                    'Cannot create S3Uploader without both'
                    ' access_key and secret_key.'
                )
            self.client = client_class(
                's3',
                aws_access_key_id=access_key, 
                aws_secret_access_key=secret_key,
            )
        else:
            self.client = client_class

        self.url_transform = integration.setting(
            self.URL_TEMPLATE_KEY).value_or_default(
                self.URL_TEMPLATE_DEFAULT)

        # Transfer information about bucket names from the
        # ExternalIntegration to the S3Uploader object, so we don't
        # have to keep the ExternalIntegration around.
        self.buckets = dict()
        for setting in integration.settings:
            if setting.key.endswith('_bucket'):
                self.buckets[setting.key] = setting.value
    def get_bucket(self, bucket_key):
        """Gets the bucket for a particular use based on the given key"""
        return self.buckets.get(bucket_key)

    @classmethod
    def url(cls, bucket, path):
        """The URL to a resource on S3 identified by bucket and path."""
        if path.startswith('/'):
            path = path[1:]
        if bucket.startswith('http://') or bucket.startswith('https://'):
            url = bucket
        else:
            url = cls.S3_BASE + bucket
        if not url.endswith('/'):
            url += '/'
        return url + path

    @classmethod
    def cover_image_root(cls, bucket, data_source, scaled_size=None):
        """The root URL to the S3 location of cover images for
        the given data source.
        """
        if scaled_size:
            path = "/scaled/%d/" % scaled_size
        else:
            path = "/"
        if isinstance(data_source, str):
            data_source_name = data_source
        else:
            data_source_name = data_source.name
        data_source_name = urllib.quote(data_source_name)
        path += data_source_name + "/"
        url = cls.url(bucket, path)
        if not url.endswith('/'):
            url += '/'
        return url

    @classmethod
    def content_root(cls, bucket, open_access=True):
        """The root URL to the S3 location of hosted content of
        the given type.
        """
        if not open_access:
            raise NotImplementedError()
        return cls.url(bucket, '/')

    def book_url(self, identifier, extension='.epub', open_access=True,
                 data_source=None, title=None):
        """The path to the hosted EPUB file for the given identifier."""
        bucket = self.get_bucket(self.OA_CONTENT_BUCKET_KEY)
        root = self.content_root(bucket, open_access)

        if not extension.startswith('.'):
            extension = '.' + extension

        if title:
            filename = "%s/%s" % (identifier.identifier, title)
        else:
            filename = identifier.identifier

        args = [identifier.type, filename]
        args = [urllib.quote(x.encode('utf-8')) for x in args]
        if data_source:
            args.insert(0, urllib.quote(data_source.name))
            template = "%s/%s/%s%s"
        else:
            template = "%s/%s%s"

        return root + template % tuple(args + [extension])

    def cover_image_url(self, data_source, identifier, filename,
                        scaled_size=None):
        """The path to the hosted cover image for the given identifier."""
        bucket = self.get_bucket(self.BOOK_COVERS_BUCKET_KEY)
        root = self.cover_image_root(bucket, data_source, scaled_size)

        args = [identifier.type, identifier.identifier, filename]
        args = [urllib.quote(x) for x in args]
        return root + "%s/%s/%s" % tuple(args)

    @classmethod
    def bucket_and_filename(cls, url):
        scheme, netloc, path, query, fragment = urlsplit(url)
        if netloc == 's3.amazonaws.com':
            if path.startswith('/'):
                path = path[1:]
            bucket, filename = path.split("/", 1)
        else:
            bucket = netloc
            filename = path[1:]
        return bucket, urllib.unquote(filename)

    def final_mirror_url(self, bucket, key):
        """Determine the URL to use as Representation.mirror_url, assuming
        that it was successfully uploaded to the given `bucket` as `key`.

        Depending on ExternalIntegration configuration this may 
        be any of the following:

        https://s3.amazonaws.com/{bucket}/{key}
        http://{bucket}/{key}
        https://{bucket}/{key}
        """
        templates = self.URL_TEMPLATES_BY_TEMPLATE
        default = templates[self.URL_TEMPLATE_DEFAULT]
        template = templates.get(self.url_transform, default)
        return template % dict(bucket=bucket, key=key)

    def mirror_one(self, representation):
        """Mirror a single representation."""
        return self.mirror_batch([representation])

    def mirror_batch(self, representations):
        """Mirror a bunch of Representations at once."""
        for representation in representations:
            # TODO: It's strange that we're setting mirror_url to the
            # original URL when the file hasn't been mirrored and that
            # may not end up being the final URL. We should be able to
            # simplify this.
            if not representation.mirror_url:
                representation.mirror_url = representation.url
            # Turn the mirror URL into an s3.amazonaws.com URL.
            bucket, filename = self.bucket_and_filename(
                representation.mirror_url
            )
            media_type = representation.external_media_type
            bucket, remote_filename = self.bucket_and_filename(
                representation.mirror_url)
            fh = representation.external_content()
            try:
                result = self.client.upload_fileobj(
                    Fileobj=fh,
                    Bucket=bucket,
                    Key=remote_filename,
                    ExtraArgs=dict(ContentType=media_type)
                )

                # Since upload_fileobj completed without a problem, we
                # know the file is available at
                # https://s3.amazonaws.com/{bucket}/{remote_filename}. But
                # that may not be the URL we want to store.
                representation.mirror_url = self.final_mirror_url(
                    bucket, remote_filename
                )

                source = representation.local_content_path
                if representation.url != representation.mirror_url:
                    source = representation.url
                if source:
                    logging.info("MIRRORED %s => %s",
                                 source, representation.mirror_url)
                else:
                    logging.info("MIRRORED %s", representation.mirror_url)
                representation.set_as_mirrored()
            except (BotoCoreError, ClientError), e:
                # BotoCoreError happens when there's a problem with
                # the network transport. ClientError happens when
                # there's a problem with the credentials. Either way,
                # the best thing to do is treat this as a transient
                # error and try again later. There's no scenario where
                # giving up is the right move.
                logging.error(
                    "Error uploading %s: %r", representation.mirror_url,
                    e, exc_info=e
                )
            finally:
                fh.close()

# MirrorUploader.implementation will instantiate an S3Uploader
# for storage integrations with protocol 'Amazon S3'.
MirrorUploader.IMPLEMENTATION_REGISTRY[S3Uploader.NAME] = S3Uploader


class MockS3Uploader(S3Uploader):
    """A dummy uploader for use in tests."""

    buckets = {
       S3Uploader.BOOK_COVERS_BUCKET_KEY : 'test.cover.bucket',
       S3Uploader.OA_CONTENT_BUCKET_KEY : 'test.content.bucket',
    }

    def __init__(self, fail=False, *args, **kwargs):
        self.uploaded = []
        self.content = []
        self.fail = fail

    def mirror_batch(self, representations):
        self.uploaded.extend(representations)
        self.content.extend([r.content for r in representations])
        for representation in representations:
            if self.fail:
                representation.mirror_exception = "Exception"
                representation.mirrored_at = None
            else:
                if not representation.mirror_url:
                    representation.mirror_url = representation.url
                representation.set_as_mirrored()


class MockS3Client(object):
    """This pool lets us test the real S3Uploader class with a mocked-up
    boto3 client.
    """

    def __init__(self, service, aws_access_key_id, aws_secret_access_key):
        assert service == 's3'
        self.access_key = aws_access_key_id
        self.secret_key = aws_secret_access_key
        self.uploads = []
        self.fail_with = None

    def upload_fileobj(self, Fileobj, Bucket, Key, ExtraArgs=None, **kwargs):
        if self.fail_with:
            raise self.fail_with
        self.uploads.append((Fileobj.read(), Bucket, Key, ExtraArgs, kwargs))
        return None
