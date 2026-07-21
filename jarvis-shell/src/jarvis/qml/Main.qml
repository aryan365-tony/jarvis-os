import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import "components"

/**
 * Main.qml — Root window of the Jarvis OS interface.
 *
 * Architecture
 * ────────────
 * The window is borderless and fills the screen (cage forces full-screen anyway).
 * Layout is NOT a traditional desktop. Instead it's an AI-centric workspace:
 *
 *   ┌─────────────────────────────────────────────────────────┐
 *   │  StatusHud (top bar: model/voice/clock)                │
 *   │                                                         │
 *   │           ┌───────────┐                                 │
 *   │           │  AiCore   │  (central presence visualizer) │
 *   │           └───────────┘                                 │
 *   │                                                         │
 *   │  ┌──────────────┐              ┌────────────────────┐  │
 *   │  │  LogStream   │              │   ChatOverlay      │  │
 *   │  │  (bottom-L)  │              │   (right side)     │  │
 *   │  └──────────────┘              └────────────────────┘  │
 *   │                                                         │
 *   │  ┌───────────────────────────────────────────────────┐  │
 *   │  │  Composer (text input, docked bottom)             │  │
 *   │  └───────────────────────────────────────────────────┘  │
 *   └─────────────────────────────────────────────────────────┘
 *
 * The ParticleField renders behind everything as ambient background energy.
 * All panels use glassmorphism and fade/slide into view.
 */
Window {
    id: root
    visible: true
    visibility: Window.FullScreen
    color: Theme.void_
    title: "Jarvis"

    // State tracking
    property bool isStreaming: false
    property string currentTime: ""

    // ── Background: ambient particle grid ──────────────────────────────
    ParticleField {
        anchors.fill: parent
        z: 0
    }

    // ── Subtle animated radial gradient behind AI core ─────────────────
    Rectangle {
        id: ambientGlow
        anchors.centerIn: parent
        width: 600
        height: 600
        radius: 300
        color: "transparent"
        opacity: 0.15

        // Simulated via nested circles with varying opacity
        Rectangle {
            anchors.centerIn: parent
            width: 500
            height: 500
            radius: 250
            color: Theme.cyan
            opacity: 0.03
        }
        Rectangle {
            anchors.centerIn: parent
            width: 350
            height: 350
            radius: 175
            color: Theme.cyan
            opacity: 0.05
        }

        SequentialAnimation on opacity {
            loops: Animation.Infinite
            NumberAnimation { to: 0.2; duration: Theme.durationBreath; easing.type: Easing.InOutSine }
            NumberAnimation { to: 0.08; duration: Theme.durationBreath; easing.type: Easing.InOutSine }
        }
    }

    // ── Status HUD (top) ───────────────────────────────────────────────
    StatusHud {
        id: statusHud
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        z: 10
        modelState: jarvis.modelState
        voiceState: jarvis.voiceState
        currentTime: root.currentTime
    }

    // ── Central AI Core Visualizer ─────────────────────────────────────
    AiCore {
        id: aiCore
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.18
        z: 5
        isThinking: root.isStreaming
        modelState: jarvis.modelState
    }

    // ── Log Stream (bottom-left floating panel) ────────────────────────
    LogStream {
        id: logStream
        anchors.left: parent.left
        anchors.bottom: composerBar.top
        anchors.leftMargin: Theme.spaceL
        anchors.bottomMargin: Theme.spaceM
        width: Math.min(380, parent.width * 0.3)
        height: Math.min(220, parent.height * 0.25)
        z: 10
    }

    // ── Chat Overlay (right side) ──────────────────────────────────────
    ChatOverlay {
        id: chatOverlay
        anchors.right: parent.right
        anchors.top: statusHud.bottom
        anchors.bottom: composerBar.top
        anchors.rightMargin: Theme.spaceL
        anchors.topMargin: Theme.spaceL
        anchors.bottomMargin: Theme.spaceM
        width: Math.min(520, parent.width * 0.4)
        z: 10
    }

    // ── Composer (bottom input bar) ────────────────────────────────────
    Composer {
        id: composerBar
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: Theme.spaceL
        z: 15

        onMessageSubmitted: function(text) {
            jarvis.sendMessage(text)
        }
    }

    // ── Signal wiring from Python bridge ───────────────────────────────
    Connections {
        target: jarvis

        function onClockTick(time) {
            root.currentTime = time
        }

        function onStreamingStarted() {
            root.isStreaming = true
            aiCore.isThinking = true
        }

        function onStreamingDelta(chunk) {
            chatOverlay.appendStreamChunk(chunk)
        }

        function onStreamingFinished(fullText) {
            root.isStreaming = false
            aiCore.isThinking = false
            chatOverlay.finalizeStream(fullText)
        }

        function onConversationAppended(role, text) {
            if (role === "user") {
                chatOverlay.addUserMessage(text)
            }
        }

        function onLogAppended(source, level, message) {
            logStream.addEntry(source, level, message)
        }

        function onModelStateChanged(state) {
            statusHud.modelState = state
            aiCore.modelState = state
        }

        function onVoiceStateChanged(state) {
            statusHud.voiceState = state
        }
    }

    // ── Initial system message ─────────────────────────────────────────
    Component.onCompleted: {
        chatOverlay.addSystemMessage("Jarvis is online. Type to begin — voice will join when ready.")
    }
}
