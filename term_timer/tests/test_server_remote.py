"""Tests for the requests of a client from the local network."""
import unittest
from http import HTTPStatus

from term_timer.server.app import Server
from term_timer.tests.test_server_daily import DAY
from term_timer.tests.test_server_daily import DailyServerTestCase

# A phone on the same Wi-Fi as the computer serving the pages.
LAN_CLIENT = '192.168.1.20'


class TestLocalClient(unittest.TestCase):
    """Tests for the client told local, the only one allowed to write."""

    def test_loopback_addresses(self) -> None:
        """Loopback in IPv4, IPv6 or IPv4 mapped in IPv6 is local."""
        for address in ('127.0.0.1', '127.0.1.1', '::1', '::ffff:127.0.0.1'):
            with self.subTest(address=address):
                self.assertTrue(
                    Server.is_local_client({'REMOTE_ADDR': address}),
                )

    def test_remote_addresses(self) -> None:
        """A peer, a missing or a malformed address is never local."""
        for address in (LAN_CLIENT, '::ffff:192.168.1.20', 'fe80::1', ''):
            with self.subTest(address=address):
                self.assertFalse(
                    Server.is_local_client({'REMOTE_ADDR': address}),
                )
        self.assertFalse(Server.is_local_client({}))

    def test_forwarded_header_ignored(self) -> None:
        """A peer claiming to forward for this computer stays remote."""
        self.assertFalse(Server.is_local_client({
            'REMOTE_ADDR': LAN_CLIENT,
            'HTTP_X_FORWARDED_FOR': '127.0.0.1',
        }))


class TestRemoteWrites(DailyServerTestCase):
    """Tests for the writes sent from the local network."""

    def test_remote_writes_refused(self) -> None:
        """A peer can neither delete, flag nor comment a solve."""
        before = self.read_day(DAY)
        for action, form in (
                ('delete', {}),
                ('flag', {'flag': 'DNF'}),
                ('comment', {'comment': 'erased'}),
        ):
            with self.subTest(action=action):
                status, _headers, _body = self.client.post(
                    f'/daily/3/{ DAY }/1/{ action }/', form,
                    remote=LAN_CLIENT,
                )

                self.assertEqual(status, HTTPStatus.FORBIDDEN)
                self.assertEqual(self.read_day(DAY), before)

    def test_remote_session_delete_refused(self) -> None:
        """The routes of a named session are refused as well."""
        status, _headers, _body = self.client.post(
            '/3/default/1/delete/', remote=LAN_CLIENT,
        )

        self.assertEqual(status, HTTPStatus.FORBIDDEN)

    def test_local_delete_allowed(self) -> None:
        """A loopback client still deletes a solve."""
        status, _headers, _body = self.client.post(
            f'/daily/3/{ DAY }/1/delete/', remote='::1',
        )

        self.assertEqual(status, HTTPStatus.SEE_OTHER)
        self.assertEqual(len(self.read_day(DAY)), 2)

    def test_remote_reads_allowed(self) -> None:
        """A peer still reads the pages, the scrambles of a duel first."""
        for path in (f'/daily/3/{ DAY }/1/', '/scramble/'):
            with self.subTest(path=path):
                status, _headers, _body = self.client.request(
                    'GET', path, remote=LAN_CLIENT,
                )

                self.assertEqual(status, HTTPStatus.OK)
