import QtQuick
import Quickshell
import Quickshell.Io
import qs
import qs.services

// IPC target "theme": the test hook for the generated theme.
//   qs ipc call theme status   JSON of the tokens as the shell uses them now (Theme's resolved values)
//   qs ipc call theme reload   re-read colors.json and settings.json
Scope {
    IpcHandler {
        target: "theme"
        function status(): string {
            const colors = Object.assign({}, ThemeStore.colors, {
                bg: String(Theme.bg), surface: String(Theme.surface), fg: String(Theme.fg), dim: String(Theme.dim),
                accent: String(Theme.accent), warn: String(Theme.warn), crit: String(Theme.crit)
            })
            const shell = {
                barHeight: Theme.barHeight, gap: Theme.gap, radius: Theme.radius,
                controlRadius: Theme.controlRadius, fontSize: Theme.fontSize, font: Theme.font
            }
            return JSON.stringify({ colors: colors, shell: shell, wallpaperPath: ThemeStore.wallpaperPath })
        }
        function reload(): void { ThemeStore.reload() }
    }
}
