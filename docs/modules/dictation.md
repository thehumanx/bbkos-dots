# Dictation (Voxtype)

Press `Super+Ctrl+X`, speak English, press it again: the words are typed into the focused window. Voxtype (speech to text with whisper.cpp) runs as a systemd user service, entirely on this machine. Added 2026-10-29. Design: `docs/specs/2026-10-29-dictation-design.md`, plan: `docs/plans/2026-10-29-dictation.md`. Status: installed, measured and tried by the owner (2026-10-29: "works great").

## What it is

- Package: AUR `voxtype` 1.1.1, built from source (the prebuilt `voxtype-bin` was rejected, below). Binaries in `/usr/lib/voxtype/` (`voxtype-native` for the CPU, `voxtype-vulkan` for the GPU); `/usr/bin/voxtype` points to the active one.
- Backend: **Vulkan on the Arc iGPU**, switched with `sudo voxtype setup gpu --enable` (run by the owner in a terminal; it changes the symlink). `voxtype setup gpu --status` shows the active backend.
- Model: `small.en` (466 MB, `~/.local/share/voxtype/models/ggml-small.en.bin`), downloaded from Hugging Face by `voxtype setup --download`.
- Config: `dotfiles/voxtype/.config/voxtype/config.toml`, Stow package `voxtype`, linked to `~/.config/voxtype/config.toml`. The hotkey is off (the key is a Hyprland bind, so Voxtype never reads the keyboard and the `input` group is not needed); English only; types with `wtype`, clipboard as the fallback; pauses media while recording; the model loads on demand; Voxtype's own on-screen waveform (GTK4 OSD) is off.
- Key: preset `dictation-toggle` (group Shell) on `Super+Ctrl+X`, `voxtype record toggle`, with a notification if the service is not running (`keybinds.md`). Not bound while locked.
- Install: `yay -S voxtype`, then `scripts/install-dictation.sh` (never as root; `--dry-run` prints the steps), then the `sudo voxtype setup gpu --enable` above.
- Reference: Omarchy's dictation (`omarchy-dictation-voxtype`, `default/voxtype/config.toml`), minus its backend switch.

## Why `voxtype` and not `voxtype-bin`

`voxtype-bin` fetches about 700 MB of prebuilt variants (CPU, Vulkan, ONNX, CUDA, MIGraphX, three OSD frontends) from GitHub release assets, which ran at 13-32 KB/s here (Cloudflare 6.8 MB/s, Hugging Face 2 MB/s, GitHub's source tarball 0.7 MB/s), and nearly all of it is CUDA/AMD builds this laptop cannot use. `voxtype` builds from the same source tarball (same sha256) natively. Omarchy installs `voxtype-bin` from its own pacman repo (`pkgs.omarchy.org`), not from the AUR. The source build's `prepare()` runs `cargo fetch --locked`, which also fetches an optional Intel OpenVINO backend (a Git fork with the OpenVINO toolkit as submodules) that is not compiled: about 3.2 GB in `~/.cargo/git`, deletable after the build (`rm -rf ~/.cargo/git`; `~/.cargo` was 3.5 GB in total).

## After a Voxtype upgrade

The package installs `/usr/bin/voxtype -> voxtype-native` itself and its upgrade hook does not keep the backend (read 2026-10-29, `voxtype.install`; not yet seen happen), so an upgrade is expected to put the slow CPU build back. Check `voxtype setup gpu --status` (the Backend row of Settings › Keyboard › Dictation turns amber), then run `sudo voxtype setup gpu --enable` in a terminal and `systemctl --user restart voxtype`.

## Measured (2026-10-29, Core Ultra 7 155H, Arc iGPU, `small.en`, Whisper's `jfk.wav`, 11 s of speech)

| | Result |
|---|---|
| CPU build (`voxtype-native`), transcription | 45.6 s and 49.6 s (about 4 times slower than real time; cause not found, the GPU result made it unnecessary) |
| Vulkan build, transcription | 5.9 s on the first run (shader compilation, probably), 1.48 s on the second |
| Model load | 0.25 s on the CPU build, 0.56 s on Vulkan |
| Daemon resident memory, Vulkan, model loaded | 58 MB (the model lives in shared GPU memory); 503 MB on the CPU build |
| Daemon resident memory, `on_demand_loading = true` | 26 MB; about 620 MB more available system memory than with the model loaded (rough: other processes move too) |
| Idle CPU (60 s sample) | 0.18 % of one core, about 40 context switches per second (25 threads); not zero, small; the same with on-demand loading (0.20 %, 39.8/s) |
| Voxtype's GTK4 OSD (default on) | 75 MB resident process even while hidden: turned off |
| Disk | package 34 MB, model 466 MB, build cache `~/.cargo` 3.5 GB (deletable) |
| Build time | not timed |

Not measured: battery drain over a working session, power during a transcription, the first-use latency of the GPU after a long idle.

## Verified

- 2026-10-29, the owner with the real key: two spoken dictations through `Super+Ctrl+X`. The log: 9.0 s of speech transcribed in 1.38 s, 6.5 s in 1.36 s (Vulkan, `small.en`, model loaded on demand in 0.56-0.58 s while recording started). The owner reported it works. The second result read as "Um... swords for... uh... Omanaut?", which the owner did not comment on: accuracy was not judged.
- Without a voice: `voxtype record toggle` starts and stops a recording and a silent recording types nothing; with the service stopped the key command exits 0 and a "Dictation" notification arrives; while recording, `qs ipc call privacy status` lists `PipeWire ALSA [voxtype-vulkan]` as the microphone and clears it afterwards. `wtype` cannot trigger Hyprland binds here (not even `Super+;`), so the key itself can only be tried by hand.

## Not verified

- Which windows the owner typed into: the clipboard fallback (a window where `wtype` cannot type), the "no speech" notification from a real key press, and whether the first spoken word is ever lost to the 0.56 s model load (none was reported).
- `setup check` reports the modifier-release guard as unavailable without the `input` group: typed text could trigger shortcuts if `Super+Ctrl` is still held when the text arrives. With a toggle the text arrives a second after the second press; nothing was reported.
- Battery use over a working session and power during a transcription were not measured.

## Undo

`systemctl --user disable --now voxtype`, `bbkos-keybinds remove dictation-toggle` then `bbkos-keybinds apply`, `stow -D --no-folding -d ~/.local/share/bbkos/repo/dotfiles -t ~ voxtype`, `yay -Rns voxtype` (the user must do the last), remove `~/.local/share/voxtype` (the model) and `~/.cargo`.
