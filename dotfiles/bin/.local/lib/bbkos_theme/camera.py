"""bbkos-camera: the webcam's picture controls from the camera.* settings (docs/modules/camera.md).

The laptop camera is a plain UVC device: its sensor processing lives in the camera and is steered only by the standard
controls (exposure, brightness, gamma, ...), which v4l2-ctl sets. They are applied when settings change (bbkos-theme
apply), at login and whenever an app opens the camera (`watch`, run by bbkos-camera.service), because an app or a
replug can bring the camera's own defaults back. `preview` shows the live picture in a small mpv window beside the
settings window while the Camera page is open.
"""
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import record as R
from . import settings as S

USAGE = """\
usage: bbkos-camera COMMAND
  apply    set the camera.* settings on the camera now
  status   the camera device and its current control values
  watch    re-apply whenever an app opens the camera (a user service runs this)
  preview  show the live camera picture in a window beside the settings window until it is closed or this is
           stopped (the Camera page runs it)
  users    JSON list of the programs that hold a camera device open
  tune     measure the picture and set manual exposure (and gamma, when the room is too dark) for the light now"""

SYSFS = "/sys/class/video4linux"
POWER_LINE = {"off": 0, "50hz": 1, "60hz": 2}
PREVIEW_CLASS = "bbkos-camera-preview"
PREVIEW_SIZE = (360, 203)          # 16:9, what a video call gets from the 1280x720 mode
SETTINGS_TITLE = "bbkOS Settings"
TUNE_TARGET = 105                  # brightness (0-255, gamma encoded) of the face region of the picture
TUNE_TOLERANCE = 5
TUNE_MIN_EXPOSURE = 3              # the camera's own range, units of 0.1 ms
TUNE_MAX_EXPOSURE = 400            # 40 ms: slower than this the frame rate falls below about 25 fps
TUNE_SLOW_EXPOSURE = 800           # last resort when exposure and gamma are used up: about 12 fps
TUNE_GAMMA_STEP = 10
TUNE_GAMMA_MAX = 150
FRAME_W, FRAME_H = 64, 36
SKIP_USERS = {"pipewire", "wireplumber", "pipewire-media-session"}


class CameraError(Exception):
    pass


def controls(cam):
    """(modes, values): v4l2 control assignments from the camera settings. Modes go first, because exposure time and
    white balance temperature are inactive (and refuse a write) while the matching auto mode is on."""
    manual_exp = cam["exposure"] == "manual"
    manual_wb = cam["whiteBalance"] == "manual"
    modes = [("auto_exposure", 1 if manual_exp else 3),
             ("white_balance_automatic", 0 if manual_wb else 1),
             ("exposure_dynamic_framerate", 0 if cam["steadyFramerate"] else 1),
             ("power_line_frequency", POWER_LINE[cam["powerLine"]])]
    values = [(k, cam[s]) for k, s in (("brightness", "brightness"), ("contrast", "contrast"),
                                       ("saturation", "saturation"), ("sharpness", "sharpness"),
                                       ("gamma", "gamma"), ("backlight_compensation", "backlight"))]
    if manual_exp:
        values.append(("exposure_time_absolute", cam["exposureTime"]))
    if manual_wb:
        values.append(("white_balance_temperature", cam["whiteBalanceTemp"]))
    return modes, values


def _arg(assignments):
    return ",".join(f"{k}={v}" for k, v in assignments)


def find_device(sysfs=SYSFS, run=subprocess.run):
    """The colour camera's capture node: the first /dev/videoN of index 0 that offers MJPG or YUYV (the infrared
    camera next to it is greyscale only, and each camera has a second metadata node)."""
    try:
        names = sorted(Path(sysfs).glob("video*"), key=lambda p: int(p.name[5:]))
    except (OSError, ValueError):
        return None
    for p in names:
        try:
            if (p / "index").read_text().strip() != "0":
                continue
            out = run(["v4l2-ctl", "-d", f"/dev/{p.name}", "--list-formats"], capture_output=True, text=True, timeout=5).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        if "MJPG" in out or "YUYV" in out:
            return f"/dev/{p.name}"
    return None


def apply(cam, dev=None, run=subprocess.run):
    """Write the controls. Returns a list of warnings (a control the camera refused); raises CameraError when there is
    no camera or no v4l2-ctl."""
    dev = dev or find_device(run=run)
    if not dev:
        raise CameraError("no colour camera found")
    modes, values = controls(cam)
    warns = []
    try:
        for group in (modes, values):
            res = run(["v4l2-ctl", "-d", dev, "-c", _arg(group)], capture_output=True, text=True, timeout=5)
            if res.returncode != 0:
                text = (res.stderr or res.stdout).strip()
                warns.append(text.splitlines()[0] if text else f"v4l2-ctl exited {res.returncode}")
    except FileNotFoundError as e:
        raise CameraError("v4l2-ctl is missing (pacman -S v4l-utils)") from e
    except subprocess.SubprocessError as e:
        raise CameraError(str(e)) from e
    return warns


