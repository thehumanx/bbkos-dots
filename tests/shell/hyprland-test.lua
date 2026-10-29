-- The nested Hyprland the shell tests start (tests/shell/harness.py). One output at scale 1 (a nested output takes the
-- size of its window on the live screen, so the mode below is a request, not a guarantee), no animations, blur or
-- shadows, nothing started and no binds: the test shell is started by the harness, not by this file. Checked with `Hyprland --verify-config -c tests/shell/hyprland-test.lua`.
hl.monitor({
    output   = "",
    mode     = "1600x1000@60",
    position = "0x0",
    scale    = 1,
})

hl.config({
    animations = { enabled = false },
    decoration = {
        blur   = { enabled = false },
        shadow = { enabled = false },
    },
    misc = {
        disable_hyprland_logo   = true,
        disable_splash_rendering = true,
        disable_watchdog_warning = true,     -- the "started without start-hyprland" banner, shown on each reload
    },
})
