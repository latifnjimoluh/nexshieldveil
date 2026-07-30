// A SpinBox in the brand palette: a slate-bordered field with aqua −/+ steppers,
// the value in mono ink. Subclasses the Basic SpinBox so `from`/`to`/`stepSize`/
// `value`/`onValueModified`/`Accessible.name` are unchanged (constat #1). Replaces
// Basic's white field and black glyphs.
import QtQuick
import QtQuick.Controls.Basic

SpinBox {
    id: control
    implicitHeight: 40
    implicitWidth: 150
    font.family: Theme.fontMono
    font.pixelSize: Theme.fontSize("body")

    contentItem: TextInput {
        text: control.displayText
        font: control.font
        color: Theme.ink
        selectionColor: Theme.accent
        selectedTextColor: Theme.base
        horizontalAlignment: Qt.AlignHCenter
        verticalAlignment: Qt.AlignVCenter
        readOnly: !control.editable
        validator: control.validator
        inputMethodHints: Qt.ImhFormattedNumbersOnly
    }

    up.indicator: Rectangle {
        x: control.mirrored ? 0 : control.width - width
        height: control.height
        implicitWidth: 34
        implicitHeight: 40
        color: control.up.pressed ? Theme.line : "transparent"
        Text {
            text: "+"
            anchors.centerIn: parent
            color: control.enabled ? Theme.accent : Theme.inkSoft
            font.family: Theme.fontUi
            font.pixelSize: Theme.fontSize("title")
        }
    }

    down.indicator: Rectangle {
        x: control.mirrored ? control.width - width : 0
        height: control.height
        implicitWidth: 34
        implicitHeight: 40
        color: control.down.pressed ? Theme.line : "transparent"
        Text {
            text: "−"
            anchors.centerIn: parent
            color: control.enabled ? Theme.accent : Theme.inkSoft
            font.family: Theme.fontUi
            font.pixelSize: Theme.fontSize("title")
        }
    }

    background: Rectangle {
        implicitWidth: 150
        color: "transparent"
        radius: Theme.radius("sm")
        border.color: control.activeFocus ? Theme.accent : Theme.line
        border.width: control.activeFocus ? 2 : 1

        // Hairline separators framing the value from the steppers.
        Rectangle {
            x: control.down.indicator.width
            width: 1
            height: parent.height
            color: Theme.line
        }
        Rectangle {
            x: parent.width - control.up.indicator.width - 1
            width: 1
            height: parent.height
            color: Theme.line
        }
    }
}
