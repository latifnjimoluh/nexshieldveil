// Camera-transparency indicator (a hard privacy requirement): visible whenever the
// camera is delivering frames. Presentational; 'active'/'label' bound by the parent.
import QtQuick

Row {
    id: root
    property bool active: false
    property string label: ""
    spacing: Theme.space("xs")
    opacity: active ? 1.0 : 0.45

    Accessible.role: Accessible.StaticText
    Accessible.name: root.label

    // A small "aperture" glyph drawn from primitives (no asset dependency).
    Rectangle {
        id: glyph
        width: 14
        height: 14
        radius: 7
        anchors.verticalCenter: parent.verticalCenter
        color: "transparent"
        border.width: 2
        border.color: root.active ? Theme.stateColor("protected") : Theme.inkSoft

        Rectangle {
            anchors.centerIn: parent
            width: 5
            height: 5
            radius: 2.5
            color: root.active ? Theme.stateColor("protected") : Theme.inkSoft
        }
    }

    Text {
        anchors.verticalCenter: parent.verticalCenter
        text: root.label
        color: Theme.inkSoft
        font.family: Theme.fontUi
        font.pixelSize: Theme.fontSize("caption")
    }
}
