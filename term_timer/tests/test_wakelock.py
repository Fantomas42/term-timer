"""Tests for the wake lock held during a solving session."""
import unittest

from wakepy import Method
from wakepy.core import DBusMethodCall
from wakepy.methods.freedesktop import FreedesktopScreenSaverInhibit
from wakepy.methods.gnome import GnomeSessionManagerNoIdle

from term_timer.wakelock import IDENTITY
from term_timer.wakelock import WHO
from term_timer.wakelock import WHY
from term_timer.wakelock import rebrand_call


class TestRebrandCall(unittest.TestCase):
    """Tests for the signature put on the calls wakepy makes."""

    def test_gnome_inhibit_is_signed(self) -> None:
        """The GNOME call carries our name and our reason."""
        call = DBusMethodCall(
            method=GnomeSessionManagerNoIdle.method_inhibit,
            args={
                'app_id': 'wakepy',
                'toplevel_xid': 42,
                'reason': 'wakelock active',
                'flags': 8,
            },
        )

        rebrand_call(call)

        self.assertEqual(call.args, (WHO, 42, WHY, 8))

    def test_screensaver_inhibit_is_signed(self) -> None:
        """The freedesktop.org call is signed on its own parameters."""
        call = DBusMethodCall(
            method=FreedesktopScreenSaverInhibit().method_inhibit,
            args={
                'application_name': 'wakepy',
                'reason_for_inhibit': 'wakelock active',
            },
        )

        rebrand_call(call)

        self.assertEqual(call.args, (WHO, WHY))

    def test_uninhibit_is_left_alone(self) -> None:
        """A call naming nobody goes through untouched."""
        call = DBusMethodCall(
            method=GnomeSessionManagerNoIdle.method_uninhibit,
            args={'inhibit_cookie': 1234},
        )

        rebrand_call(call)

        self.assertEqual(call.args, (1234,))


class TestWakepyIdentity(unittest.TestCase):
    """Tests guarding the seams the signature is hooked on."""

    def test_the_signed_gate_is_installed(self) -> None:
        """Importing the module wraps the gate every method calls."""
        self.assertEqual(
            Method.process_dbus_call.__name__,
            'process_signed_dbus_call',
        )

    def test_wakepy_still_names_the_holder_the_same_way(self) -> None:
        """The parameters we sign are the ones wakepy still declares."""
        params = set(GnomeSessionManagerNoIdle.method_inhibit.params or ())
        params |= set(
            FreedesktopScreenSaverInhibit().method_inhibit.params or (),
        )

        self.assertEqual(params & set(IDENTITY), set(IDENTITY))
