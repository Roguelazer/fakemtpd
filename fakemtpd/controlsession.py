import functools
import logging
import re

try:
    import simplejson as json
except ImportError:
    import json

import fakemtpd.stats
from fakemtpd.config import Config

QUIT_COMMAND=re.compile(r'^quit', re.I)
HELP_COMMAND=re.compile(r'^help', re.I)
SHUTDOWN_COMMAND=re.compile(r'^shutdown', re.I)

helpstr="""fakemtpd control interface

lets you do all sorts of neat things to control fakemtpd

commands:
    help            prints this help
    quit            disconnect from the interface
    shutdown        shut down fakemtpd immediately
    stats           show statistics

"""

log = logging.getLogger("control")

class ControlSession(object):
    """Implement the control protocol on top of a Connection"""

    def __init__(self, connection, server):
        self.conn = connection
        self.conn.on_connected(functools.partial(fakemtpd.stats.increment, "lifetime_control_sessions"))
        self.conn.on_timeout(self._print_timeout)
        self.conn.on_data(self._handle_data)
        self.config = Config.instance()
        self.server = server

    def _handle_data(self, data):
        quit_match = QUIT_COMMAND.match(data)
        help_match = HELP_COMMAND.match(data)
        if data.startswith("quit"):
            self.conn.close()
            return
        elif data.startswith("help"):
            self._print_help()
        elif data.startswith("shutdown"):
            log.warn("shutting down via control socket")
            self.server.stop()
        elif data.startswith("stats"):
            self._print_stats()

    def _print_timeout(self):
        self.conn.write("Timeout exceeded, good bye\n", self.conn.close, False)

    def _print_help(self):
        for line in helpstr.split("\n"):
            self.conn.write(line + "\n")

    def _print_stats(self):
        stats = {}
        for stat in fakemtpd.stats.tracked_stats:
            stats[stat] = fakemtpd.stats.get(stat)
        self.conn.write(json.dumps(stats) + "\n")
