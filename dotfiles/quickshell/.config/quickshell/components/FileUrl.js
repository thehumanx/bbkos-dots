.pragma library

// Absolute path -> file:// URL, each path segment percent-encoded, so spaces, unicode, #, ? and % in a name stay
// part of the file name. "" for anything that is not an absolute path. Shared by modules/wallpaper/Wallpaper.qml
// and modules/settings/PageWallpaper.qml.
function toUrl(p) {
    if (typeof p !== "string" || !p.startsWith("/")) return ""
    return "file://" + p.split("/").map(encodeURIComponent).join("/")
}
