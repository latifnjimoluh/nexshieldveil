// A horizontal Slider dressed in the brand palette: slate track, aqua fill, a
// panel-coloured handle ringed in aqua. Subclasses the Basic Slider so every API
// the views rely on (from/to/stepSize/value/onMoved/Accessible.name) is unchanged
// — only the visual delegates are replaced (see docs/DESIGN_TOKENS.md, constat #1).
import QtQuick
import QtQuick.Controls.Basic

Slider {
    id: control
    implicitHeight: 28

    background: Rectangle {
        x: control.leftPadding
        y: control.topPadding + control.availableHeight / 2 - height / 2
        width: control.availableWidth
        height: 4
        radius: 2
        color: Theme.line

        // Filled portion up to the handle.
        Rectangle {
            width: control.position * parent.width
            height: parent.height
            radius: 2
            color: Theme.accent
        }
    }

    handle: Rectangle {
        x: control.leftPadding + control.visualPosition * (control.availableWidth - width)
        y: control.topPadding + control.availableHeight / 2 - height / 2
        implicitWidth: 20
        implicitHeight: 20
        radius: 10
        color: control.pressed ? Qt.darker(Theme.panel, 1.15) : Theme.panel
        border.color: Theme.accent
        border.width: 2

        // Focus ring — accessibility floor, matches PrimaryButton.
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
}
