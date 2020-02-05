"""Turn local URLs into CDN URLs."""
import os, sys
import urllib.request, urllib.parse, urllib.error
import urllib.parse
from nose.tools import set_trace

from .config import Configuration, CannotLoadConfiguration
from .s3 import S3Uploader

def cdnify(url, cdns=None):
    """Turn local URLs into CDN URLs"""
    try:
        cdns = cdns or Configuration.cdns()
    except CannotLoadConfiguration as e:
        pass

    if not cdns:
        # No CDNs configured
        return url
    scheme, netloc, path, query, fragment = urllib.parse.urlsplit(url)

    if netloc == 's3.amazonaws.com':
        # This is a URL like "http://s3.amazonaws.com/bucket/foo".
        # It's equivalent to "http://bucket/foo".
        # i.e. treat the bucket name as the netloc.
        #
        # Since we are using the 'filename' to generate a URL rather
        # than talk to S3, we don't want it to be unquoted.
        #
        netloc, path = S3Uploader.bucket_and_filename(url, unquote=False)

    if netloc not in cdns:
        # This domain name is not covered by any of our CDNs.
        return url

    cdn_host = cdns[netloc]
    cdn_scheme, cdn_netloc, i1, i2, i3 = urllib.parse.urlsplit(cdn_host)
    return urllib.parse.urlunsplit((cdn_scheme, cdn_netloc, path, query, fragment))

