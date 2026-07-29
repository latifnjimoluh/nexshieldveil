// Updates: current version, check, and — only for a release whose installer we can
// verify — the one-click install. Binds to `updatesVM`, `Theme`, `Tr`.
import QtQuick
import QtQuick.Controls

Item {
    id: root
    implicitWidth: 460
    implicitHeight: 420

    GlassPanel {
        anchors.fill: parent
        anchors.margins: Theme.space("md")

        Column {
            anchors.fill: parent
            anchors.margins: Theme.space("lg")
            spacing: Theme.space("md")

            Text {
                objectName: "updateHeadline"
                width: parent.width
                text: updatesVM.headline
                wrapMode: Text.WordWrap
                color: Theme.ink
                font.family: Theme.fontDisplay
                font.pixelSize: Theme.fontSize("title")
            }

            Text {
                objectName: "updateDetail"
                width: parent.width
                text: updatesVM.detail
                wrapMode: Text.WordWrap
                color: Theme.inkSoft
                font.family: Theme.fontUi
                font.pixelSize: Theme.fontSize("body")
            }

            Text {
                width: parent.width
                text: updatesVM.current_version
                color: Theme.inkSoft
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontSize("caption")
            }

            ProgressBar {
                objectName: "updateProgress"
                width: parent.width
                visible: updatesVM.state_key === "downloading"
                from: 0
                to: 1
                value: updatesVM.progress
            }

            Rectangle { width: parent.width; height: 1; color: Theme.line }

            Row {
                spacing: Theme.space("sm")

                PrimaryButton {
                    objectName: "checkButton"
                    text: updatesVM.check_label
                    enabled: !updatesVM.busy
                    onClicked: updatesVM.check()
                }

                PrimaryButton {
                    objectName: "installButton"
                    text: updatesVM.install_label
                    visible: updatesVM.can_install
                    enabled: !updatesVM.busy
                    onClicked: updatesVM.install()
                }

                PrimaryButton {
                    objectName: "pageButton"
                    text: updatesVM.page_label
                    visible: updatesVM.can_open_page
                    onClicked: updatesVM.open_release_page()
                }
            }

            Row {
                spacing: Theme.space("sm")

                CheckBox {
                    objectName: "autoCheckBox"
                    checked: updatesVM.auto_check
                    Accessible.name: updatesVM.auto_check_label
                    onToggled: updatesVM.set_auto_check(checked)
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: updatesVM.auto_check_label
                    color: Theme.inkSoft
                    font.family: Theme.fontUi
                    font.pixelSize: Theme.fontSize("body")
                }
            }

            Text {
                objectName: "updateNotes"
                width: parent.width
                text: updatesVM.notes
                visible: updatesVM.notes.length > 0
                wrapMode: Text.WordWrap
                color: Theme.inkSoft
                font.family: Theme.fontUi
                font.pixelSize: Theme.fontSize("caption")
            }
        }
    }
}
