[![Build Status](https://travis-ci.org/Roguelazer/fakemtpd.png)](https://travis-ci.org/Roguelazer/fakemtpd)

fakemtpd
========

**fakemtpd** is a simple tool that emulates a modern SMTP daemon. It accepts
connections and contains a valid implementation of the SMTP protocol as specified
in [http://tools.ietf.org/html/rfc821](RFC 821) and
[http://tools.ietf.org/html/rfc5321](RFC 5321).

Usage
-----
Run `fakemtpd` with no arguments to start a default server. To see the default
configuration, run `fakemtpd --gen-config`. You can change any of these parameters
and write them to a YAML file, and then run `fakemtpd -c /path/to/config.yaml`. Many
of the configuration parameters can also be overridden at the command line;
run `fakemtpd --help` to see which ones.

Contributing
------------
In general, forks and pull requests are useful. If you want to do something more
involved, send an e-mail to [mailto:Roguelazer@gmail.com](James Brown).

License
-------
This work is available under the ISC (OpenBSD) license. The full contents of this
license are available as LICENSE
