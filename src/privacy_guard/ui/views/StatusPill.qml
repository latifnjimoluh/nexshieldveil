// Discrete state indicator: a coloured dot + the state headline. Presentational only
// (role/label are bound by the parent), so it stays reusable and smoke-testable alone.
import QtQuick

Row {
    id: root
    property string role: "paused"
    property string label: ""
    property bool engaging: false
    spacing: Theme.space("sm")

    Accessible.role: Accessible.StaticText
    Accessible.name: root.label

    Rectangle {
        id: dot
        width: 12
        height: 12
        radius: 6
        anchors.verticalCenter: parent.verticalCenter
        color: Theme.stateColor(root.role)

        // A soft pulse only while an observer is being detected (and motion is allowed).
        SequentialAnimation on opacity {
            running: root.engaging && !Theme.reduced_motion
            loops: Animation.Infinite
            NumberAnimation { to: 0.35; duration: 700; easing.type: Easing.InOutSine }
            NumberAnimation { to: 1.0; duration: 700; easing.type: Easing.InOutSine }
        }
    }

    Text {
        anchors.verticalCenter: parent.verticalCenter
        text: root.label
        color: Theme.ink
        font.family: Theme.fontDisplay
        font.pixelSize: Theme.fontSize("title")
    }
}
