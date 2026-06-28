// About & limits: states plainly what the product does and does NOT protect against.
// Binds to `aboutVM`, `Theme`, `Tr`.
import QtQuick

Item {
    id: root
    implicitWidth: 460
    implicitHeight: 460

    GlassPanel {
        anchors.fill: parent
        anchors.margins: Theme.space("md")

        Flickable {
            anchors.fill: parent
            anchors.margins: Theme.space("lg")
            contentHeight: col.implicitHeight
            clip: true

            Column {
                id: col
                width: parent.width
                spacing: Theme.space("md")

                Text {
                    text: aboutVM.title
                    color: Theme.ink
                    font.family: Theme.fontDisplay
                    font.pixelSize: Theme.fontSize("display")
                }
                Text {
                    text: aboutVM.version
                    color: Theme.inkSoft
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSize("caption")
                }
                Text {
                    width: parent.width
                    text: aboutVM.tagline
                    wrapMode: Text.WordWrap
                    color: Theme.ink
                    font.family: Theme.fontUi
                    font.pixelSize: Theme.fontSize("base")
                }
                Text {
                    width: parent.width
                    text: aboutVM.local_text
                    wrapMode: Text.WordWrap
                    color: Theme.inkSoft
                    font.family: Theme.fontUi
                    font.pixelSize: Theme.fontSize("body")
                }

                Rectangle { width: parent.width; height: 1; color: Theme.line }

                Text {
                    text: aboutVM.limits_title
                    color: Theme.ink
                    font.family: Theme.fontUi
                    font.bold: true
                    font.pixelSize: Theme.fontSize("title")
                }

                Repeater {
                    model: aboutVM.limits
                    delegate: Row {
                        required property string modelData
                        width: col.width
                        spacing: Theme.space("sm")
                        Text {
                            text: "—"
                            color: Theme.stateColor("error")
                            font.family: Theme.fontUi
                            font.pixelSize: Theme.fontSize("body")
                        }
                        Text {
                            width: col.width - Theme.space("xl")
                            text: parent.modelData
                            wrapMode: Text.WordWrap
                            color: Theme.inkSoft
                            font.family: Theme.fontUi
                            font.pixelSize: Theme.fontSize("body")
                        }
                    }
                }

                Text {
                    text: aboutVM.license_text
                    color: Theme.inkSoft
                    font.family: Theme.fontUi
                    font.pixelSize: Theme.fontSize("caption")
                }
            }
        }
    }
}
