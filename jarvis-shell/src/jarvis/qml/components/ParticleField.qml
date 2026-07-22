import QtQuick
import ".."

/**
 * ParticleField — ambient background energy visualization.
 *
 * A field of softly drifting dots that creates the feeling of a living,
 * breathing environment. Dots drift slowly upward and respawn at the bottom.
 * Density and brightness are kept low to avoid distraction while still
 * conveying that the system is alive.
 *
 * Pure Canvas-based rendering for maximum performance (no Qt Particles
 * dependency needed).
 */
Item {
    id: field

    property int particleCount: 60
    property color particleColor: Theme.cyan
    property real maxOpacity: 0.25
    property real speed: 0.3

    Canvas {
        id: canvas
        anchors.fill: parent
        renderStrategy: Canvas.Threaded

        property var particles: []
        property real time: 0

        Component.onCompleted: {
            // Initialize particles with random positions
            var p = []
            for (var i = 0; i < particleCount; i++) {
                p.push({
                    x: Math.random() * width,
                    y: Math.random() * height,
                    size: 1 + Math.random() * 2,
                    speed: (0.1 + Math.random() * speed) * 0.5,
                    opacity: Math.random() * maxOpacity,
                    phase: Math.random() * Math.PI * 2
                })
            }
            particles = p
        }

        Timer {
            interval: 33  // ~30fps — sufficient for ambient particles
            running: true
            repeat: true
            onTriggered: {
                canvas.time += 0.033
                canvas.requestPaint()
            }
        }

        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)

            for (var i = 0; i < particles.length; i++) {
                var p = particles[i]

                // Drift upward, slight horizontal sway
                p.y -= p.speed
                p.x += Math.sin(canvas.time + p.phase) * 0.15

                // Respawn at bottom when off top
                if (p.y < -10) {
                    p.y = height + 10
                    p.x = Math.random() * width
                }

                // Wrap horizontal
                if (p.x < 0) p.x = width
                if (p.x > width) p.x = 0

                // Pulsing opacity
                var alpha = p.opacity * (0.5 + 0.5 * Math.sin(canvas.time * 0.8 + p.phase))

                ctx.beginPath()
                ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
                ctx.fillStyle = Qt.rgba(
                    particleColor.r,
                    particleColor.g,
                    particleColor.b,
                    alpha
                )
                ctx.fill()
            }
        }
    }

    // Faint grid overlay for depth
    Canvas {
        id: gridCanvas
        anchors.fill: parent
        opacity: 0.03

        onPaint: {
            var ctx = getContext("2d")
            ctx.strokeStyle = Theme.cyan.toString()
            ctx.lineWidth = 0.5
            var spacing = 80

            // Vertical lines
            for (var x = 0; x < width; x += spacing) {
                ctx.beginPath()
                ctx.moveTo(x, 0)
                ctx.lineTo(x, height)
                ctx.stroke()
            }

            // Horizontal lines
            for (var y = 0; y < height; y += spacing) {
                ctx.beginPath()
                ctx.moveTo(0, y)
                ctx.lineTo(width, y)
                ctx.stroke()
            }
        }

        Component.onCompleted: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
    }
}
