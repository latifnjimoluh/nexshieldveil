// A RadioButton in the brand palette: a ring that gains an aqua core when chosen,
// its label in ink. Subclasses the Basic RadioButton so `checked`, `onClicked`,
// `ButtonGroup.group`, `text` and `Accessible.name` are untouched (constat #1).
import QtQuick
import QtQuick.Controls.Basic

RadioButton {
    id: control
    spacing: Theme.space("sm")
    font.family: Theme.fontUi
    font.pixelSize: Theme.fontSize("body")

    indicator: Rectangle {
        implicitWidth: 20
        implicitHeight: 20
        x: control.leftPadding
        y: control.topPadding + (control.availableHeight - height) / 2
        radius: 10
        color: "transparent"
        border.color: control.checked ? Theme.accent : Theme.line
        border.width: 2

        Rectangle {
            anchors.centerIn: parent
            visible: control.checked
            width: 10
            height: 10
            radius: 5
            color: Theme.accent
        }

        // Focus ring.
        Rectangle {
            anchors.fill: parent
            anchors.margins: -3
            radius: parent.radius + 3
            color: "transparent"
            border.width: 2
            border.color: Theme.accent
            visible: control.visualFocus
        }
    }

    contentItem: Text {
        text: control.text
        font: control.font
        color: control.enabled ? Theme.ink : Theme.inkSoft
        opacity: control.enabled ? 1.0 : 0.5
        wrapMode: Text.WordWrap
        verticalAlignment: Text.AlignVCenter
        leftPadding: control.indicator.width + control.spacing
    }
}
