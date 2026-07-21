import QtQuick
import QtQuick.Controls
import ".."

/**
 * LogStream — floating log panel showing backend activity.
 * Fed by the Python event bus. Shows source, level, and message
 * with level-based coloring (info=white, warning=amber, error=red).
 */
GlassPanel {
    id: logPanel

    function addEntry(source, level, message) {
        if (logModel.count > 200) logModel.remove(0)
        logModel.append({ source: source, level: level, message: message })
        logList.positionViewAtEnd()
    }

    Text {
        id: title
        anchors.top: parent.top; anchors.left: parent.left
        anchors.topMargin: Theme.spaceS; anchors.leftMargin: Theme.spaceS
        text: "SYSTEM LOG"; color: Theme.cyan
        font.pixelSize: Theme.fontSmall; font.bold: true
        font.letterSpacing: 2; font.family: Theme.fontFamily; opacity: 0.5
    }

    Rectangle {
        id: sep; anchors.top: title.bottom
        anchors.left: parent.left; anchors.right: parent.right
        anchors.topMargin: Theme.spaceXS; anchors.leftMargin: Theme.spaceS
        anchors.rightMargin: Theme.spaceS; height: 1
        color: Theme.border; opacity: 0.3
    }

    ListModel { id: logModel }

    ListView {
        id: logList
        anchors.top: sep.bottom; anchors.bottom: parent.bottom
        anchors.left: parent.left; anchors.right: parent.right
        anchors.margins: Theme.spaceS; anchors.topMargin: Theme.spaceXS
        clip: true; spacing: 2; model: logModel

        ScrollBar.vertical: ScrollBar {
            policy: ScrollBar.AsNeeded
            contentItem: Rectangle { implicitWidth: 2; radius: 1; color: Theme.textDim; opacity: 0.3 }
        }

        delegate: Row {
            width: logList.width; spacing: Theme.spaceS
            Text {
                text: model.source
                color: Theme.textDim
                font.pixelSize: Theme.fontSmall
                font.family: Theme.fontFamily
                width: 50; elide: Text.ElideRight
            }
            Text {
                width: parent.width - 58
                text: model.message
                color: {
                    switch(model.level) {
                        case "warning": return Theme.amber
                        case "error": return Theme.red
                        default: return Theme.textSecondary
                    }
                }
                font.pixelSize: Theme.fontSmall
                font.family: Theme.fontFamily
                wrapMode: Text.NoWrap; elide: Text.ElideRight
            }
        }
    }
}
