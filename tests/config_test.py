from __future__ import absolute_import

import ssl
from cStringIO import StringIO

import fakemtpd.config

from testify import TestCase, assert_equal, assert_is, run


def _config_with(config_string):
    s = StringIO()
    s.write(config_string)
    s.seek(0)
    c = fakemtpd.config.Config.instance()
    c.read_file_obj(s)
    return c


class ConfigTestCase(TestCase):

    def test_is_singleton(self):
        c1 = fakemtpd.config.Config.instance()
        c2 = fakemtpd.config.Config.instance()
        assert_is(c1, c2)

    def test_ssl_versions(self):
        c = _config_with('')
        assert_equal(ssl.PROTOCOL_SSLv23, c.ssl_version)
        c = _config_with('ssl_version: ssl23')
        assert_equal(ssl.PROTOCOL_SSLv23, c.ssl_version)
        c = _config_with('ssl_version: tls1')
        assert_equal(ssl.PROTOCOL_TLSv1, c.ssl_version)


if __name__ == "__main__":
    run()
