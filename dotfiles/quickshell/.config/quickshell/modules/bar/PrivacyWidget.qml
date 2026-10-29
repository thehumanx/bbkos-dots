import QtQuick
import qs
import qs.components
import qs.services

// Privacy indicator: a microphone, camera or screen glyph in the warning colour while an app is using it (the BarItem hides the
// widget otherwise). Which of the three count is the Privacy page; place it with the bar layout editor (docs/modules/privacy.md).
Txt {
    horizontalAlignment: Text.AlignHCenter
    color: Theme.warn
    font.bold: true
    text: (Privacy.mic ? "" : "") + (Privacy.camera ? (Privacy.mic ? "  " : "") + "" : "")
          + (Privacy.screen ? (Privacy.mic || Privacy.camera ? "  " : "") + "" : "")
}
