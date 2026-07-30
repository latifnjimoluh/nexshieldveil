// A ProgressBar in the brand palette: a slate track with an aqua fill. Subclasses
// the Basic ProgressBar so `from`/`to`/`value` are unchanged (constat #1).
import QtQuick
import QtQuick.Controls.Basic

ProgressBar {
    id: control
    implicitHeight: 6

    background: Rectangle {
        implicitWidth: 200
        implicitHeight: 6
        radius: 3
        color: Theme.line
    }

    contentItem: Item {
        implicitHeight: 6

        Rectangle {
            width: control.visualPosition * parent.width
            height: parent.height
            radius: 3
            color: Theme.accent
        }
    }
}
