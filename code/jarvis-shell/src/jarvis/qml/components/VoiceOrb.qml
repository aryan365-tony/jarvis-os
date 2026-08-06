import QtQuick
import ".."

/**
 * VoiceOrb.qml — the central voice presence (Phase 5).
 *
 * Reacts to jarvis.voiceActivity (phase + level). It is the visual heart of the
 * voice-first shell: a breathing orb that changes behaviour per phase.
 *
 *   idle       → slow gentle breathing pulse
 *   listening  → reactive ring whose radius tracks the live mic level
 *   thinking   → fast orbiting shimmer
 *   speaking   → rhythmic expansion synced to output
 *
 * Purely driven by properties so it also works with reduced-motion (animations
 * collapse to static states when durations are near-zero).
 */
Item {
    id: orb
    property string phase: "idle"
    property real level: 0.0        // 0..1 live audio level
    property color accent: Theme.cyan

    implicitWidth: 260
    implicitHeight: 260

    function phaseColor() {
        switch (phase) {
            case "listening": return Theme.cyan;
            case "thinking":  return Theme.purple;
            case "speaking":  return Theme.teal;
            default:          return Theme.cyanDim;
        }
    }

    // Outer reactive ring (tracks mic level when listening / speaking).
    Rectangle {
        id: ring
        anchors.centerIn: parent
        property real base: 180
        property real react: (orb.phase === "listening" || orb.phase === "speaking")
                             ? orb.level * 70 : 0
        width: base + react
        height: width
        radius: width / 2
        color: "transparent"
        border.width: 2
        border.color: orb.phaseColor()
        opacity: 0.5
        Behavior on width { NumberAnimation { duration: 90; easing.type: Easing.OutQuad } }
    }

    // Core disc.
    Rectangle {
        id: core
        anchors.centerIn: parent
        width: 120
        height: 120
        radius: 60
        color: orb.phaseColor()
        opacity: 0.85

        // Idle breathing.
        SequentialAnimation on scale {
            running: orb.phase === "idle"
            loops: Animation.Infinite
            NumberAnimation { to: 1.08; duration: Theme.durationBreath / 2; easing.type: Easing.InOutSine }
            NumberAnimation { to: 0.96; duration: Theme.durationBreath / 2; easing.type: Easing.InOutSine }
        }
        // Speaking pulse.
        SequentialAnimation on scale {
            running: orb.phase === "speaking"
            loops: Animation.Infinite
            NumberAnimation { to: 1.15; duration: 220; easing.type: Easing.OutQuad }
            NumberAnimation { to: 1.0;  duration: 220; easing.type: Easing.InQuad }
        }
    }

    // Thinking orbiter.
    Rectangle {
        id: orbiter
        visible: orb.phase === "thinking"
        width: 16
        height: 16
        radius: 8
        color: Theme.purple
        x: parent.width / 2 - 8
        y: parent.height / 2 - 90
        transformOrigin: Item.Center
        RotationAnimation on rotation {
            running: orb.phase === "thinking"
            loops: Animation.Infinite
            from: 0; to: 360; duration: 1200
        }
        // Rotate around the orb centre.
        Rotation { origin.x: 8; origin.y: 90 }
    }

    // Soft glow halo.
    Rectangle {
        anchors.centerIn: parent
        width: core.width * 2.2
        height: width
        radius: width / 2
        color: orb.phaseColor()
        opacity: 0.08 + orb.level * 0.12
        z: -1
    }
}
