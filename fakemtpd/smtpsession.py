import re

from fakemtpd.config import Config

# SMTP States
SMTP_TLS_NEGOT = -1
SMTP_DISCONNECTED = 0
SMTP_CONNECTED = 1
SMTP_HELO = 2
SMTP_MAIL_FROM = 3

# Command REs
MAIL_FROM_COMMAND=re.compile(r'MAIL\s+FROM:\s*<(.+)>', re.I)
HELO_COMMAND=re.compile(r'^HELO\s+(.*)', re.I)
EHLO_COMMAND=re.compile(r'^EHLO\s+(.*)', re.I)
RCPT_TO_COMMAND=re.compile(r'^RCPT\s+TO:\s*<(.+)>', re.I)
VRFY_COMMAND=re.compile(r'^VRFY (<?.+>?)', re.I)
QUIT_COMMAND=re.compile(r'^QUIT', re.I)
NOOP_COMMAND=re.compile(r'^NOOP', re.I)
RSET_COMMAND=re.compile(r'^RSET', re.I)
DATA_COMMAND=re.compile(r'^DATA', re.I)
HELP_COMMAND=re.compile(r'^HELP', re.I)
EXPN_COMMAND=re.compile(r'^EXPN', re.I)
STARTTLS_COMMAND=re.compile(r'^STARTTLS', re.I)

class SMTPSession(object):
    """Implement the SMTP protocol on top of a Connection"""

    # Timeout before disconecting (in seconds)
    timeout = 30

    def __init__(self, connection):
        self.conn = connection
        self.conn.on_connected(self._connect)
        self.conn.on_connected(self._print_banner)
        self.conn.on_timeout(self._print_timeout)
        self.conn.on_data(self._handle_data)
        self.config = Config.instance()
        self.remote = ''
        self._state = SMTP_DISCONNECTED
        self._message_state = {}
        self._mode = 'HELO'

    def _connect(self):
        self._state = SMTP_CONNECTED

    def _print_banner(self):
        self.conn.write("220 %s %s %s\r\n" % (self.config.hostname, self.config.smtp_ver, self.config.mtd))

    def _handle_data(self, data):
        rv = False
        if self._state_all(data):
            return
        if self._state >= SMTP_HELO:
            rv = self._state_after_helo(data)
        if self._state == SMTP_CONNECTED:
            rv = self._state_connected(data)
            # Some people don't HELO before sending commands; lame
            if not rv:
                rv = self._state_helo(data)
        elif self._state == SMTP_HELO:
            rv = self._state_helo or self._state_after_helo(data)
        elif self._state == SMTP_HELO:
            rv = self._state_helo(data)
        elif self._state == SMTP_MAIL_FROM:
            rv = self._state_mail_from(data)
        elif self._state == SMTP_TLS_NEGOT:
            rv = self._state_tls_negot(data)
        if rv == False:
            self.conn.write("503 Commands out of sync or unrecognized\r\n")
            self._state = SMTP_HELO if self._state >= SMTP_HELO else SMTP_CONNECTED

    def _state_all(self, data):
        quit_match = QUIT_COMMAND.match(data)
        rset_match = RSET_COMMAND.match(data)
        noop_match = NOOP_COMMAND.match(data)
        help_match = HELP_COMMAND.match(data)
        if quit_match:
            self.conn.write_and_close("221 2.0.0 Bye\r\n")
            return True
        elif rset_match:
            self._state = SMTP_HELO if self._state >= SMTP_HELO else SMTP_CONNECTED
            self._message_state = {}
            self.conn.write("250 2.0.0 Ok\r\n")
            return True
        elif noop_match:
            self.conn.write("250 2.0.0 Ok\r\n")
            return True
        elif help_match:
            self.conn.write_help()
            return True

    def _state_connected(self, data):
        helo_match = HELO_COMMAND.match(data)
        ehlo_match = EHLO_COMMAND.match(data)
        if helo_match:
            self.remote = helo_match.group(1)
            self.conn.write("250 %s\r\n" % self.config.hostname)
            self._state = SMTP_HELO
            self._mode = 'HELO'
            return True
        elif ehlo_match:
            self.remote = ehlo_match.group(1)
            self.conn.write("250 %s\r\n" % self.config.hostname)
            if self.config.cert:
                self.conn.write("250-STARTTLS\r\n")
            self._state = SMTP_HELO
            self._mode = 'EHLO'
            return True
        return False

    def _state_helo(self, data):
        mail_from_match = MAIL_FROM_COMMAND.match(data)
        vrfy_match = VRFY_COMMAND.match(data)
        expn_match = EXPN_COMMAND.match(data)
        if mail_from_match:
            self._message_state = {}
            self._message_state['mail_from'] = mail_from_match.group(1)
            self.conn.write("250 2.1.0 Ok\r\n")
            self._state = SMTP_MAIL_FROM
            return True
        elif vrfy_match:
            self.conn.write("502 5.5.1 VRFY command is disabled\r\n")
            self._state = SMTP_HELO if self._state >= SMTP_HELO else SMTP_CONNECTED
            return True
        elif expn_match:
            self.conn.write("502 5.5.1 EXPN command is disabled\r\n")
            self._state = SMTP_HELO if self._state >= SMTP_HELO else SMTP_CONNECTED
            return True
        return False

    def _state_after_helo(self, data):
        starttls_match = STARTTLS_COMMAND.match(data)
        if starttls_match:
            if self.config.cert and self._mode == 'EHLO':
                self.conn.write('220 Go Ahead')
                self._state = SMTP_TLS_NEGOT
            else:
                self.conn.write('502 5.5.1 STARTTLS not supported in RFC821 mode (meant to say EHLO?)\r\n')
            return True
        return False

    def _state_mail_from(self, data):
        rcpt_to_match = RCPT_TO_COMMAND.match(data)
        data_match = DATA_COMMAND.match(data)
        mail_from_match = MAIL_FROM_COMMAND.match(data)
        if rcpt_to_match:
            self._message_state.setdefault('rcpt_to', []).append(rcpt_to_match.group(1))
            self.conn.write("554 5.7.1 <%s>: Relay access denied\r\n" % self._message_state['mail_from'])
            self._state = SMTP_HELO
            return True
        elif data_match:
            self.conn.write("502 5.5.1 DATA command is disabled\r\n")
            self._state = SMTP_HELO
            return True
        elif mail_from_match:
            self.conn.write("503 5.5.1 Error: nested MAIL command\r\n")
            self._state = SMTP_HELO
            return True
        return False

    def _state_tls_negot(self, data):
        return False

    def _print_timeout(self):
        self._timeout_handle = None
        self.conn.write_and_close("421 4.4.2 %s Error: timeout exceeded\r\n" % self.config.hostname)

    def write_help(self):
        self.conn.write("250 Ok\r\n")
        message = [
                "HELO",
                "EHLO",
                "HELP",
                "NOOP",
                "QUIT",
                "MAIL FROM:<address>",
                "RCPT TO:<address>",
                "DATA",
                "VRFY",
                "EXPN",
                "RSET",
        ]
        for msg in message:
            self.conn.write("250 HELP - " + msg + "\r\n")
