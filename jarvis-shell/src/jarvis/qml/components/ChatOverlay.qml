import QtQuick
import QtQuick.Controls
import ".."

GlassPanel {
    id: chatPanel

    function addUserMessage(text) {
        messageModel.append({ role: "user", text: text, streaming: false })
        scrollToBottom()
    }

    function addSystemMessage(text) {
        messageModel.append({ role: "system", text: text, streaming: false })
        scrollToBottom()
    }

    function appendStreamChunk(chunk) {
        if (messageModel.count === 0 || !messageModel.get(messageModel.count - 1).streaming) {
            messageModel.append({ role: "assistant", text: chunk, streaming: true })
        } else {
            var last = messageModel.get(messageModel.count - 1)
            messageModel.setProperty(messageModel.count - 1, "text", last.text + chunk)
        }
        scrollToBottom()
    }

    function finalizeStream(fullText) {
        if (messageModel.count > 0 && messageModel.get(messageModel.count - 1).streaming) {
            messageModel.setProperty(messageModel.count - 1, "text", fullText)
            messageModel.setProperty(messageModel.count - 1, "streaming", false)
        }
    }

    function scrollToBottom() { scrollTimer.restart() }

    Text {
        id: title
        anchors.top: parent.top; anchors.left: parent.left
        anchors.topMargin: Theme.spaceS; anchors.leftMargin: Theme.spaceS
        text: "CONVERSATION"; color: Theme.cyan
        font.pixelSize: Theme.fontSmall; font.bold: true
        font.letterSpacing: 2; font.family: Theme.fontFamily; opacity: 0.6
    }

    Rectangle {
        id: sep; anchors.top: title.bottom
        anchors.left: parent.left; anchors.right: parent.right
        anchors.topMargin: Theme.spaceS; anchors.leftMargin: Theme.spaceS
        anchors.rightMargin: Theme.spaceS; height: 1
        color: Theme.border; opacity: 0.4
    }

    ListModel { id: messageModel }

    ListView {
        id: messageList
        anchors.top: sep.bottom; anchors.bottom: parent.bottom
        anchors.left: parent.left; anchors.right: parent.right
        anchors.margins: Theme.spaceS; anchors.topMargin: Theme.spaceS
        clip: true; spacing: Theme.spaceS; model: messageModel
        ScrollBar.vertical: ScrollBar {
            policy: ScrollBar.AsNeeded
            contentItem: Rectangle { implicitWidth: 3; radius: 1.5; color: Theme.textDim; opacity: 0.4 }
        }
        delegate: MessageBubble {
            width: messageList.width; role: model.role
            messageText: model.text; isStreaming: model.streaming
        }
    }

    Timer { id: scrollTimer; interval: 50; onTriggered: messageList.positionViewAtEnd() }
}
