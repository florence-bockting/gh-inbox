"""The parts that differ between Linux, macOS and Windows.

Only the Linux branch is tested. The macOS and Windows branches are untested.
"""

import os
import plistlib
import shutil
import socket
import subprocess
import sys
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path

WINDOWS = sys.platform == "win32"
MACOS = sys.platform == "darwin"

if WINDOWS:
    import msvcrt
else:
    import fcntl

# The command that starts the daemon. It runs inside the current (virtual) environment.
DAEMON_ARGS = [sys.executable, "-m", "ghinbox", "daemon"]

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


# ---- start at login ---------------------------------------------------------

def autostart_path():
    if WINDOWS:
        return (Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup"
                / "gh-inbox.vbs")
    if MACOS:
        return Path.home() / "Library/LaunchAgents/io.github.gh-inbox.plist"
    return Path.home() / ".config/autostart/gh-inbox.desktop"


def install_autostart(log_dir):
    """Write the login entry. Return a hint that tells how to start the daemon now."""
    path = autostart_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if WINDOWS:
        # pythonw.exe runs without a console window. Window style 0 hides it as well.
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        command = f'""{pythonw}"" -m ghinbox daemon'
        path.write_text(f'CreateObject("WScript.Shell").Run "{command}", 0, False\r\n')
        return f'Run "{path}" to start it now.'
    if MACOS:
        # A login agent does not get the shell PATH. Add the folder of gh to it.
        dirs = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"]
        gh = shutil.which("gh")
        if gh:
            dirs.insert(0, str(Path(gh).parent))
        plist = {
            "Label": "io.github.gh-inbox",
            "ProgramArguments": DAEMON_ARGS,
            "RunAtLoad": True,
            "EnvironmentVariables": {"PATH": ":".join(dict.fromkeys(dirs))},
            "StandardErrorPath": str(Path(log_dir) / "daemon.err"),
        }
        with open(path, "wb") as f:
            plistlib.dump(plist, f)
        return f"Run `launchctl load {path}` to start it now."
    path.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=GitHub Inbox poller\n"
        "Comment=Syncs GitHub notifications and sends reminders\n"
        f"Exec={' '.join(DAEMON_ARGS)}\n"
        "NoDisplay=true\n"
        "X-GNOME-Autostart-enabled=true\n")
    return "Run `gh-inbox daemon &` to start it now."


def remove_autostart():
    path = autostart_path()
    if MACOS and path.exists():
        subprocess.run(["launchctl", "unload", str(path)], check=False)
    path.unlink(missing_ok=True)
    return path


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
