fakemtpd
========

**fakemtpd** was a simple tool that emulates a modern SMTP daemon. It accepts
connections and contains a valid implementation of the SMTP protocol as specified
in [RFC 821](http://tools.ietf.org/html/rfc821) and
[RFC 5321](http://tools.ietf.org/html/rfc5321).

This code hasn't been maintained since 2015 and does not work on any contemporary version of Python.
It has some security issues, and needs to be rewritten to use tornado 5+ and asyncio.
