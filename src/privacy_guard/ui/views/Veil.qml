// The signature treatment: the veil "settling" over content when protection engages.
// Purely visual (opacity + a faint scale), driven only by `engaged`. Honours
// prefers-reduced-motion by dropping the scale and shortening the fade.
import QtQuick

Item {
    id: root
    property bool engaged: false
    property string caption: ""
    property real radius: 0

    Rectangle {
        id: veil
        anchors.fill: parent
        radius: parent.radius
        // An opaque cool veil — the same material the product paints on screen.
        color: Qt.rgba(Qt.color(Theme.base).r,
                       Qt.color(Theme.base).g,
                       Qt.color(Theme.base).b,
                       0.94)
        opacity: root.engaged ? 1.0 : 0.0
        visible: opacity > 0.001
        scale: (root.engaged || Theme.reduced_motion) ? 1.0 : 1.02

        Behavior on opacity {
            NumberAnimation {
                duration: Theme.duration("veil_settle")
                easing.type: Easing.OutCubic
            }
        }
        Behavior on scale {
            enabled: !Theme.reduced_motion
            NumberAnimation {
                duration: Theme.duration("veil_settle")
                easing.type: Easing.OutCubic
            }
        }

        Text {
            anchors.centerIn: parent
            visible: root.caption.length > 0
            text: root.caption
            color: Theme.inkSoft
            font.family: Theme.fontDisplay
            font.pixelSize: Theme.fontSize("title")
        }
    }
}
