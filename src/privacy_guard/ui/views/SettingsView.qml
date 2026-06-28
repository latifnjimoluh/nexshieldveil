// Preferences. Sliders/switches bind to `settingsVM` and push edits back through it
// (never touching the core directly). Honest masking: non-live styles are disabled
// with a 'soon' note. Binds to `settingsVM`, `Theme`, `Tr`.
import QtQuick
import QtQuick.Controls.Basic

Item {
    id: root
    implicitWidth: 560
    implicitHeight: 560

    component SectionTitle: Text {
        color: Theme.ink
        font.family: Theme.fontUi
        font.bold: true
        font.pixelSize: Theme.fontSize("title")
    }
    component FieldLabel: Text {
        color: Theme.inkSoft
        font.family: Theme.fontUi
        font.pixelSize: Theme.fontSize("body")
    }
    component ValueLabel: Text {
        color: Theme.accent
        font.family: Theme.fontMono
        font.pixelSize: Theme.fontSize("body")
    }

    GlassPanel {
        anchors.fill: parent
        anchors.margins: Theme.space("md")

        Flickable {
            anchors.fill: parent
            anchors.margins: Theme.space("xl")
            contentHeight: col.implicitHeight
            clip: true

            Column {
                id: col
                width: parent.width
                spacing: Theme.space("lg")

                Text {
                    text: settingsVM ? Tr.t("settings.title") : ""
                    color: Theme.ink
                    font.family: Theme.fontDisplay
                    font.pixelSize: Theme.fontSize("display")
                }

                // ---- Detection ---------------------------------------- //
                SectionTitle { text: Tr.t("settings.tab.detection") }

                FieldLabel { text: Tr.t("settings.sensitivity") }
                Row {
                    width: parent.width
                    spacing: Theme.space("md")
                    Slider {
                        objectName: "sensitivitySlider"
                        width: parent.width * 0.7
                        from: 5; to: 40; stepSize: 1
                        value: settingsVM.sensitivity_deg
                        Accessible.name: Tr.t("settings.sensitivity")
                        onMoved: settingsVM.set_sensitivity_deg(value)
                    }
                    ValueLabel {
                        anchors.verticalCenter: parent.verticalCenter
                        text: settingsVM.sensitivity_caption
                    }
                }
                FieldLabel {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    font.pixelSize: Theme.fontSize("caption")
                    text: Tr.t("settings.sensitivity.hint")
                }

                FieldLabel { text: Tr.t("settings.trigger") }
                Row {
                    width: parent.width
                    spacing: Theme.space("md")
                    Slider {
                        objectName: "triggerSlider"
                        width: parent.width * 0.7
                        from: 0; to: 2000; stepSize: 50
                        value: settingsVM.trigger_ms
                        Accessible.name: Tr.t("settings.trigger")
                        onMoved: settingsVM.set_trigger_ms(value)
                    }
                    ValueLabel {
                        anchors.verticalCenter: parent.verticalCenter
                        text: settingsVM.trigger_caption
                    }
                }

                FieldLabel { text: Tr.t("settings.release") }
                Row {
                    width: parent.width
                    spacing: Theme.space("md")
                    Slider {
                        objectName: "releaseSlider"
                        width: parent.width * 0.7
                        from: settingsVM.release_floor; to: 3000; stepSize: 50
                        value: settingsVM.release_ms
                        Accessible.name: Tr.t("settings.release")
                        onMoved: settingsVM.set_release_ms(value)
                    }
                    ValueLabel {
                        anchors.verticalCenter: parent.verticalCenter
                        text: settingsVM.release_caption
                    }
                }
                FieldLabel {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    font.pixelSize: Theme.fontSize("caption")
                    text: Tr.t("settings.release.hint")
                }

                Rectangle { width: parent.width; height: 1; color: Theme.line }

                // ---- Masking ------------------------------------------ //
                SectionTitle { text: Tr.t("settings.tab.masking") }
                FieldLabel { text: Tr.t("settings.masking.style") }
                ButtonGroup { id: maskingGroup }
                Repeater {
                    model: settingsVM.masking_options
                    delegate: RadioButton {
                        required property var modelData
                        text: modelData.label + (modelData.live ? "" : "  (" + modelData.note + ")")
                        enabled: modelData.live
                        checked: settingsVM.masking_strategy === modelData.id
                        ButtonGroup.group: maskingGroup
                        Accessible.name: text
                        onClicked: settingsVM.set_masking_strategy(modelData.id)
                    }
                }

                FieldLabel { text: Tr.t("settings.opacity") }
                Slider {
                    objectName: "opacitySlider"
                    width: parent.width * 0.7
                    from: 0; to: 1; stepSize: 0.01
                    value: settingsVM.opacity
                    Accessible.name: Tr.t("settings.opacity")
                    onMoved: settingsVM.set_opacity(value)
                }

                Rectangle { width: parent.width; height: 1; color: Theme.line }

                // ---- General ------------------------------------------ //
                SectionTitle { text: Tr.t("settings.tab.general") }

                CheckBox {
                    objectName: "startLoginSwitch"
                    text: Tr.t("settings.start_at_login")
                    checked: settingsVM.start_at_login
                    Accessible.name: text
                    onToggled: settingsVM.set_start_at_login(checked)
                }

                Row {
                    spacing: Theme.space("md")
                    FieldLabel {
                        anchors.verticalCenter: parent.verticalCenter
                        text: Tr.t("settings.language")
                    }
                    ComboBox {
                        objectName: "languageCombo"
                        model: settingsVM.languages
                        textRole: "label"
                        Accessible.name: Tr.t("settings.language")
                        currentIndex: {
                            for (var i = 0; i < model.length; i++)
                                if (model[i].code === settingsVM.language) return i
                            return 0
                        }
                        onActivated: settingsVM.set_language(model[currentIndex].code)
                    }
                }

                Row {
                    spacing: Theme.space("md")
                    FieldLabel {
                        anchors.verticalCenter: parent.verticalCenter
                        text: Tr.t("settings.theme")
                    }
                    Switch {
                        objectName: "themeSwitch"
                        checked: Theme.is_dark
                        text: Theme.is_dark ? Tr.t("settings.theme.dark") : Tr.t("settings.theme.light")
                        Accessible.name: Tr.t("settings.theme")
                        onToggled: Theme.is_dark = checked
                    }
                }
            }
        }
    }
}
