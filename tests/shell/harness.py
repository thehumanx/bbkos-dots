"""A separate bbkOS shell for tests: a nested Hyprland and the repo's Quickshell in a temp home (layer 2 of
docs/specs/2026-10-29-shell-tests-design.md; how to use it: docs/modules/shell-tests.md).

    shell = TestShell().start(settings={"shell": {"barPosition": "bottom"}})
    shell.ipc("panel", "toggle", "battery")
    shell.stop()

Nothing of the owner's home is read or written: settings are the built-in defaults (plus the test's), the theme is
rendered into the temp home by the repo's bbkos-theme, and commands that would act on the machine are stand-ins
(stub.sh) that log to $HOME/calls.log. What the shell does over D-Bus directly (Wi-Fi, Bluetooth, volume, power
profile, notifications) cannot be stood in for: tests must not trigger those actions.
"""
import atexit
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHELL_DIR = ROOT / "dotfiles/quickshell/.config/quickshell"
REPO_BIN = ROOT / "dotfiles/bin/.local/bin"
LOCK_AVATAR = ROOT / "dotfiles/hypr/.config/hypr/lock-avatar.png"           # the default avatar the Lock screen page shows
MATUGEN_TOML = ROOT / "dotfiles/bbkos-settings/.config/bbkos/matugen.toml"     # the palette engine's config (repo, not owner)
HERE = Path(__file__).resolve().parent
CONFIG = HERE / "hyprland-test.lua"
STUB = HERE / "stub.sh"
RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
SPECIAL = "special:shelltest"              # the live workspace the nested window opens on, without focus
READY_S = 15

# Commands the test shell (and bbkos-theme run inside it) must not run for real.
# The startup inventory (2026-10-29: every Process and execDetached in services/ and modules/) found nothing else that
# acts on the machine at start; bbkos-camera (preview and tune on the Camera page: the real webcam), checkupdates (the
# Updates service: network) and adb (the Android window) act on later triggers the tests reach.
STUBBED = ("sudo", "systemctl", "loginctl", "brightnessctl", "ddcutil", "bbkos-brightness", "nmcli", "bluetoothctl",
           "wpctl", "rfkill", "hyprlock", "bbkos-lock", "gsettings", "dconf", "hyprsunset", "notify-send", "uwsm",
           "bbkos-camera", "checkupdates", "adb", "bbkos-power-apply", "bbkos-logind-apply", "v4l2-ctl")
HOME_PREFIX = str(Path(tempfile.gettempdir()) / "bbkos-shelltest-")

# Stand-ins the shell calls by itself at start (test_start checks nothing else appears): the power helper (PowerTuning
# runs it at login) and the update check (Updates).
ALLOWED_AT_START = frozenset({"bbkos-power-apply", "checkupdates"})

# WARN lines a test shell is expected to print: the live shell owns these D-Bus services.
EXPECTED_WARNINGS = [
    re.compile(r"Could not register notification server"),
    re.compile(r"Registration will be attempted again if the active service is unregistered"),
    re.compile(r"An authentication agent already exists"),
    re.compile(r"failed to register listener on path \"/org/quickshell/PolkitAgent\""),
    # Qt's text-input bookkeeping when a popup with a text field (timer, Wi-Fi password) closes; the live shell logs it too
    re.compile(r"QWaylandTextInputv3::disableSurface"),
    # a fresh home has no screen-time file yet: the first read fails once, as on a first login
    re.compile(r"ScreenTime\.qml\[\d+:\d+\]: Read of .*/screentime\.json failed: File does not exist"),
]
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def unexpected_warnings(log: str) -> list:
    """The WARN lines of a shell log that are not in EXPECTED_WARNINGS."""
    out = []
    for line in ANSI.sub("", log).splitlines():
        if "WARN" in line and not any(p.search(line) for p in EXPECTED_WARNINGS):
            out.append(line.strip())
    return out


