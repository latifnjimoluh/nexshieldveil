// Opt-in live camera preview: shows what the camera sees + the detection boxes.
// Off by default; only renders frames while `cameraVM.available`. Binds to
// `cameraVM`, `Theme`, `Tr`. Nothing here is recorded — it only displays.
import QtQuick

Item {
    id: root
    property real radius: 0
    implicitWidth: 420
    implicitHeight: 320

    GlassPanel {
        anchors.fill: parent
        radius: root.radius

        Column {
            anchors.fill: parent
            anchors.margins: Theme.space("lg")
            spacing: Theme.space("md")

            Text {
                text: cameraVM.title
                color: Theme.ink
                font.family: Theme.fontDisplay
                font.pixelSize: Theme.fontSize("title")
            }

            // The frame (or an honest 'off' message when not showing).
            Rectangle {
                id: frame
                width: parent.width
                height: parent.height - Theme.space("xxxl") * 2
                radius: Theme.radius("md")
                color: "#0C0D10"
                clip: true
                border.width: 1
                border.color: Theme.line

                Image {
                    objectName: "cameraImage"
                    anchors.fill: parent
                    anchors.margins: 2
                    fillMode: Image.PreserveAspectFit
                    cache: false
                    visible: cameraVM.available
                    // The counter busts the cache so each new frame is re-fetched.
                    source: cameraVM.available ? "image://nsvcam/" + cameraVM.frame_tick : ""
                }

                Text {
                    anchors.centerIn: parent
                    width: parent.width - Theme.space("xl")
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    visible: !cameraVM.available
                    text: cameraVM.off_text
                    color: Theme.inkSoft
                    font.family: Theme.fontUi
                    font.pixelSize: Theme.fontSize("body")
                }
            }

            // Legend: what each coloured box means.
            Row {
                spacing: Theme.space("lg")
                Repeater {
                    model: cameraVM.legend
                    delegate: Row {
                        required property var modelData
                        spacing: Theme.space("xs")
                        Rectangle {
                            width: 10; height: 10; radius: 5
                            anchors.verticalCenter: parent.verticalCenter
                            color: modelData.color
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.label
                            color: Theme.inkSoft
                            font.family: Theme.fontUi
                            font.pixelSize: Theme.fontSize("caption")
                        }
                    }
                }
            }

            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: cameraVM.hint
                color: Theme.inkSoft
                font.family: Theme.fontUi
                font.pixelSize: Theme.fontSize("caption")
            }
        }
    }
}
