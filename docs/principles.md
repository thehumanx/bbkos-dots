# Principles

Rules for every change to bbkOS, whether made by the owner or an AI agent.

## Working with the owner

1. **Think about the intent, not just the wording.** If a request has a better alternative, say so before doing it.
2. **Justify every recommendation.** For each package, service or setting: why it is recommended, the alternatives, and pros and cons of each. Lead with a recommendation, not a survey.
3. **No slop.** Nothing is installed "just in case". Every package must have a reason recorded in a decision or module doc.
4. **Optimise for this machine** (Intel Core Ultra 7 155H, Arc iGPU, 30 GB RAM, NVMe, btrfs, laptop) rather than for a generic Arch install.
5. **Document as you go.** A change is not finished until its module doc and changelog entry exist.

## End goal

The most **flexible and configurable** system possible, **without** paying for it in RAM, CPU, GPU, battery or boot time. Stability comes first in phase 1, but every choice must keep the path to full configurability open (for example, prefer components Quickshell can replace or drive over closed, fixed-function ones).

## Resource impact (required in every recommendation)

Every recommendation states its cost on this machine, next to the alternatives:

1. **Memory:** idle RSS, and whether it shares libraries with something already running (for example, Qt apps share libraries with Quickshell).
2. **CPU and wakeups:** does it poll or sit idle? Prefer event-driven (D-Bus, inotify, Wayland events) over timers and polling.
3. **GPU and battery:** continuous animation, blur, shadows and shaders cost battery on the iGPU. Anything that redraws while idle needs a justification.
4. **Boot and login time:** services, and whether they can be socket- or D-Bus-activated instead of always running.
5. **Disk and background work:** indexers, scanners, update checkers and telemetry. Disable or avoid them unless wanted.
6. **Dependency weight:** what it pulls in (for example, KDE or GNOME libraries just for one app).

Where possible, **measure rather than guess**: record before/after numbers in the module doc using the method in `docs/measurement.md`. Estimates are labelled as estimates.

## Changing the system

1. **Read before write.** Inspect the current state of a file or service before changing it.
2. **Prefer official repos, then AUR.** Every AUR package is justified in writing, with its PKGBUILD reviewed before install.
3. **Prefer drop-ins over edits.** Use `/etc/<unit>.d/*.conf` and `/etc/<tool>.conf.d/` rather than editing packaged files.
4. **Reversible changes.** Take a snapshot before risky changes (once snapshots exist) and record how to undo each one.
5. **Use systemd properly.** Enable units with `systemctl enable --now`, prefer user units for per-user services, and verify with `systemctl status` and `journalctl`.
6. **Verify, don't assume.** After each change, run a command that shows it worked, and record the evidence in the changelog.
7. **No unsolicited privilege use.** Anything needing `sudo` is shown to the owner first and run by them, unless they have said otherwise.
8. **Configuration lives in version control.** User config is tracked (dotfiles repo, to be decided), not scattered.
9. **Follow the Arch Wiki** for the component in question, and note where we deliberately deviate.
