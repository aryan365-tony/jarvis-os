import QtQuick
import ".."

/**
 * StatusHud — Top HUD bar displaying system state at a glance.
 *
 * Inspired by aircraft HUD overlays: minimal, high-information-density,
 * always visible. Shows:
 *   • JARVIS branding (left)
 *   • Model status indicator
 *   • Voice status indicator
 *   • System clock (right)
 *
 * All state is driven by properties bound to the Python bridge.
 */
GlassPanel {
    id: hud
    height: 44
    radius: 0

    property string modelState: "initializing"
    property bool modelOnline: false
    property string voiceState: "initializing"
    property string currentTime: ""
    signal toggleModelOnlineRequested(bool enabled)

    // Override glass for a subtler top bar
    color: Qt.rgba(0.03, 0.04, 0.06, 0.85)
    border.width: 0

    // Bottom edge accent line
    Rectangle {
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        height: 1
        color: Theme.border
        opacity: 0.6
    }

    Row {
        anchors.fill: parent
        anchors.leftMargin: Theme.spaceXL
        anchors.rightMargin: Theme.spaceXL
        spacing: Theme.spaceXL

        // ── Branding ───────────────────────────────────────────────────
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: "JARVIS"
            color: Theme.cyan
            font.pixelSize: Theme.fontLarge
            font.bold: true
            font.letterSpacing: 4
            font.family: Theme.fontFamily

            // Subtle glow animation
            opacity: 0.9
            SequentialAnimation on opacity {
                loops: Animation.Infinite
                NumberAnimation { to: 1.0; duration: 2000; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.8; duration: 2000; easing.type: Easing.InOutSine }
            }
        }

        // ── Separator ──────────────────────────────────────────────────
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: 1; height: 20
            color: Theme.border
        }

        // ── Model status pill ──────────────────────────────────────────
        Row {
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.spaceS

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 8; height: 8; radius: 4
                color: Theme.statusColor(modelState)

                SequentialAnimation on opacity {
                    loops: Animation.Infinite
                    NumberAnimation { to: 1.0; duration: 1000; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 0.5; duration: 1000; easing.type: Easing.InOutSine }
                }
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "MODEL"
                color: Theme.textSecondary
                font.pixelSize: Theme.fontSmall
                font.letterSpacing: 1.5
                font.family: Theme.fontFamily
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: modelState
                color: Theme.statusColor(modelState)
                font.pixelSize: Theme.fontSmall
                font.family: Theme.fontFamily
                opacity: 0.8
            }
        }

        // ── Voice status pill ──────────────────────────────────────────
        Row {
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.spaceS

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 8; height: 8; radius: 4
                color: Theme.statusColor(voiceState)

                SequentialAnimation on opacity {
                    loops: Animation.Infinite
                    NumberAnimation { to: 1.0; duration: 1200; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 0.5; duration: 1200; easing.type: Easing.InOutSine }
                }
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "VOICE"
                color: Theme.textSecondary
                font.pixelSize: Theme.fontSmall
                font.letterSpacing: 1.5
                font.family: Theme.fontFamily
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: voiceState
                color: Theme.statusColor(voiceState)
                font.pixelSize: Theme.fontSmall
                font.family: Theme.fontFamily
                opacity: 0.8
            }
        }

        // ── Model online/offline control ──────────────────────────────
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: 122
            height: 28
            radius: 14
            color: modelOnline ? Qt.rgba(0.10, 0.30, 0.20, 0.90) : Qt.rgba(0.30, 0.18, 0.12, 0.90)
            border.width: 1
            border.color: modelOnline ? Theme.green : Theme.amber

            Text {
                anchors.centerIn: parent
                text: modelOnline ? "GO OFFLINE" : "GO ONLINE"
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSmall
                font.bold: true
                font.family: Theme.fontFamily
                font.letterSpacing: 1.2
            }

            MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: hud.toggleModelOnlineRequested(!modelOnline)
            }
        }

        // ── Spacer ─────────────────────────────────────────────────────
        Item { width: 10 }
    }

    // ── Clock (right-aligned) ──────────────────────────────────────────
    Text {
        anchors.right: parent.right
        anchors.rightMargin: Theme.spaceXL
        anchors.verticalCenter: parent.verticalCenter
        text: currentTime
        color: Theme.textDim
        font.pixelSize: Theme.fontBody
        font.letterSpacing: 2
        font.family: Theme.fontFamily
    }
}
