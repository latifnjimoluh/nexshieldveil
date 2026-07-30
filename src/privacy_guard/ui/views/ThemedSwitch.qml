// A Switch in the brand palette: a slate track that turns aqua when on, with a
// sliding knob. Subclasses the Basic Switch so `checked`, `onToggled`, `text` and
// `Accessible.name` keep working (constat #1). Replaces Basic's green #17a81a.
import QtQuick
import QtQuick.Controls.Basic

Switch {
    id: control
    spacing: Theme.space("sm")
    font.family: Theme.fontUi
    font.pixelSize: Theme.fontSize("body")

    indicator: Rectangle {
        implicitWidth: 44
        implicitHeight: 24
        x: control.leftPadding
        y: control.topPadding + (control.availableHeight - height) / 2
        radius: 12
        color: control.checked ? Theme.accent : Theme.line

        Behavior on color {
            enabled: !Theme.reduced_motion
            ColorAnimation { duration: Theme.duration("quick") }
        }

        Rectangle {
            x: control.checked ? parent.width - width - 2 : 2
            y: 2
            width: 20
            height: 20
            radius: 10
            color: "#FFFFFF"

            Behavior on x {
                enabled: !Theme.reduced_motion
                NumberAnimation { duration: Theme.duration("quick") }
            }
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
        verticalAlignment: Text.AlignVCenter
        leftPadding: control.indicator.width + control.spacing
    }
}
