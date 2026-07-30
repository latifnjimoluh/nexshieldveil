// A ComboBox in the brand palette: a slate-bordered field with an aqua chevron and
// a panel-coloured popup. Subclasses the Basic ComboBox so `model`/`textRole`/
// `currentIndex`/`onActivated`/`Accessible.name` are unchanged (constat #1).
import QtQuick
import QtQuick.Controls.Basic

ComboBox {
    id: control
    implicitHeight: 40
    implicitWidth: 150
    font.family: Theme.fontUi
    font.pixelSize: Theme.fontSize("body")

    delegate: ItemDelegate {
        id: itemDelegate
        required property var model
        required property int index
        width: ListView.view.width
        highlighted: control.highlightedIndex === index

        contentItem: Text {
            text: control.textRole
                  ? itemDelegate.model[control.textRole]
                  : itemDelegate.model
            font: control.font
            color: Theme.ink
            verticalAlignment: Text.AlignVCenter
        }

        background: Rectangle {
            color: itemDelegate.highlighted ? Theme.line : "transparent"
        }
    }

    indicator: Text {
        x: control.width - width - control.rightPadding
        y: control.topPadding + (control.availableHeight - height) / 2
        text: "▾"
        font.family: Theme.fontUi
        font.pixelSize: Theme.fontSize("body")
        color: Theme.accent
    }

    contentItem: Text {
        leftPadding: Theme.space("md")
        rightPadding: control.indicator.width + Theme.space("sm")
        text: control.displayText
        font: control.font
        color: Theme.ink
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        implicitWidth: 150
        color: "transparent"
        radius: Theme.radius("sm")
        border.color: control.activeFocus ? Theme.accent : Theme.line
        border.width: control.activeFocus ? 2 : 1
    }

    popup: Popup {
        y: control.height
        width: control.width
        implicitHeight: Math.min(contentItem.implicitHeight, 260)
        padding: 1

        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator {}
        }

        background: Rectangle {
            color: Theme.panel
            radius: Theme.radius("sm")
            border.color: Theme.line
            border.width: 1
        }
    }
}
