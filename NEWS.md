fakemtpd 0.2.0
==============
This release supports logging to syslog instead of just to a file, which closes Issue #1. To use it, add the following fragment to your config file:

```yaml
    logging_method: syslog
```

Syslog also supports some configuration. You can set the `syslog_domain_socket` to log to a domain socket (typically actually the `/dev/log` node). By default, it will use UDP to log to `localhost:514`. You can override these with the `syslog_host` and/or `syslog_port` configuration options. As usual, all of these options have command-line equivalents.

Additionally, this version cleans up some of the configuration methods. And adds this NEWS file!

fakemtpd 0.1.6
==============
* Fixes some shutdown bugs with the lockfile
* Allows specifying groups instead of GIDs
* Fixes a bug where privileges weren't being restored before re-opening log
  file

fakemtpd 0.1.5
==============
* Greatly improves logging

fakemtpd 0.1.4
==============
* Fixes some parsing bugs

fakemtpd 0.1.3
==============
* Change the EUID/EGID instead of RUID/RGID

fakemtpd 0.1.2
==============
* buildsystem changes

fakemtpd 0.1.1
==============
Lots of fixes here!

fakemtpd 0.1
============
Initial release
