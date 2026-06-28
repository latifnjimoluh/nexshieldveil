// Accessible button built on plain QtQuick: keyboard-operable, visible focus ring,
// honest disabled state. Used everywhere so the a11y floor is enforced in one place.
import QtQuick

Rectangle {
    id: root
    property string text: ""
    property bool primary: true
    property bool actionEnabled: true
    signal clicked()

    implicitWidth: label.implicitWidth + Theme.space("xl") * 2
    implicitHeight: label.implicitHeight + Theme.space("md") * 2
    radius: Theme.radius("md")
    opacity: actionEnabled ? 1.0 : 0.45

    color: !primary ? "transparent"
           : mouse.containsPress ? Qt.darker(Theme.accent, 1.15)
           : mouse.containsMouse ? Qt.lighter(Theme.accent, 1.06)
           : Theme.accent
    border.width: primary ? 0 : 1
    border.color: Theme.line

    activeFocusOnTab: actionEnabled
    Accessible.role: Accessible.Button
    Accessible.name: root.text
    Accessible.description: root.text
    Accessible.focusable: true
    Accessible.onPressAction: if (root.actionEnabled) root.clicked()

    Behavior on color {
        enabled: !Theme.reduced_motion
        ColorAnimation { duration: Theme.duration("quick") }
    }

    Text {
        id: label
        anchors.centerIn: parent
        text: root.text
        font.family: Theme.fontUi
        font.pixelSize: Theme.fontSize("body")
        font.bold: true
        // High-contrast label on the aqua accent in both themes.
        color: root.primary ? (Theme.is_dark ? "#0E1116" : "#FFFFFF") : Theme.ink
    }

    // Focus ring — never removed (accessibility floor).
    Rectangle {
        anchors.fill: parent
        anchors.margins: -3
        radius: parent.radius + 3
        color: "transparent"
        border.width: 2
        border.color: Theme.accent
        visible: root.activeFocus
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        enabled: root.actionEnabled
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }

    Keys.onReturnPressed: if (root.actionEnabled) root.clicked()
    Keys.onEnterPressed: if (root.actionEnabled) root.clicked()
    Keys.onSpacePressed: if (root.actionEnabled) root.clicked()
}
