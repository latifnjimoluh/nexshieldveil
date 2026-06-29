// The main window — surfaces every option on a real interface (not only the tray
// menu): state, primary action, show/hide camera, settings, about, quit. The live
// camera preview is embedded but OFF by default (revealed via the toggle).
// Binds to statusVM, cameraVM, trayVM, Theme, Tr.
import QtQuick

Item {
    id: root
    implicitWidth: 480
    implicitHeight: cameraVM.preview_enabled ? 760 : 420

    GlassPanel {
        id: panel
        anchors.fill: parent
        anchors.margins: Theme.space("md")

        Column {
            anchors.fill: parent
            anchors.margins: Theme.space("lg")
            spacing: Theme.space("md")

            // ---- header: identity + state ---------------------------------- //
            Row {
                width: parent.width
                Column {
                    width: parent.width - statusPill.width
                    Text {
                        text: Tr.t("main.title")
                        color: Theme.ink
                        font.family: Theme.fontDisplay
                        font.pixelSize: Theme.fontSize("display")
                    }
                    Text {
                        text: Tr.t("main.subtitle")
                        color: Theme.inkSoft
                        font.family: Theme.fontUi
                        font.pixelSize: Theme.fontSize("caption")
                    }
                }
                StatusPill {
                    id: statusPill
                    objectName: "statusPill"
                    anchors.verticalCenter: parent.verticalCenter
                    role: statusVM.color_role
                    label: statusVM.headline
                    engaging: statusVM.engaging
                }
            }

            Text {
                width: parent.width
                text: statusVM.detail
                wrapMode: Text.WordWrap
                color: Theme.inkSoft
                font.family: Theme.fontUi
                font.pixelSize: Theme.fontSize("body")
            }

            Row {
                spacing: Theme.space("lg")
                CameraBadge {
                    objectName: "cameraBadge"
                    active: statusVM.camera_active
                    label: statusVM.camera_label
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: statusVM.show_faces
                    text: statusVM.faces_text
                    color: Theme.inkSoft
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontSize("caption")
                }
            }

            // ---- options (all on the main interface) ----------------------- //
            Flow {
                width: parent.width
                spacing: Theme.space("sm")

                PrimaryButton {
                    objectName: "primaryAction"
                    text: statusVM.primary_action_label
                    onClicked: statusVM.activate_primary()
                }
                PrimaryButton {
                    objectName: "previewToggle"
                    primary: false
                    text: cameraVM.toggle_label
                    onClicked: cameraVM.toggle()
                }
                PrimaryButton {
                    objectName: "settingsButton"
                    primary: false
                    text: Tr.t("action.settings")
                    onClicked: trayVM.open_settings()
                }
                PrimaryButton {
                    objectName: "aboutButton"
                    primary: false
                    text: Tr.t("action.about")
                    onClicked: trayVM.open_about()
                }
                PrimaryButton {
                    objectName: "quitButton"
                    primary: false
                    text: Tr.t("action.quit")
                    onClicked: trayVM.quit()
                }
            }

            // ---- opt-in camera preview (collapsed when off) ---------------- //
            CameraView {
                objectName: "cameraView"
                width: parent.width
                height: cameraVM.preview_enabled ? 320 : 0
                visible: cameraVM.preview_enabled
                radius: Theme.radius("md")
            }
        }
    }

    // Signature veil over the whole panel when protected.
    Veil {
        objectName: "veil"
        anchors.fill: panel
        radius: Theme.radius("lg")
        engaged: statusVM.state_key === "protected"
        caption: statusVM.headline
    }
}
