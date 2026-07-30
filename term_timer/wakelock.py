"""Keep the screen awake for a solving session, under our own name."""
from itertools import starmap
from typing import Final

from wakepy import Method
from wakepy import Mode
from wakepy import keep
from wakepy.core import DBusMethodCall

# Identity of the lock, as the desktop lists its inhibitors
WHO: Final = 'term-timer'
WHY: Final = 'Solving on a cube'

# Call parameters naming the holder of a lock, per D-Bus interface:
# app_id and reason on org.gnome.SessionManager, application_name and
# reason_for_inhibit on the freedesktop.org ones
IDENTITY: Final = {
    'app_id': WHO,
    'application_name': WHO,
    'reason': WHY,
    'reason_for_inhibit': WHY,
}


def rebrand_call(call: DBusMethodCall) -> DBusMethodCall:
    """
    Sign a D-Bus call with our identity instead of the library one.

    Wakepy hardcodes ``wakepy`` and ``wakelock active`` in the arguments
    of its Inhibit calls, which is what the desktop then shows in its
    list of inhibitors. Arguments being positional, they are matched back
    to their names through the parameters of the called method, and only
    those naming the holder are replaced.

    Args:
        call: The D-Bus call about to be processed.

    Returns:
        The same call, signed by us when it carries an identity.

    """
    params = call.method.params

    if params is not None:
        call.args = tuple(
            starmap(IDENTITY.get, zip(params, call.args, strict=False)),
        )

    return call


def patch_wakepy_identity() -> None:
    """
    Route every D-Bus call of wakepy through our signature.

    The identity is hardcoded in the ``enter_mode`` of each method, with
    no setting to change it, so the single gate every method calls is
    wrapped instead. A wakepy release moving that gate or renaming its
    parameters costs the name shown in the inhibitor list, nothing more:
    the lock itself is taken all the same.
    """
    process_dbus_call = Method.process_dbus_call

    def process_signed_dbus_call(
            self: Method, call: DBusMethodCall,
    ) -> object:
        return process_dbus_call(self, rebrand_call(call))

    Method.process_dbus_call = process_signed_dbus_call  # type: ignore[method-assign]


patch_wakepy_identity()


def keep_awake() -> Mode:
    """
    Build the wake lock held for the length of a solving session.

    Solving on a smart cube produces no keyboard nor mouse event, so the
    session would otherwise blank the screen and suspend the machine in
    the middle of an attempt. Only idle is inhibited: a suspend asked for
    explicitly, lid included, must keep working during a session.

    A system offering no inhibitor is not an error, the session simply
    runs unlocked, hence the silent failure: the warning wakepy issues by
    default would land in the middle of the timer display.

    Returns:
        The lock, to be held as a context manager.

    """
    return keep.presenting(on_fail='pass')
