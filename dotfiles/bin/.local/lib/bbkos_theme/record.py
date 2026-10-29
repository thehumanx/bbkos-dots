"""bbkos-record: screen recording with gpu-screen-recorder (docs/modules/capture.md).

Pure helpers first (options, region, command line: unit-tested), then the process side: pick the area, start the
recorder under a small detached supervisor, stop it with SIGINT (the only way gpu-screen-recorder finalises the file),
and tell the desktop when the file is ready. State lives in $XDG_RUNTIME_DIR/bbkos-record/state.json: written when the
recorder has created its file, removed by the supervisor when the recorder ends for any reason. The shell watches that
file for the bar's recording indicator. Adapted from Omarchy's omarchy-capture-screenrecording (same recorder, same
slurp picker, same webcam-overlay idea) without its HDR/portal/wf-recorder fallbacks.
"""
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from . import settings as S

USAGE = """\
usage: bbkos-record COMMAND [OPTIONS]
  start  [--region|--screen] [--audio none|desktop|mic|both] [--camera|--no-camera]   pick the area, then record
  stop                                                                                finish and save
  toggle [same options as start]                                                      stop if recording, else start
  status                                                                              JSON; exit 0 only while recording
  camera [next|tl|tr|bl|br]                                                           move the camera window to a corner
Options not given come from the capture.record* settings (bbkos-theme status / the Capture page)."""

AUDIO_SOURCES = {"none": [], "desktop": ["default_output"], "mic": ["default_input"],
                 "both": ["default_output", "default_input"]}
CAMERA_GEOMETRY = {"small": (240, 180), "medium": (320, 240), "large": (480, 360)}   # 4:3, the camera's native 640x480
CAMERA_CLASS = "bbkos-camera"
CAMERA_MARGIN = 24
READY_TIMEOUT = 10.0
QUICK_TIMEOUT = 5.0


def run_quick(cmd, timeout=QUICK_TIMEOUT):
    """subprocess.run for short best-effort calls (hyprctl dispatch, systemctl, device lists), output captured as text.
    A hang gives a failed result (returncode 124, empty output) instead of blocking the whole command; a missing
    binary still raises, as before."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "timed out")
MIN_FREE_BYTES = 2 * 1024 ** 3         # a very_high 60 fps recording writes about 1 GB a minute: do not start on a nearly full disk


class RecordError(Exception):
    """A failure with a message for stderr; the exit code is 1, or args[1] when given (help: 0, usage mistakes: 2)."""


# ---------------------------------------------------------------- pure helpers

def expand_dir(value):
    return Path(os.path.expanduser(value))


def options(settings, overrides=None):
    """The recording options: the capture.record* settings, then any command-line overrides (None = not given)."""
    c = settings["capture"]
    opts = {"area": c["recordArea"], "audio": c["recordAudio"], "camera": c["recordCamera"],
            "cameraSize": c["recordCameraSize"], "cameraMirror": c["recordCameraMirror"], "quality": c["recordQuality"], "fps": c["recordFps"],
            "directory": expand_dir(c["recordDirectory"])}
    for k, v in (overrides or {}).items():
        if v is not None:
            opts[k] = v
    return opts


def region_from_slurp(text):
    """slurp prints "X,Y WxH" (logical pixels, may be negative on a monitor left of or above the origin); the recorder
    wants "WxH+X+Y". Returns None for anything else (a cancelled pick prints nothing)."""
    m = re.fullmatch(r"\s*(-?\d+),(-?\d+) (\d+)x(\d+)\s*", text or "")
    if not m:
        return None
    x, y, w, h = (int(g) for g in m.groups())
    if w < 2 or h < 2:
        return None
    return f"{w}x{h}+{x}+{y}"


def build_command(opts, target, output):
    """The gpu-screen-recorder argv. target = a monitor name, or ("region", "WxH+X+Y"). 60 fps constant frame rate
    (editors and players like it), H.264/HEVC by the recorder's own choice (-k auto), CPU encoding only as a fallback."""
    if isinstance(target, tuple):
        capture = ["-w", "region", "-region", target[1]]
    else:
        capture = ["-w", target]
    cmd = ["gpu-screen-recorder", *capture, "-k", "auto", "-f", str(opts["fps"]), "-fm", "cfr",
           "-q", opts["quality"], "-fallback-cpu-encoding", "yes", "-o", str(output)]
    sources = AUDIO_SOURCES[opts["audio"]]
    if sources:
        # one merged track: players such as mpv play separate tracks one at a time
        cmd += ["-a", "|".join(sources), "-ac", "aac"]
    return cmd


