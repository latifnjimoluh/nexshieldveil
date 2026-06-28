// The discrete in-use status surface: state, detail, camera transparency, faces
// count, and the primary action. A Veil layer demonstrates the signature treatment
// when protection is engaged. Binds to `statusVM`, `Theme`, `Tr` (context props).
import QtQuick

Item {
    id: root
    implicitWidth: 400
    implicitHeight: 240

    GlassPanel {
        id: panel
        anchors.fill: parent
        anchors.margins: Theme.space("md")

        Column {
            anchors.fill: parent
            anchors.margins: Theme.space("lg")
            spacing: Theme.space("md")

            StatusPill {
                objectName: "statusPill"
                role: statusVM.color_role
                label: statusVM.headline
                engaging: statusVM.engaging
            }

            Text {
                width: parent.width
                text: statusVM.detail
                wrapMode: Text.WordWrap
                color: Theme.inkSoft
                font.family: Theme.fontUi
                font.pixelSize: Theme.fontSize("body")
            }

            CameraBadge {
                objectName: "cameraBadge"
                active: statusVM.camera_active
                label: statusVM.camera_label
            }

            Text {
                visible: statusVM.show_faces
                text: statusVM.faces_text
                color: Theme.inkSoft
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontSize("caption")
            }

            PrimaryButton {
                objectName: "primaryAction"
                text: statusVM.primary_action_label
                onClicked: statusVM.activate_primary()
            }
        }
    }

    // Signature: the veil settles over the surface when protected.
    Veil {
        objectName: "veil"
        anchors.fill: panel
        radius: Theme.radius("lg")
        engaged: statusVM.state_key === "protected"
        caption: statusVM.headline
    }
}
