import QtQuick
import QtQuick.Effects
import qs

// The tinted shadow under a floating card (Theme.shadow; shell.popupShadow sets its strength, 0 = none). Put it inside
// the card as its first child: z -1 draws it behind the card's own fill, and it follows the card's scale and opacity.
// The card's window needs Theme.shadowPad free pixels around the card, or the shadow is cut off at the window's edge.
// One RectangularShadow (Qt 6.9+) is a single shader quad: no offscreen pass, nothing redraws while the card is still.
RectangularShadow {
    anchors.fill: parent
    z: -1
    radius: parent.radius ?? 0
    blur: 24
    offset.y: 6
    color: Theme.shadow
    visible: Theme.shadowStrength > 0
}
