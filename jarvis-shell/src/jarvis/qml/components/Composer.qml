import QtQuick
import QtQuick.Controls
import ".."

/**
 * Composer — text input bar docked at the bottom.
 * Glassmorphic input field with send affordance and voice state indicator.
 */
GlassPanel {
    id: composer
    height: 56
    radius: Theme.radiusL

    signal messageSubmitted(string text)

    Row {
        anchors.fill: parent
        anchors.margins: Theme.spaceS
        spacing: Theme.spaceS

        // Cyan accent dot (alive indicator)
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: 6; height: 6; radius: 3
            color: Theme.cyan; opacity: 0.6
            SequentialAnimation on opacity {
                loops: Animation.Infinite
                NumberAnimation { to: 1.0; duration: 1500; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.3; duration: 1500; easing.type: Easing.InOutSine }
            }
        }

        TextField {
            id: inputField
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - sendBtn.width - 30
            height: 38
            placeholderText: "Ask Jarvis..."
            placeholderTextColor: Theme.textDim
            color: Theme.textPrimary
            font.pixelSize: Theme.fontBody
            font.family: Theme.fontFamily
            background: Rectangle {
                radius: Theme.radiusS
                color: Qt.rgba(0.04, 0.06, 0.09, 0.8)
                border.color: inputField.activeFocus ? Theme.cyan : Theme.border
                border.width: 1
                Behavior on border.color { ColorAnimation { duration: 200 } }
            }
            Keys.onReturnPressed: composer.submit()
            Keys.onEnterPressed: composer.submit()
        }

        // Send button
        Rectangle {
            id: sendBtn
            anchors.verticalCenter: parent.verticalCenter
            width: 38; height: 38; radius: Theme.radiusS
            color: inputField.text.trim() ? Theme.cyan : Theme.border
            opacity: inputField.text.trim() ? 1.0 : 0.4
            Behavior on color { ColorAnimation { duration: 200 } }
            Behavior on opacity { NumberAnimation { duration: 200 } }

            Text {
                anchors.centerIn: parent
                text: "▸"
                color: inputField.text.trim() ? Theme.void_ : Theme.textDim
                font.pixelSize: Theme.fontLarge; font.bold: true
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: composer.submit()
            }
        }
    }

    function submit() {
        var text = inputField.text.trim()
        if (text) {
            messageSubmitted(text)
            inputField.text = ""
        }
    }

    // Auto-focus on load
    Component.onCompleted: inputField.forceActiveFocus()
}