def _settings():
    s, _ = S.load(os.environ.get("BBKOS_SETTINGS") or Path.home() / ".config/bbkos/settings.json")
    return s["camera"]


def status():
    dev = find_device()
    if not dev:
        raise CameraError("no colour camera found")
    print(dev)
    print(R.run_quick(["v4l2-ctl", "-d", dev, "--list-ctrls"]).stdout, end="")
    return 0


def watch(quiet_seconds=3.0):
    """Re-apply after each open of the camera node. Our own v4l2-ctl calls open it too, so events during and just
    after an apply are ignored; the short wait lets the app finish its own set-up first."""
    dev = find_device()
    if not dev:
        raise CameraError("no colour camera found")
    proc = subprocess.Popen(["inotifywait", "-m", "-q", "-e", "open", "--format", "%e", dev],
                            stdout=subprocess.PIPE, text=True)
    ignore_until = 0.0
    try:
        apply(_settings(), dev)
        ignore_until = time.monotonic() + quiet_seconds
        for _ in proc.stdout:
            if time.monotonic() < ignore_until:
                continue
            time.sleep(1.5)
            try:
                apply(_settings(), dev)
            except CameraError as e:
                print(f"bbkos-camera: {e}", file=sys.stderr)
            ignore_until = time.monotonic() + quiet_seconds
    finally:
        proc.terminate()
    # inotifywait ends when the camera node goes away (driver reload, USB replug) or the tool dies. Exit non-zero so the
    # service's Restart=on-failure starts a fresh watch; a clean exit 0 would leave the service stopped for good.
    print("bbkos-camera: the camera node closed; restarting the watch", file=sys.stderr)
    return 1


def device_users(proc="/proc", uid=None):
    """Sorted names of the programs (of this user) that hold a /dev/video* node open. PipeWire and WirePlumber open the
    nodes to probe them or to serve a camera stream (which the shell sees as a PipeWire stream), so they are left out."""
    uid = os.getuid() if uid is None else uid
    found = set()
    for pid in filter(str.isdigit, os.listdir(proc)):
        try:
            if os.stat(f"{proc}/{pid}").st_uid != uid:
                continue
            fds = os.listdir(f"{proc}/{pid}/fd")
        except OSError:
            continue
        for fd in fds:
            try:
                target = os.readlink(f"{proc}/{pid}/fd/{fd}")
            except OSError:
                continue
            if target.startswith("/dev/video"):
                try:
                    comm = Path(f"{proc}/{pid}/comm").read_text().strip()
                except OSError:
                    break
                if comm not in SKIP_USERS:
                    found.add(comm)
                break
    return sorted(found)


def preview_command(dev, size=PREVIEW_SIZE, mirror=True):
    """The mpv argv of the preview window: the 1280x720 MJPG mode a call uses, mirrored like a call's self-view."""
    w, h = size
    return ["mpv", f"av://v4l2:{dev}", "--profile=low-latency", "--untimed", "--no-cache",
            "--demuxer-lavf-o=video_size=1280x720,framerate=30,input_format=mjpeg", f"--geometry={w}x{h}",
            "--no-audio", "--no-osc", "--osd-level=0", f"--title={PREVIEW_CLASS}",
            f"--wayland-app-id={PREVIEW_CLASS}", "--really-quiet", *(["--vf=hflip"] if mirror else [])]


def preview_layout(win, mon, size=PREVIEW_SIZE, gap=10):
    """(new settings x or None, preview x, preview y) in logical pixels. The preview goes to the right of the settings
    window, top aligned (a tiled settings window is not moved: the preview sits in its top right corner). When the screen has no room there, the settings window moves left to make it; when even that is
    not enough the preview overlaps the settings window's right edge (it can be dragged)."""
    (x, y), (w, _) = win["at"], win["size"]
    mx, my, mw, mh = mon
    pw, ph = size
    if win.get("floating") is False:                         # tiled settings fills the workspace: the preview floats in its top right corner, nothing moves
        return None, x + w - pw - gap, y + gap
    new_x = x
    if x + w + gap + pw + gap > mx + mw:
        new_x = max(mx + gap, mx + mw - w - pw - 2 * gap)
    px = min(new_x + w + gap, mx + mw - pw - gap)
    py = max(my + gap, min(y, my + mh - ph - gap))
    return (new_x if new_x != x else None), px, py


