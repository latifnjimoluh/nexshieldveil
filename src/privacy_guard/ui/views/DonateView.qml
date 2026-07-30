// Donate panel: an optional way to support the project. The button opens the
// hosted KPay payment page in the user's browser (the view-model emits the intent;
// the shell owns the browser). Binds to `donateVM`, `Theme`, `Tr`, `Brand`.
import QtQuick

Item {
    id: root
    implicitWidth: 460
    implicitHeight: 420

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

                // Brand lockup (degrades to nothing if the asset is not bundled).
                Image {
                    source: Brand.wordmark
                    visible: source != ""
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    width: Math.min(col.width, 260)
                    height: width * 131 / 527  // native lockup ratio
                }

                Text {
                    text: donateVM.title
                    color: Theme.ink
                    font.family: Theme.fontDisplay
                    font.pixelSize: Theme.fontSize("display")
                }

                Text {
                    width: parent.width
                    text: donateVM.body
                    wrapMode: Text.WordWrap
                    color: Theme.ink
                    font.family: Theme.fontUi
                    font.pixelSize: Theme.fontSize("base")
                }

                PrimaryButton {
                    objectName: "donateButton"
                    text: donateVM.action_label
                    onClicked: donateVM.donate()
                }

                // Where the button leads, spelled out — no surprise redirect.
                Text {
                    width: parent.width
                    text: donateVM.url
                    wrapMode: Text.WrapAnywhere
                    color: Theme.accent
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSize("caption")
                }

                Text {
                    width: parent.width
                    text: donateVM.note
                    wrapMode: Text.WordWrap
                    color: Theme.inkSoft
                    font.family: Theme.fontUi
                    font.pixelSize: Theme.fontSize("caption")
                }
            }
        }
    }
}
