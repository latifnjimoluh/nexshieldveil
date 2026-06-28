// A frosted-glass surface: translucent panel colour + hairline edge glow.
// The signature material — depth comes from translucency and a faint accent border,
// never from hard drop shadows (see docs/DESIGN_TOKENS.md).
import QtQuick

Rectangle {
    id: root
    radius: Theme.radius("lg")
    color: Qt.rgba(Qt.color(Theme.panel).r,
                   Qt.color(Theme.panel).g,
                   Qt.color(Theme.panel).b,
                   0.86)
    border.width: 1
    // Faint accent edge: the "light caught in frosted glass" cue.
    border.color: Qt.rgba(Qt.color(Theme.accent).r,
                          Qt.color(Theme.accent).g,
                          Qt.color(Theme.accent).b,
                          0.18)

    Behavior on color {
        enabled: !Theme.reduced_motion
        ColorAnimation { duration: Theme.duration("standard") }
    }
}
