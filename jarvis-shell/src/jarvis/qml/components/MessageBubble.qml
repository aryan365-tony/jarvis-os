import QtQuick
import ".."

/**
 * MessageBubble — a single chat message (user, assistant, or system).
 *
 * Visually distinct per role:
 *   • User:      right-aligned, blue-ish accent border
 *   • Assistant:  left-aligned, cyan/teal accent border
 *   • System:    centered, dimmed, no strong accent
 *
 * Entry animation slides the bubble in from the edge.
 */
Item {
    id: bubble
    width: parent ? parent.width : 400
    height: contentColumn.height + Theme.spaceM * 2

    property string role: "user"
    property string messageText: ""
    property bool isStreaming: false

    // Role-dependent styling
    property color accentColor: {
        switch (role) {
            case "user":      return Theme.blue
            case "assistant": return Theme.teal
            case "system":    return Theme.textDim
            default:          return Theme.textDim
        }
    }

    property real alignment: role === "user" ? 1.0 : 0.0

    Rectangle {
        id: bg
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: Math.min(parent.width * 0.85, contentColumn.implicitWidth + Theme.spaceXL * 2)

        // Alignment: user right, assistant left
        x: bubble.alignment * (parent.width - width)

        radius: Theme.radiusM
        color: Qt.rgba(Theme.surface.r, Theme.surface.g, Theme.surface.b, 0.7)
        border.color: Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.3)
        border.width: 1

        Column {
            id: contentColumn
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: Theme.spaceM
            spacing: Theme.spaceXS

            // Role label
            Text {
                text: {
                    switch (role) {
                        case "user":      return "YOU"
                        case "assistant": return "JARVIS"
                        case "system":    return "SYSTEM"
                        default:          return role.toUpperCase()
                    }
                }
                color: accentColor
                font.pixelSize: Theme.fontSmall
                font.bold: true
                font.letterSpacing: 1.5
                font.family: Theme.fontFamily
                opacity: 0.8
            }

            // Message body
            Text {
                id: bodyText
                width: parent.width
                text: messageText + (isStreaming ? " ▋" : "")
                color: role === "system" ? Theme.textSecondary : Theme.textPrimary
                font.pixelSize: Theme.fontBody
                font.family: Theme.fontFamily
                wrapMode: Text.Wrap
                lineHeight: 1.4
            }
        }
    }

    // ── Entry animation ────────────────────────────────────────────────
    opacity: 0
    transform: Translate { id: slideTransform; x: role === "user" ? 30 : -30 }

    Component.onCompleted: {
        entryOpacity.start()
        entrySlide.start()
    }

    NumberAnimation {
        id: entryOpacity
        target: bubble
        property: "opacity"
        from: 0; to: 1
        duration: Theme.durationNormal
        easing.type: Easing.OutCubic
    }
    NumberAnimation {
        id: entrySlide
        target: slideTransform
        property: "x"
        to: 0
        duration: Theme.durationNormal
        easing.type: Easing.OutCubic
    }
}
