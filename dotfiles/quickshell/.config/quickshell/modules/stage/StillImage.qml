import QtQuick
import Quickshell.Wayland

// A still screenshot of one window that can be refreshed without a blink. A refresh builds the capture in the second
// slot underneath the shown one, and swaps only once the new frame has arrived, so a card never goes blank while it
// updates. The capture is drawn through a layer: ScreencopyView does not blend, so a translucent window's alpha would
// otherwise land in the surface itself (see docs/modules/overview.md, translucent windows).
Item {
    id: root

    property var captureSource: null           // a Toplevel handle (HyprlandToplevel.wayland), or null
    property int refreshToken: 0               // bump to take a new still
    readonly property bool hasContent: front === 0 ? slotA.ready : slotB.ready
    property int front: 0                      // which slot is shown

    onRefreshTokenChanged: startBack()
    onCaptureSourceChanged: { slotA.active = false; slotB.active = false; front = 0; slotA.active = captureSource !== null }

    function startBack() {
        if (captureSource === null) return
        const back = front === 0 ? slotB : slotA
        back.active = false
        back.active = true
    }

    function swapIfReady(slot) {
        const isA = slot === slotA
        if (!slot.ready || (front === 0) === isA) return        // not ready, or it is already the shown one
        front = isA ? 0 : 1
        if (isA) slotB.active = false
        else slotA.active = false
    }

    component Slot: Loader {
        readonly property bool ready: item ? item.hasContent : false
        anchors.fill: parent
        active: false
        onReadyChanged: root.swapIfReady(this)
        sourceComponent: Component {
            ScreencopyView {
                anchors.fill: parent
                captureSource: root.captureSource
                live: false
                paintCursor: false
                layer.enabled: true
                layer.smooth: true
            }
        }
    }

    Slot { id: slotA; z: root.front === 0 ? 1 : 0; Component.onCompleted: active = root.captureSource !== null }
    Slot { id: slotB; z: root.front === 1 ? 1 : 0 }
}
