// First-run onboarding: honest intro + limits, explicit camera consent, first
// settings. The camera is never opened here — consent is only recorded. Binds to
// `onboardingVM`, `settingsVM`, `Theme`, `Tr`.
import QtQuick
import QtQuick.Controls.Basic

Item {
    id: root
    implicitWidth: 520
    implicitHeight: 480

    GlassPanel {
        anchors.fill: parent
        anchors.margins: Theme.space("md")

        Column {
            anchors.fill: parent
            anchors.margins: Theme.space("xl")
            spacing: Theme.space("lg")

            // Step progress (dots).
            Row {
                spacing: Theme.space("sm")
                Repeater {
                    model: onboardingVM.count
                    delegate: Rectangle {
                        required property int index
                        width: 8; height: 8; radius: 4
                        color: index === onboardingVM.index
                               ? Theme.accent : Theme.line
                    }
                }
            }

            Text {
                width: parent.width
                text: onboardingVM.title
                wrapMode: Text.WordWrap
                color: Theme.ink
                font.family: Theme.fontDisplay
                font.pixelSize: Theme.fontSize("display")
            }

            Text {
                width: parent.width
                text: onboardingVM.body
                wrapMode: Text.WordWrap
                color: Theme.inkSoft
                font.family: Theme.fontUi
                font.pixelSize: Theme.fontSize("base")
            }

            // Step 1: the honest limits, shown before any camera request.
            Column {
                visible: onboardingVM.show_limits
                width: parent.width
                spacing: Theme.space("xs")
                Text {
                    text: onboardingVM.limits_title
                    color: Theme.stateColor("paused")
                    font.family: Theme.fontUi
                    font.bold: true
                    font.pixelSize: Theme.fontSize("body")
                }
                Text {
                    width: parent.width
                    text: onboardingVM.limits_body
                    wrapMode: Text.WordWrap
                    color: Theme.inkSoft
                    font.family: Theme.fontUi
                    font.pixelSize: Theme.fontSize("body")
                }
            }

            // Step 2: explicit camera consent.
            Row {
                visible: onboardingVM.show_camera_consent
                spacing: Theme.space("md")
                PrimaryButton {
                    objectName: "allowButton"
                    text: Tr.t("onboarding.step2.allow")
                    onClicked: onboardingVM.allow_camera()
                }
                PrimaryButton {
                    objectName: "skipButton"
                    primary: false
                    text: Tr.t("onboarding.step2.later")
                    onClicked: onboardingVM.skip_camera()
                }
            }

            // Step 3: a first masking choice + start-at-login.
            Column {
                visible: onboardingVM.is_last
                width: parent.width
                spacing: Theme.space("sm")
                Text {
                    text: Tr.t("onboarding.step3.masking")
                    color: Theme.ink
                    font.family: Theme.fontUi
                    font.pixelSize: Theme.fontSize("body")
                }
                ButtonGroup { id: obMasking }
                Repeater {
                    model: settingsVM.masking_options
                    delegate: RadioButton {
                        required property var modelData
                        text: modelData.label + (modelData.live ? "" : "  (" + modelData.note + ")")
                        enabled: modelData.live
                        checked: settingsVM.masking_strategy === modelData.id
                        ButtonGroup.group: obMasking
                        Accessible.name: text
                        onClicked: settingsVM.set_masking_strategy(modelData.id)
                    }
                }
                CheckBox {
                    objectName: "startAtLogin"
                    text: Tr.t("onboarding.step3.startup")
                    checked: settingsVM.start_at_login
                    Accessible.name: text
                    onToggled: settingsVM.set_start_at_login(checked)
                }
            }
        }

        // Footer navigation.
        Row {
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: Theme.space("xl")
            spacing: Theme.space("md")

            PrimaryButton {
                objectName: "backButton"
                primary: false
                visible: !onboardingVM.is_first
                text: Tr.t("common.back")
                onClicked: onboardingVM.back()
            }
            PrimaryButton {
                objectName: "nextButton"
                visible: !onboardingVM.is_last
                text: Tr.t("common.next")
                onClicked: onboardingVM.next()
            }
            PrimaryButton {
                objectName: "finishButton"
                visible: onboardingVM.is_last
                text: Tr.t("onboarding.finish")
                onClicked: onboardingVM.finish()
            }
        }
    }
}
