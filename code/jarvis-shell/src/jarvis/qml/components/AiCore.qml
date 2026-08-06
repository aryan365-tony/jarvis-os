import QtQuick
import ".."

/**
 * AiCore — Central AI presence visualizer.
 *
 * A concentric ring system that communicates AI state through motion:
 *   • Idle:     slow breathing pulse, calm cyan glow
 *   • Thinking: faster rotation, expanded rings, brighter glow
 *   • Ready:    steady green-cyan pulse
 *   • Error:    red pulsing alert
 *
 * The rings rotate at different speeds to create depth and life.
 * This is the "heart" of the interface — the user always knows the AI is alive.
 */
Item {
    id: core
    width: 200
    height: 200

    property bool isThinking: false
    property string modelState: "initializing"

    // Derived colors
    property color activeColor: {
        if (isThinking) return Theme.cyan
        return Theme.statusColor(modelState)
    }

    property real breathScale: 1.0
    property real ringOpacity: 0.6

    // ── Outer ring (slowest rotation) ──────────────────────────────────
    Rectangle {
        id: outerRing
        anchors.centerIn: parent
        width: 180 * breathScale
        height: width
        radius: width / 2
        color: "transparent"
        border.color: Qt.rgba(activeColor.r, activeColor.g, activeColor.b, 0.15)
        border.width: 1

        Behavior on width { NumberAnimation { duration: Theme.durationSlow; easing.type: Easing.OutCubic } }
        Behavior on border.color { ColorAnimation { duration: Theme.durationNormal } }

        RotationAnimation on rotation {
            from: 0; to: 360
            duration: isThinking ? 6000 : 20000
            loops: Animation.Infinite
        }

        // Accent arc (top)
        Rectangle {
            width: 40; height: 3; radius: 1.5
            color: activeColor
            opacity: ringOpacity * 0.8
            anchors.horizontalCenter: parent.horizontalCenter
            y: 0
        }
    }

    // ── Middle ring ────────────────────────────────────────────────────
    Rectangle {
        id: midRing
        anchors.centerIn: parent
        width: 130 * breathScale
        height: width
        radius: width / 2
        color: "transparent"
        border.color: Qt.rgba(activeColor.r, activeColor.g, activeColor.b, 0.25)
        border.width: 1.5

        Behavior on width { NumberAnimation { duration: Theme.durationSlow; easing.type: Easing.OutCubic } }
        Behavior on border.color { ColorAnimation { duration: Theme.durationNormal } }

        RotationAnimation on rotation {
            from: 360; to: 0
            duration: isThinking ? 4000 : 15000
            loops: Animation.Infinite
        }

        // Accent arcs
        Rectangle {
            width: 30; height: 2; radius: 1
            color: activeColor
            opacity: ringOpacity
            anchors.horizontalCenter: parent.horizontalCenter
            y: 0
        }
        Rectangle {
            width: 20; height: 2; radius: 1
            color: activeColor
            opacity: ringOpacity * 0.6
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height - 2
        }
    }

    // ── Inner ring ─────────────────────────────────────────────────────
    Rectangle {
        id: innerRing
        anchors.centerIn: parent
        width: 80 * breathScale
        height: width
        radius: width / 2
        color: "transparent"
        border.color: Qt.rgba(activeColor.r, activeColor.g, activeColor.b, 0.4)
        border.width: 2

        Behavior on width { NumberAnimation { duration: Theme.durationSlow; easing.type: Easing.OutCubic } }
        Behavior on border.color { ColorAnimation { duration: Theme.durationNormal } }

        RotationAnimation on rotation {
            from: 0; to: 360
            duration: isThinking ? 2000 : 10000
            loops: Animation.Infinite
        }
    }

    // ── Core dot (center) ──────────────────────────────────────────────
    Rectangle {
        id: coreDot
        anchors.centerIn: parent
        width: 12
        height: 12
        radius: 6
        color: activeColor
        opacity: 0.9

        Behavior on color { ColorAnimation { duration: Theme.durationNormal } }
    }

    // ── Core glow ──────────────────────────────────────────────────────
    Rectangle {
        anchors.centerIn: parent
        width: 40
        height: 40
        radius: 20
        color: activeColor
        opacity: 0.08

        SequentialAnimation on opacity {
            loops: Animation.Infinite
            NumberAnimation { to: isThinking ? 0.2 : 0.12; duration: isThinking ? 800 : Theme.durationBreath; easing.type: Easing.InOutSine }
            NumberAnimation { to: 0.04; duration: isThinking ? 800 : Theme.durationBreath; easing.type: Easing.InOutSine }
        }

        Behavior on color { ColorAnimation { duration: Theme.durationNormal } }
    }

    // ── Breathing animation ────────────────────────────────────────────
    SequentialAnimation on breathScale {
        loops: Animation.Infinite
        NumberAnimation {
            to: isThinking ? 1.12 : 1.04
            duration: isThinking ? 1200 : Theme.durationBreath
            easing.type: Easing.InOutSine
        }
        NumberAnimation {
            to: isThinking ? 0.95 : 0.98
            duration: isThinking ? 1200 : Theme.durationBreath
            easing.type: Easing.InOutSine
        }
    }

    // ── Status label ───────────────────────────────────────────────────
    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.bottom
        anchors.topMargin: Theme.spaceM
        text: isThinking ? "PROCESSING" : modelState.toUpperCase()
        color: activeColor
        opacity: 0.7
        font.pixelSize: Theme.fontSmall
        font.letterSpacing: 3
        font.family: Theme.fontFamily

        Behavior on text {
            SequentialAnimation {
                NumberAnimation { target: parent; property: "opacity"; to: 0; duration: 100 }
                PropertyAction {}
                NumberAnimation { target: parent; property: "opacity"; to: 0.7; duration: 200 }
            }
        }
        Behavior on color { ColorAnimation { duration: Theme.durationNormal } }
    }

    // ── Entry animation ────────────────────────────────────────────────
    scale: 0.5
    opacity: 0
    Component.onCompleted: {
        scaleAnim.start()
        opacityAnim.start()
    }
    NumberAnimation { id: scaleAnim; target: core; property: "scale"; to: 1.0; duration: 1000; easing.type: Easing.OutBack }
    NumberAnimation { id: opacityAnim; target: core; property: "opacity"; to: 1.0; duration: 800; easing.type: Easing.OutCubic }
}