def _locked() -> bool:
    return subprocess.run(["pgrep", "-x", "hyprlock"], capture_output=True).returncode == 0


def session_reason() -> str:
    """Why the live layer cannot run here, or "" when it can."""
    if not os.environ.get("WAYLAND_DISPLAY") or not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return "no Hyprland session"
    for b in ("Hyprland", "hyprctl", "quickshell", "qs", "grim"):
        if not shutil.which(b):
            return f"{b} not installed"
    if _locked():
        return "the screen is locked (hyprlock running)"
    return ""


def skip_unless_session():
    reason = session_reason()
    return unittest.skipIf(reason != "", reason)


def nested_pids() -> list:
    """PIDs of nested Hyprlands started exactly as `Hyprland -c <test config>` (ours or left over from a crashed run)."""
    want = ["Hyprland", "-c", str(CONFIG)]
    out = []
    for pid in subprocess.run(["pgrep", "-x", "Hyprland"], capture_output=True, text=True).stdout.split():
        try:
            argv = Path(f"/proc/{pid}/cmdline").read_bytes().rstrip(b"\0").split(b"\0")
        except OSError:
            continue
        if [a.decode(errors="replace") for a in argv] == want:
            out.append(int(pid))
    return out


def processes_with_home(prefix: str) -> list:
    """PIDs of this user's processes whose HOME starts with prefix (a test home, or all test homes)."""
    out = []
    for d in Path("/proc").iterdir():
        if not d.name.isdigit() or int(d.name) == os.getpid():
            continue
        try:
            if d.stat().st_uid != os.getuid():
                continue
            env = (d / "environ").read_bytes().split(b"\0")
        except OSError:
            continue
        if any(e.startswith(b"HOME=" + prefix.encode()) for e in env):
            out.append(int(d.name))
    return out


def _kill_group(pid: int, wait_s: float = 5.0) -> None:
    """TERM, then KILL, the process group led by pid (the shell and its children, or the nested Hyprland's)."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pid, sig)
        except (ProcessLookupError, PermissionError):
            return
        end = time.monotonic() + wait_s
        while time.monotonic() < end:
            try:
                os.killpg(pid, 0)
            except (ProcessLookupError, PermissionError):
                return
            time.sleep(0.05)


def sweep_leftovers() -> None:
    """Remove what a crashed or interrupted run left: nested Hyprlands with the test config, and every process whose
    HOME is a test home (the test Quickshell and its children, such as the camera watcher's inotifywait)."""
    for pid in nested_pids():
        _kill(pid)
    for pid in processes_with_home(HOME_PREFIX):
        _kill(pid, 2.0)


# Every started TestShell until it is stopped: stopped at interpreter exit (also after Ctrl-C) and on SIGTERM
# (`timeout ... python3 -m unittest` sends it), so an interrupted run leaves nothing behind.
_LIVE = set()


def _stop_all() -> None:
    for shell in list(_LIVE):
        shell.stop()


def _on_sigterm(signum, frame):
    _stop_all()
    raise SystemExit(128 + signum)


atexit.register(_stop_all)
if signal.getsignal(signal.SIGTERM) in (signal.SIG_DFL, None):
    signal.signal(signal.SIGTERM, _on_sigterm)


def _kill(pid: int, wait_s: float = 5.0) -> None:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            return
        end = time.monotonic() + wait_s
        while time.monotonic() < end:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.05)