def _client(cls=None, title=None):
    for c in R._hypr_json("clients"):
        if (cls is None or c.get("class") == cls) and (title is None or c.get("title") == title):
            return c
    return None


def _logical_monitor(win):
    for m in R._hypr_json("monitors"):
        if m.get("id") == win.get("monitor"):
            sc = m.get("scale") or 1
            return m["x"], m["y"], m["width"] / sc, m["height"] / sc
    return None


def preview():
    """Open the preview window and wait until it is closed; the settings window is moved aside when needed and put back
    in the middle afterwards. SIGTERM (the page closing) stops it cleanly."""
    dev = find_device()
    if not dev:
        raise CameraError("no colour camera found")
    busy = device_users()
    if busy:
        raise CameraError("the camera is in use by " + ", ".join(busy) + " (that program already shows your picture)")
    settings = _client(title=SETTINGS_TITLE)
    before = (R._hypr_json("activewindow") or {}).get("address")
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    proc = subprocess.Popen(preview_command(dev), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    moved = False
    try:
        win = None
        for _ in range(60):                                  # the window may take up to 3 s to map
            win = _client(PREVIEW_CLASS)
            if win or proc.poll() is not None:
                break
            time.sleep(0.05)
        if win is None:
            err = (proc.stderr.read() if proc.poll() is not None else "").strip()
            raise CameraError(err.splitlines()[-1] if err else "the preview window did not open")
        sel = f'window = "address:{win["address"]}"'
        if not win.get("floating"):                          # toggles: only when the window rule did not apply
            R.run_quick(["hyprctl", "dispatch", f"hl.dsp.window.float({{ {sel} }})"])
        mon = _logical_monitor(settings) if settings else None
        if settings and mon:
            new_x, px, py = preview_layout(settings, mon)
            if new_x is not None:
                R._move_window(settings["address"], new_x, settings["at"][1])
                moved = True
            R._move_window(win["address"], px, py)
        if before:
            R.run_quick(["hyprctl", "dispatch", f'hl.dsp.focus({{ window = "address:{before}" }})'])
        proc.wait()
        return 0
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(3)
            except subprocess.TimeoutExpired:
                proc.kill()
        if moved:
            again = _client(title=SETTINGS_TITLE)
            if again:
                R.run_quick(["hyprctl", "dispatch", f'hl.dsp.window.center({{ window = "address:{again["address"]}" }})'])


def frame_brightness(frame, w=FRAME_W, h=FRAME_H):
    """Brightness of where a face is in a call, from a grey frame (w*h bytes): the 40th percentile of the lower middle
    (the middle 40 % across, from a third to 92 % down, where a laptop camera that looks up sees a seated head). In a
    backlit room the picture is two groups, a dark face and a bright window or ceiling; a mean or the median follows the
    bright group, a low percentile follows the face (measured on the owner's backlit room: it tracked the face's own
    brightness within about 10 over exposures 295, 600 and 900). A dark shirt or doorway in the region pulls it down."""
    vals = sorted(frame[y * w + x] for y in range(h // 3, h * 11 // 12) for x in range(w * 3 // 10, w * 7 // 10))
    return vals[len(vals) * 40 // 100]


def search_exposure(measure, lo=TUNE_MIN_EXPOSURE, hi=TUNE_MAX_EXPOSURE, target=TUNE_TARGET, tol=TUNE_TOLERANCE,
                    steps=7):
    """The exposure time (units of 0.1 ms) whose picture is closest to `target` brightness, by bisection on a log scale
    (brightness rises with exposure). measure(exposure) -> brightness. Returns (exposure, brightness); the end of the
    range is returned as it is when even that is too dark or too bright."""
    m_hi = measure(hi)
    if m_hi < target - tol:
        return hi, m_hi
    m_lo = measure(lo)
    if m_lo > target + tol:
        return lo, m_lo
    best = min(((abs(m_hi - target), hi, m_hi), (abs(m_lo - target), lo, m_lo)))
    for _ in range(steps):
        mid = round((lo * hi) ** 0.5)
        if mid in (lo, hi):
            break
        m = measure(mid)
        best = min(best, (abs(m - target), mid, m))
        if abs(m - target) <= tol:
            break
        if m < target:
            lo = mid
        else:
            hi = mid
    return best[1], best[2]


class Meter:
    """Streams small grey frames from the camera and measures them after each exposure change. A thread keeps reading,
    because the pipe would otherwise hold old frames from before the change."""

    SETTLE = 0.5       # seconds for a new exposure to reach the frames
    WINDOW = 0.6       # seconds of frames averaged

    def __init__(self, dev):
        self.dev = dev
        self.frames = []                                     # (time, brightness), newest last
        self.proc = subprocess.Popen(
            ["ffmpeg", "-loglevel", "error", "-f", "v4l2", "-input_format", "mjpeg", "-video_size", "1280x720",
             "-framerate", "30", "-i", dev, "-vf", f"fps=10,scale={FRAME_W}:{FRAME_H},format=gray", "-f", "rawvideo", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        size = FRAME_W * FRAME_H
        while True:
            data = self.proc.stdout.read(size)
            if len(data) < size:
                return
            self.frames = self.frames[-60:] + [(time.monotonic(), frame_brightness(data))]

    def control(self, assignments):
        subprocess.run(["v4l2-ctl", "-d", self.dev, "-c", _arg(assignments)], capture_output=True, timeout=5)

    def measure(self):
        """Mean brightness of the frames of the next WINDOW seconds after SETTLE."""
        t0 = time.monotonic() + self.SETTLE
        time.sleep(self.SETTLE + self.WINDOW)
        vals = [b for t, b in self.frames if t >= t0]
        if not vals:
            raise CameraError("the camera gave no pictures (is another program using it?)")
        return sum(vals) / len(vals)

    def measure_exposure(self, exposure):
        self.control([("auto_exposure", 1), ("exposure_time_absolute", exposure)])
        return self.measure()

    def close(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(3)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def _service(action):
    R.run_quick(["systemctl", "--user", action, "bbkos-camera.service"], timeout=15)


def tune():
    """Find the manual exposure (and, when the room is too dark for even the slowest exposure, the gamma) that gives the
    middle of the picture TUNE_TARGET brightness, and save it as the camera.* settings. The watcher service is paused
    meanwhile (it would put the saved values back each time the camera opens) and always started again."""
    dev = find_device()
    if not dev:
        raise CameraError("no colour camera found")
    busy = device_users()
    if busy:
        raise CameraError("the camera is in use by " + ", ".join(busy) + "; close it first")
    cam = _settings()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))
    _service("stop")
    meter = None
    try:
        meter = Meter(dev)
        gamma = cam["gamma"]
        meter.control([("gamma", gamma)])
        dark = lambda: brightness < TUNE_TARGET - TUNE_TOLERANCE                      # noqa: E731
        exposure, brightness = search_exposure(meter.measure_exposure)
        while dark() and exposure == TUNE_MAX_EXPOSURE and gamma < TUNE_GAMMA_MAX:   # 1: lift the shadows
            gamma = min(TUNE_GAMMA_MAX, gamma + TUNE_GAMMA_STEP)
            meter.control([("gamma", gamma)])
            brightness = meter.measure()
        if dark() and exposure == TUNE_MAX_EXPOSURE:                                   # 2: slower frames
            exposure, brightness = search_exposure(meter.measure_exposure, lo=TUNE_MAX_EXPOSURE, hi=TUNE_SLOW_EXPOSURE)
        meter.close()
        meter = None
        changes = [("camera.exposure", "manual"), ("camera.exposureTime", exposure)]
        if gamma != cam["gamma"]:
            changes.append(("camera.gamma", gamma))
        for key, value in changes:
            subprocess.run(["bbkos-theme", "set", key, str(value)], capture_output=True, check=True, timeout=30)
        result = {"exposureTime": exposure, "gamma": gamma, "brightness": round(brightness),
                  "slowFrames": exposure > TUNE_MAX_EXPOSURE,
                  "tooDark": exposure >= TUNE_SLOW_EXPOSURE and brightness < TUNE_TARGET - TUNE_TOLERANCE,
                  "tooBright": exposure == TUNE_MIN_EXPOSURE and brightness > TUNE_TARGET + TUNE_TOLERANCE}
        print(json.dumps(result))
        return 0
    except (OSError, subprocess.SubprocessError) as e:
        raise CameraError(f"tuning failed: {e}") from e
    finally:
        if meter:
            meter.close()
        _service("start")                                    # applies the saved settings again, tuned or not


def main(argv):
    try:
        if argv == ["apply"]:
            for w in apply(_settings()):
                print(f"bbkos-camera: {w}", file=sys.stderr)
            return 0
        if argv == ["status"]:
            return status()
        if argv == ["watch"]:
            return watch()
        if argv == ["preview"]:
            return preview()
        if argv == ["tune"]:
            return tune()
        if argv == ["users"]:
            print(json.dumps(device_users()))
            return 0
        print(USAGE, file=sys.stderr)
        return 2
    except CameraError as e:
        print(f"bbkos-camera: {e}", file=sys.stderr)
        return 1
