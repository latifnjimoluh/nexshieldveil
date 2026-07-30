// A CheckBox in the brand palette: a rounded square that fills aqua with a tick
// when checked, its label in ink. Subclasses the Basic CheckBox so `checked`,
// `onToggled`, `text` and `Accessible.name` behave exactly as before (constat #1).
import QtQuick
import QtQuick.Controls.Basic

CheckBox {
    id: control
    spacing: Theme.space("sm")
    font.family: Theme.fontUi
    font.pixelSize: Theme.fontSize("body")

    indicator: Rectangle {
        implicitWidth: 20
        implicitHeight: 20
        x: control.leftPadding
        y: control.topPadding + (control.availableHeight - height) / 2
        radius: 4
        color: control.checked ? Theme.accent : "transparent"
        border.color: control.checked ? Theme.accent : Theme.line
        border.width: 2

        Text {
            anchors.centerIn: parent
            visible: control.checked
            text: "✓"
            font.family: Theme.fontUi
            font.pixelSize: 13
            font.bold: true
            // High-contrast tick on the aqua fill, in both themes.
            color: Theme.is_dark ? "#0E1116" : "#FFFFFF"
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
        color: Theme.ink
        opacity: control.enabled ? 1.0 : 0.5
        wrapMode: Text.WordWrap
        verticalAlignment: Text.AlignVCenter
        leftPadding: control.indicator.width + control.spacing
    }
}