def output_path(directory, now=None):
    return Path(directory) / ("screenrecording-" + (now or datetime.now()).strftime("%Y-%m-%d_%H-%M-%S") + ".mp4")


def camera_corner(area, size, margin=CAMERA_MARGIN):
    """Top-left of the camera window: the bottom-right corner of the recorded area (x, y, w, h in logical pixels)."""
    ax, ay, aw, ah = area
    return ax + aw - size[0] - margin, ay + ah - size[1] - margin


CORNERS = ("br", "bl", "tl", "tr")                     # the order "next" walks through


def corner_position(area, size, corner, margin=CAMERA_MARGIN):
    """Top-left of a camera window of `size` in `corner` (br, bl, tl, tr) of the area (x, y, w, h)."""
    ax, ay, aw, ah = area
    x = ax + margin if corner in ("bl", "tl") else ax + aw - size[0] - margin
    y = ay + margin if corner in ("tl", "tr") else ay + ah - size[1] - margin
    return x, y


def nearest_corner(area, rect):
    """Which corner of the area the camera window (x, y, w, h) is closest to."""
    ax, ay, aw, ah = area
    cx, cy = rect[0] + rect[2] / 2, rect[1] + rect[3] / 2
    right, bottom = cx > ax + aw / 2, cy > ay + ah / 2
    return ("b" if bottom else "t") + ("r" if right else "l")


def next_corner(current):
    return CORNERS[(CORNERS.index(current) + 1) % len(CORNERS)] if current in CORNERS else CORNERS[0]


def runtime_dir(env=None):
    env = os.environ if env is None else env
    base = env.get("XDG_RUNTIME_DIR") or os.path.join(env.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "bbkos")
    return Path(base) / "bbkos-record"


def _is_recorder(pid):
    try:
        exe = os.readlink(f"/proc/{int(pid)}/exe")
    except (OSError, ValueError):
        return False
    return os.path.basename(exe.removesuffix(" (deleted)")) == "gpu-screen-recorder"