def start_compositor_for_test_only() -> subprocess.Popen:
    """A bare nested Hyprland with the test config (test_start uses it to stand for a leftover of a crashed run), moved
    out of sight and with the focus given back, as the harness does."""
    focused = _active_window()
    _rule_hidden()
    p = subprocess.Popen(["Hyprland", "-c", str(CONFIG)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    end = time.monotonic() + READY_S
    while time.monotonic() < end and not (_window_of(p.pid) and _instance_of(p.pid)):
        time.sleep(0.1)
    _hide(p.pid, focused)
    return p


def _dispatch(lua: str) -> None:
    """A Hyprland 0.56 dispatcher (Lua: `hl.dsp...`); raises unless hyprctl answers "ok". (The old `hyprctl dispatch
    name args` form only prints a Lua error, which went unnoticed here until 2026-10-29.)"""
    r = subprocess.run(["hyprctl", "dispatch", lua], capture_output=True, text=True, timeout=5)
    if r.stdout.strip() != "ok":
        raise RuntimeError(f"hyprctl dispatch {lua}: {(r.stdout or r.stderr).strip()}")


def _rule_hidden() -> None:
    """A runtime window rule on the live Hyprland: a nested Hyprland's window (class aquamarine) opens on the hidden
    workspace without the focus. Without it the window mapped on the owner's workspace and took the focus for ~65 ms
    before _hide moved it, so the owner's tiled windows split and snapped back on every test start (seen as a flicker,
    2026-10-31). Added again each time: a config reload drops runtime rules; the old handle is disabled first."""
    lua = ('if BBKOS_SHELLTEST then BBKOS_SHELLTEST:set_enabled(false) end; '
           'BBKOS_SHELLTEST = hl.window_rule({ name = "bbkos-shelltest", match = { class = "^aquamarine$" }, '
           f'workspace = "{SPECIAL} silent", no_initial_focus = true }})')
    r = subprocess.run(["hyprctl", "eval", lua], capture_output=True, text=True, timeout=5)
    if r.stdout.strip() != "ok":
        raise RuntimeError(f"hyprctl eval (shell-test window rule): {(r.stdout or r.stderr).strip()}")


def _hide(pid: int, focused: str) -> None:
    """Move a nested Hyprland's window to the hidden workspace and, only if it holds the focus, give the focus back to
    the window that had it (the owner may be using the desktop: never move the focus otherwise)."""
    _dispatch(f'hl.dsp.window.move({{ workspace = "{SPECIAL}", window = "pid:{pid}", follow = false }})')
    for _ in range(3):                                     # the window can take the focus a moment after it maps
        if _active_pid() != pid:
            time.sleep(0.2)
            if _active_pid() != pid:
                return
        if focused:
            _dispatch(f'hl.dsp.focus({{ window = "address:{focused}" }})')


def _instance_of(pid: int):
    """(Wayland socket, instance signature) of the Hyprland with this pid, from `hyprctl instances -j`, or None."""
    r = subprocess.run(["hyprctl", "instances", "-j"], capture_output=True, text=True, timeout=5)
    try:
        for i in json.loads(r.stdout):
            if i.get("pid") == pid and i.get("wl_socket") and i.get("instance"):
                return i["wl_socket"], i["instance"]
    except ValueError:
        pass
    return None


def _active_window() -> str:
    """The live session's focused window address, or ""."""
    r = subprocess.run(["hyprctl", "activewindow", "-j"], capture_output=True, text=True, timeout=5)
    try:
        return json.loads(r.stdout).get("address", "") or ""
    except ValueError:
        return ""


def _active_pid() -> int:
    """The pid of the live session's focused window, or 0."""
    r = subprocess.run(["hyprctl", "activewindow", "-j"], capture_output=True, text=True, timeout=5)
    try:
        return int(json.loads(r.stdout).get("pid", 0) or 0)
    except (ValueError, TypeError):
        return 0


def _window_of(pid: int) -> bool:
    """True once the live session has a window for this process (the nested Hyprland's)."""
    r = subprocess.run(["hyprctl", "clients", "-j"], capture_output=True, text=True, timeout=5)
    try:
        return any(c.get("pid") == pid for c in json.loads(r.stdout))
    except ValueError:
        return False


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


class TestShell:
    """A test shell. Either `shell = TestShell().start(...)` with `shell.stop()` in a cleanup, or
    `with TestShell(settings=..., remove=...) as shell:`, which starts it and always stops it."""

    def __init__(self, visible: bool = False, settings: dict | None = None, remove=()):
        self._with_settings = settings
        self._with_remove = remove
        # visible=True leaves the nested window on the owner's screen: a hidden nested Hyprland does not draw (no frame
        # callbacks from the live compositor), so only a visible one can be screenshotted. Opt-in tests only.
        self.visible = visible
        self.home = None
        self.wayland = None
        self.signature = None
        self.pid = None
        self.hypr_pid = None
        self._proc = None
        self._hypr = None
        self._logf = None

    def __enter__(self) -> "TestShell":
        return self.start(settings=self._with_settings, remove=self._with_remove)

    def __exit__(self, *exc) -> bool:
        self.stop()
        return False                                          # an error in the block still propagates

    # ---- environment ----
    def _env(self, extra=None) -> dict:
        env = {
            "HOME": str(self.home),
            "PATH": f"{self.home / 'stubs'}:{REPO_BIN}:/usr/local/bin:/usr/bin:/bin",
            "XDG_RUNTIME_DIR": str(RUNTIME),
            "LANG": "C.UTF-8",
            "BBKOS_POWER_HELPER": str(self.home / "stubs/bbkos-power-apply"),
            "BBKOS_LOGIND_HELPER": str(self.home / "stubs/bbkos-logind-apply"),
            "BBKOS_KITTY_COMM": "bbkos-shelltest-no-kitty",      # bbkos-theme's kitty reload signals no real kitty
            "BBKOS_CLIP_DIR": str(self.home / "clip"),           # the clipboard picker empties its folder: not the live one
        }
        if os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
            env["DBUS_SESSION_BUS_ADDRESS"] = os.environ["DBUS_SESSION_BUS_ADDRESS"]
        if self.wayland:
            env.update(WAYLAND_DISPLAY=self.wayland, HYPRLAND_INSTANCE_SIGNATURE=self.signature, QT_QPA_PLATFORM="wayland")
        env.update(extra or {})
        return env

    def _make_home(self, settings, remove=()):
        self.home = Path(tempfile.mkdtemp(prefix="bbkos-shelltest-"))
        stubs = self.home / "stubs"
        stubs.mkdir()
        for name in STUBBED:
            (stubs / name).symlink_to(STUB)
        (self.home / ".local").mkdir()
        (self.home / ".local/bin").symlink_to(REPO_BIN)
        cfg = self.home / ".config/bbkos"
        cfg.mkdir(parents=True)
        shutil.copy(MATUGEN_TOML, cfg / "matugen.toml")
        (self.home / ".config/hypr").mkdir()
        (self.home / ".config/hypr/lock-avatar.png").symlink_to(LOCK_AVATAR)
        env = self._env()
        out = subprocess.run([str(REPO_BIN / "bbkos-theme"), "defaults"], env=env, capture_output=True, text=True,
                             timeout=30, check=True).stdout
        merged = _deep_merge(json.loads(out)["defaults"], settings or {})
        for key in remove:                                       # "section.key": as if an older settings.json lacked it
            section, name = key.split(".", 1)
            merged.get(section, {}).pop(name, None)
        (cfg / "settings.json").write_text(json.dumps(merged, indent=2))
        state = self.home / ".local/state/bbkos/theme"
        state.mkdir(parents=True)
        r = subprocess.run([str(REPO_BIN / "bbkos-theme"), "apply", "--out-dir", str(state)], env=env,
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            raise RuntimeError("bbkos-theme apply for the test home failed: " + (r.stderr or r.stdout).strip())

    # ---- compositor ----
    def _start_compositor(self):
        """Start the nested Hyprland, then (unless visible) move its window to a hidden special workspace and give the
        focus back if it took it. Hidden, it does not draw: the shell runs and answers IPC, but screen capture hangs
        (checked 2026-10-29, also with a headless output inside it and with render_unfocused on the window)."""
        focused = _active_window()                              # before the leftover sweep, which can move the focus
        sweep_leftovers()
        _rule_hidden()
        self._hypr = subprocess.Popen(["Hyprland", "-c", str(CONFIG)], stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
        self.hypr_pid = self._hypr.pid
        end = time.monotonic() + READY_S
        while time.monotonic() < end:
            inst = _instance_of(self.hypr_pid)                  # matched by pid: never the live or another instance
            if inst and _window_of(self.hypr_pid):
                self.wayland, self.signature = inst
                if not self.visible:
                    _hide(self.hypr_pid, focused)
                return
            if self._hypr.poll() is not None:
                break
            time.sleep(0.1)
        raise RuntimeError("the nested Hyprland did not come up")

    # ---- shell ----
    def start(self, settings: dict | None = None, remove=()) -> "TestShell":
        _LIVE.add(self)
        try:
            self._make_home(settings, remove)
            self._start_compositor()
            self._logf = open(self.home / "shell.log", "w")
            self._proc = subprocess.Popen(["quickshell", "--path", str(SHELL_DIR)], env=self._env(),
                                          stdout=self._logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                          start_new_session=True)       # its own group: stop() kills its children too
            self.pid = self._proc.pid
            end = time.monotonic() + READY_S
            while time.monotonic() < end:
                if self._proc.poll() is not None:
                    raise RuntimeError("the test shell exited:\n" + self.log())
                r = subprocess.run(["qs", "ipc", "--pid", str(self.pid), "show"], env=self._env(),
                                   capture_output=True, text=True, timeout=5)
                if "target panel" in r.stdout:
                    return self
                time.sleep(0.2)
            raise RuntimeError("the test shell did not answer on IPC:\n" + self.log())
        except BaseException:
            self.stop()
            raise

    def stop(self) -> None:
        """Kill the shell's process group, the nested Hyprland's, anything still running with this test home, then
        remove the home and the nested instance's runtime directory. Each step runs even if one before it fails."""
        _LIVE.discard(self)
        steps = []
        if self._proc is not None:
            steps.append(lambda: _kill_group(self._proc.pid))
            steps.append(lambda: self._proc.wait(timeout=10))
        if self.hypr_pid:
            steps.append(lambda: _kill_group(self.hypr_pid))
            if self._hypr is not None:
                steps.append(lambda: self._hypr.wait(timeout=10))
        if self.home:
            home = str(self.home)
            steps.append(lambda: [_kill(p, 2.0) for p in processes_with_home(home)])
        if self._logf:
            steps.append(self._logf.close)
        if self.home:
            steps.append(lambda: shutil.rmtree(self.home, ignore_errors=True))
        if self.signature:
            steps.append(lambda: shutil.rmtree(RUNTIME / "hypr" / self.signature, ignore_errors=True))
        for step in steps:
            try:
                step()
            except Exception:
                pass
        self._proc = self._logf = self.hypr_pid = self._hypr = None
        self.signature = self.wayland = None

    # ---- driving ----
    def ipc(self, target: str, fn: str, *args: str) -> str:
        r = subprocess.run(["qs", "ipc", "--pid", str(self.pid), "call", target, fn, *args], env=self._env(),
                           capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            raise RuntimeError(f"qs ipc call {target} {fn} {' '.join(args)}: {r.stderr.strip()}")
        return r.stdout.strip()

    def log(self) -> str:
        p = self.home / "shell.log" if self.home else None
        return p.read_text(errors="replace") if p and p.exists() else ""

    def calls(self) -> list:
        p = self.home / "calls.log"
        return p.read_text().splitlines() if p.exists() else []

    def screenshot(self, path: str) -> None:
        subprocess.run(["grim", path], env=self._env(), capture_output=True, timeout=10, check=True)

    def set(self, key: str, value: str) -> None:
        subprocess.run([str(REPO_BIN / "bbkos-theme"), "set", key, value], env=self._env(), capture_output=True,
                       text=True, timeout=60, check=True)
