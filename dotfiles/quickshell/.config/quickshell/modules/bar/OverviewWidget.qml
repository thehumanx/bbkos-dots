import QtQuick
import qs
import qs.components
import qs.services

// Grid icon: left click opens the workspace overview on this screen, or closes it when it is already open here
// (modules/overview). Accent while the overview is open.
Txt {
    property string screenName: ""

    text: "\uf009"                 // Font Awesome th-large
    color: OverviewState.open ? Theme.accent : tone(Theme.accent)

    BarHit { cursorShape: Qt.PointingHandCursor
        onClicked: OverviewState.toggle(screenName)
    }
}
