"""The parts that differ between Linux, macOS and Windows.

Only the Linux branch is tested. The macOS and Windows branches are untested.
"""

import os
import socket
import subprocess
import sys
from contextlib import contextmanager
from http.server import ThreadingHTTPServer

WINDOWS = sys.platform == "win32"
MACOS = sys.platform == "darwin"

if WINDOWS:
    import msvcrt
else:
    import fcntl

# PowerShell AppUserModelID: Windows shows toasts only for a registered app ID.
_PS_APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
# The title and body come from GitHub. Pass them as environment variables, never in the
# script text, so that no title can inject code.
_PS_TOAST = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$x = $t.GetElementsByTagName("text")
$x.Item(0).AppendChild($t.CreateTextNode($env:GHI_TITLE)) > $null
$x.Item(1).AppendChild($t.CreateTextNode($env:GHI_BODY)) > $null
if ($env:GHI_URGENT -eq "1") { $t.DocumentElement.SetAttribute("duration", "long") }
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:GHI_APP).Show([Windows.UI.Notifications.ToastNotification]::new($t))
"""


# ---- pop-ups ----------------------------------------------------------------

def notify(title, body, urgent=False):
    """Show a desktop pop-up. On Linux, an urgent pop-up stays until you close it."""
    env = None
    if WINDOWS:
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS_TOAST]
        env = dict(os.environ, GHI_TITLE=title, GHI_BODY=body, GHI_URGENT=str(int(urgent)),
                   GHI_APP=_PS_APP_ID)
    elif MACOS:
        # The texts are arguments to the script, never part of the script text.
        cmd = ["osascript", "-e", "on run argv",
               "-e", "display notification (item 2 of argv) with title (item 1 of argv)",
               "-e", "end run", title, body]
    else:
        cmd = ["notify-send", "--app-name=GitHub Inbox", "-u", "critical" if urgent else "normal",
               title, body]
    kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if WINDOWS else {}
    try:
        subprocess.run(cmd, check=False, timeout=20, env=env, **kwargs)
    except (OSError, subprocess.TimeoutExpired):
        pass


# ---- one sync at a time -----------------------------------------------------

@contextmanager
def try_lock(path):
    """Yield True if this process holds the lock file, False if another one holds it."""
    with open(path, "a+") as f:
        if WINDOWS:
            f.seek(0)
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                yield False
                return
            try:
                yield True
            finally:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            yield True


# ---- one daemon at a time ---------------------------------------------------

class ExclusiveHTTPServer(ThreadingHTTPServer):
    """A second daemon must fail to bind the port, so that no pop-up comes twice.

    On Windows, SO_REUSEADDR lets two processes bind the same port. Use
    SO_EXCLUSIVEADDRUSE there instead.
    """

    allow_reuse_address = not WINDOWS

    def server_bind(self):
        if WINDOWS:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()
