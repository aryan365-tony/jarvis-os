import QtQuick
import ".."

/**
 * GlassPanel — reusable glassmorphic container.
 *
 * A translucent, bordered rectangle with subtle glow that serves as the
 * foundation for every floating panel in the interface. Uses CSS-like
 * glassmorphism: dark translucent background + border highlight.
 * (True backdrop-blur requires Qt GraphicalEffects which may not be available
 *  on all targets, so we achieve the glass look with opacity + color.)
 */
Rectangle {
    id: panel

    property alias contentItem: content
    default property alias contentData: content.data

    color: Theme.glassColor
    radius: Theme.radiusM
    border.color: Theme.glassBorder
    border.width: 1

    // Subtle top-edge highlight (simulates light hitting glass)
    Rectangle {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 1
        height: 1
        radius: parent.radius
        color: Qt.rgba(1, 1, 1, 0.06)
    }

    // Content container
    Item {
        id: content
        anchors.fill: parent
        anchors.margins: Theme.spaceM
    }

    // Entry animation
    opacity: 0
    Component.onCompleted: {
        entryAnim.start()
    }

    NumberAnimation {
        id: entryAnim
        target: panel
        property: "opacity"
        from: 0; to: 1
        duration: Theme.durationSlow
        easing.type: Easing.OutCubic
    }
}