def read_state(rt):
    """The state while a recording really runs, else None (a state file whose recorder is gone is removed)."""
    path = rt / "state.json"
    try:
        st = json.loads(path.read_text())
        pid = int(st["recorder"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if _is_recorder(pid):
        return st
    try:
        path.unlink()
    except OSError:
        pass
    return None


def _write_state(rt, st):
    tmp = rt / "state.json.tmp"
    tmp.write_text(json.dumps(st))
    os.replace(tmp, rt / "state.json")


# ---------------------------------------------------------------- process side

def _notify(summary, body="", image=None, command=None, urgency="normal", timeout=5000):
    args = ["omarchy-notification-send", "-g", "", "--app-name", "bbkos-record", "-t", str(timeout), "-u", urgency, summary, body]
    if image:
        args += ["--image", str(image)]
    if command:
        args += ["--exec", *command]
    try:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass


def _tell_shell():
    """Let Quickshell re-read the recording state (the bar's indicator and the options panel). Best effort."""
    try:
        subprocess.Popen(["qs", "ipc", "call", "record", "changed"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except OSError:
        pass


def _hypr_json(what):
    try:
        out = subprocess.run(["hyprctl", what, "-j"], capture_output=True, text=True, timeout=5).stdout
        return json.loads(out)
    except (OSError, ValueError, subprocess.SubprocessError):
        return []


def focused_monitor():
    for m in _hypr_json("monitors"):
        if m.get("focused"):
            return m
    mons = _hypr_json("monitors")
    return mons[0] if mons else None


def pick_target(area):
    """(target, (x, y, w, h)) for the recorder and for the camera corner; None when the pick is cancelled."""
    mon = focused_monitor()
    if mon is None:
        raise RecordError("no monitor found (is Hyprland running?)")
    if area == "screen":
        w, h = int(mon["width"] / mon["scale"]), int(mon["height"] / mon["scale"])
        return mon["name"], (int(mon["x"]), int(mon["y"]), w, h)
    try:
        # BBKOS_RECORD_REGION="X,Y WxH" replaces the picker (a test hook: nobody can drag a region in a script).
        picked = os.environ.get("BBKOS_RECORD_REGION") or subprocess.run(["slurp", "-d"], capture_output=True, text=True).stdout
    except OSError as e:
        raise RecordError(f"cannot run slurp: {e}") from e
    geometry = region_from_slurp(picked)
    if geometry is None:
        return None                                   # Esc: not an error
    m = re.fullmatch(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", geometry)
    w, h, x, y = (int(g) for g in m.groups())
    return ("region", geometry), (x, y, w, h)


def _camera_device():
    for line in run_quick(["gpu-screen-recorder", "--list-v4l2-devices"]).stdout.splitlines():
        dev = line.split("|")[0]
        if dev.startswith("/dev/video"):
            return dev
    return None


def _camera_client():
    for c in _hypr_json("clients"):
        if c.get("class") == CAMERA_CLASS:
            return c
    return None


def _move_window(address, x, y):
    sel = f'window = "address:{address}"'
    run_quick(["hyprctl", "dispatch", f"hl.dsp.window.move({{ x = {int(x)}, y = {int(y)}, relative = false, {sel} }})"])


def camera_move(which):
    """Put the camera window in a corner of the recorded area: tl, tr, bl, br, or next (the following corner). The window
    can also be dragged by hand (it is an ordinary floating window; Super+drag works too); this is the keyboard way."""
    st = read_state(runtime_dir())
    if not st or not st.get("camera"):
        raise RecordError("no recording with a camera is running", 1)
    win = _camera_client()
    if win is None:
        raise RecordError("the camera window is not open", 1)
    area = tuple(st["rect"])
    size = tuple(win["size"])
    current = nearest_corner(area, (*win["at"], *win["size"]))
    corner = next_corner(current) if which == "next" else which
    x, y = corner_position(area, size, corner)
    _move_window(win["address"], x, y)
    return 0


def camera_command(dev, size, mirror):
    """The mpv argv for the camera window. Mirrored (the default) like a video-call preview: lift your right hand and the
    right side of the picture moves; the recording shows it that way too."""
    w, h = size
    return ["mpv", f"av://v4l2:{dev}", "--profile=low-latency", "--untimed", "--no-cache",
            "--demuxer-lavf-o=video_size=640x480,framerate=30", f"--geometry={w}x{h}", "--no-border", "--no-audio",
            "--no-osc", "--osd-level=0", f"--title={CAMERA_CLASS}", f"--wayland-app-id={CAMERA_CLASS}", "--really-quiet",
            *(["--vf=hflip"] if mirror else [])]


def start_camera(size_name, area, mirror=True):
    """A small always-on-top camera window (mpv) in the recorded area's bottom-right corner, so it is part of the
    video. Returns the mpv process, or None (with a notification) when there is no camera."""
    dev = _camera_device()
    if dev is None:
        _notify("No camera found", "Recording without it.", urgency="critical", timeout=3000)
        return None
    w, h = CAMERA_GEOMETRY[size_name]
    try:
        active = json.loads(subprocess.run(["hyprctl", "activewindow", "-j"], capture_output=True, text=True, timeout=5).stdout)
        before = active.get("address") if isinstance(active, dict) else None
    except (OSError, ValueError, subprocess.SubprocessError):
        before = None
    proc = subprocess.Popen(
        camera_command(dev, (w, h), mirror),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    win = None
    for _ in range(60):                               # wait (3 s at most) for the window to map
        win = _camera_client()
        if win or proc.poll() is not None:
            break
        time.sleep(0.05)
    if win:
        address = win["address"]
        sel = f'window = "address:{address}"'
        # The window rule (hyprland.lua) floats and pins it. float and pin are TOGGLES: send them only when the rule
        # did not apply (another config), never on top of it.
        if not win.get("floating"):
            run_quick(["hyprctl", "dispatch", f"hl.dsp.window.float({{ {sel} }})"])
        if not win.get("pinned"):
            run_quick(["hyprctl", "dispatch", f"hl.dsp.window.pin({{ {sel} }})"])
        x, y = camera_corner(area, (w, h))
        _move_window(address, x, y)
        time.sleep(0.5)                               # let the window settle before the recording starts
        if before:                                    # mpv took the keyboard focus when it opened: hand it back
            run_quick(["hyprctl", "dispatch", f'hl.dsp.focus({{ window = "address:{before}" }})'])
    return proc


def stop_camera(proc):
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(3)
        except subprocess.TimeoutExpired:
            proc.kill()


def _thumbnail(video, out):
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "quiet", "-ss", "0.5", "-i", str(video), "-frames:v", "1",
                        "-vf", "scale=720:-1", str(out)], timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return out if Path(out).exists() else None


def _supervise(rt, cmd, output, camera, opts, area):
    """Runs in the detached child: start the recorder, publish the state, wait, clean up, notify."""
    log = open(rt / "gsr.log", "ab")
    log.write(f"\n===== {datetime.now():%F %T} {' '.join(cmd)}\n".encode())
    log.flush()
    rec = subprocess.Popen(cmd, stdout=log, stderr=log, start_new_session=True)
    waited = 0.0
    while rec.poll() is None and not output.exists() and waited < READY_TIMEOUT:
        time.sleep(0.1)
        waited += 0.1
    if rec.poll() is not None or not output.exists():
        if rec.poll() is None:
            rec.send_signal(signal.SIGINT)
            rec.wait(5)
        stop_camera(camera)
        tail = (rt / "gsr.log").read_text(errors="replace").strip().splitlines()[-1:] or [""]
        _notify("Recording failed", tail[0][:200], urgency="critical", timeout=8000)
        output.unlink(missing_ok=True)
        return 1
    _write_state(rt, {"recorder": rec.pid, "supervisor": os.getpid(), "file": str(output), "started": time.time(),
                      "area": opts["area"], "rect": list(area), "audio": opts["audio"], "camera": camera is not None})
    _tell_shell()
    rec.wait()                                        # SIGINT from `stop` makes it finalise the file and exit 0
    (rt / "state.json").unlink(missing_ok=True)
    _tell_shell()
    stop_camera(camera)
    if output.exists() and output.stat().st_size > 0:
        thumb = _thumbnail(output, rt / "thumb.png")
        _notify("Recording saved", "Click to play", image=thumb, command=["xdg-open", str(output)], timeout=10000)
    else:
        _notify("Recording failed", "No video was written.", urgency="critical", timeout=8000)
    return 0


def start(opts):
    rt = runtime_dir()
    rt.mkdir(parents=True, exist_ok=True, mode=0o700)
    if read_state(rt):
        print("already recording", file=sys.stderr)
        return 1
    for tool in ("gpu-screen-recorder", "slurp" if opts["area"] == "region" else "hyprctl"):
        if shutil.which(tool) is None:
            raise RecordError(f"{tool} is not installed")
    if opts["camera"] and shutil.which("mpv") is None:
        raise RecordError("mpv is not installed (needed for the camera overlay)")
    picked = pick_target(opts["area"])
    if picked is None:
        return 0
    target, area = picked
    directory = Path(opts["directory"])
    directory.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(directory).free
    if free < MIN_FREE_BYTES:
        raise RecordError(f"only {free // 1024 ** 2} MiB free in {directory}: free some space before recording")
    output = output_path(directory)
    cmd = build_command(opts, target, output)
    pid = os.fork()
    if pid:                                           # the caller: wait until the recording is really running
        deadline = time.time() + READY_TIMEOUT + 8
        while time.time() < deadline:
            st = read_state(rt)
            if st:
                return 0
            time.sleep(0.1)
        return 1
    os.setsid()                                       # the supervisor: detached from the key press, the panel and the shell
    for fd in (0, 1, 2):
        os.close(fd)
    os.open(os.devnull, os.O_RDWR)
    os.dup2(0, 1)
    os.dup2(0, 2)
    camera = start_camera(opts["cameraSize"], area, opts["cameraMirror"]) if opts["camera"] else None
    os._exit(_supervise(rt, cmd, output, camera, opts, area))


def stop():
    rt = runtime_dir()
    st = read_state(rt)
    if not st:
        print("not recording", file=sys.stderr)
        return 1
    os.kill(int(st["recorder"]), signal.SIGINT)
    for _ in range(100):                              # the supervisor removes the state once the file is finalised
        if not (rt / "state.json").exists():
            return 0
        time.sleep(0.1)
    return 0


def status():
    st = read_state(runtime_dir())
    out = {"recording": bool(st)}
    if st:
        out.update(file=st["file"], started=st["started"], area=st["area"], rect=st.get("rect"), audio=st["audio"],
                   camera=st["camera"])
    print(json.dumps(out))
    return 0 if st else 1


def parse(args):
    """-> (command, overrides). Raises RecordError on bad input."""
    if args and args[0] in ("-h", "--help", "help"):
        raise RecordError(USAGE, 0)
    if not args:
        raise RecordError(USAGE)
    cmd, rest, ov = args[0], args[1:], {}
    if cmd == "camera":
        if len(rest) > 1 or (rest and rest[0] not in ("next", "tl", "tr", "bl", "br")):
            raise RecordError(f"bad option {' '.join(rest)!r}\n{USAGE}")
        return cmd, {"corner": rest[0] if rest else "next"}
    if cmd not in ("start", "stop", "toggle", "status"):
        raise RecordError(f"unknown command {cmd!r}\n{USAGE}")
    i = 0
    while i < len(rest):
        a = rest[i]
        if cmd in ("stop", "status"):
            raise RecordError(f"{cmd} takes no options")
        if a == "--region":
            ov["area"] = "region"
        elif a == "--screen":
            ov["area"] = "screen"
        elif a == "--camera":
            ov["camera"] = True
        elif a == "--no-camera":
            ov["camera"] = False
        elif a == "--audio" and i + 1 < len(rest) and rest[i + 1] in S.RECORD_AUDIOS:
            ov["audio"] = rest[i + 1]
            i += 1
        else:
            raise RecordError(f"bad option {a!r}\n{USAGE}")
        i += 1
    return cmd, ov


def main(argv):
    try:
        cmd, ov = parse(argv)
        if cmd == "camera":
            return camera_move(ov["corner"])
        if cmd == "stop":
            return stop()
        if cmd == "status":
            return status()
        if cmd == "toggle" and read_state(runtime_dir()):
            return stop()
        settings, _ = S.load(os.environ.get("BBKOS_SETTINGS") or Path.home() / ".config/bbkos/settings.json")
        return start(options(settings, ov))
    except RecordError as e:
        msg = str(e.args[0])
        code = e.args[1] if len(e.args) > 1 else 2 if msg.startswith(("usage", "unknown", "bad ", "stop takes", "status takes")) else 1
        print(msg, file=sys.stderr if code else sys.stdout)
        return code
