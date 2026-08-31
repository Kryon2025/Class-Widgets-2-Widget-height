import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import ClassWidgets.Plugins

/*!
    小组件布局插件设置页。

    配置经官方插件配置通道持久化（plugins.configs.com.kryon.widgets-high），
    通过 backend 槽读写（getConfig / setDisplayHeight / setHideDepth），
    改动即保存；主程序 WidgetsContainer 的轮询 Timer 实时应用，无需重启。
*/

PluginPage {
    id: page
    pluginId: "com.kryon.widgets-high"
    title: qsTr("小组件布局")

    property var info: ({})
    property bool syncingControls: false

    Component.onCompleted: {
        Qt.callLater(reload)
    }

    onBackendChanged: {
        if (backend) {
            Qt.callLater(reload)
        }
    }

    function reload() {
        if (!backend) {
            return
        }
        var newInfo = backend.getConfig()
        if (newInfo) {
            info = newInfo
        }
        syncControls()
    }

    function syncControls() {
        page.syncingControls = true
        var d = info.display_height
        displaySlider.value = (d !== undefined && d !== null && d >= 0)
            ? d : (Configs.data.preferences.widgets_offset_y || 0)
        hideSlider.value = (info.hide_depth !== undefined && info.hide_depth !== null)
            ? info.hide_depth : 24
        page.syncingControls = false
    }

    Connections {
        target: backend
        function onConfigChanged() { page.reload() }
    }

    // ------------------------------------------------------------------ 展示高度
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 4

        Text {
            typography: Typography.BodyStrong
            text: qsTr("展示高度")
        }

        SettingCard {
            Layout.fillWidth: true
            icon.name: "ic_fluent_arrow_up_20_regular"
            title: qsTr("组件距屏幕顶部的距离")
            description: qsTr("顶部停靠时生效；拖动即时应用，无需重启")

            Slider {
                id: displaySlider
                objectName: "displaySlider"
                Layout.fillWidth: true
                Layout.preferredWidth: 260
                from: 0
                to: 800
                stepSize: 4
                tickmarks: true
                tickFrequency: 200
                toolTip.text: Math.round(value) + " px"
                onValueChanged: {
                    if (pressed && !page.syncingControls && backend) {
                        backend.setDisplayHeight(value)
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------ 隐藏深度
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 4

        Text {
            typography: Typography.BodyStrong
            text: qsTr("隐藏深度")
        }

        SettingCard {
            Layout.fillWidth: true
            icon.name: "ic_fluent_arrow_hide_20_regular"
            title: qsTr("隐藏时保留在屏幕边缘的宽度")
            description: qsTr("拖动即时应用，无需重启")

            Slider {
                id: hideSlider
                objectName: "hideSlider"
                Layout.fillWidth: true
                Layout.preferredWidth: 260
                from: 0
                to: 200
                stepSize: 4
                tickmarks: true
                tickFrequency: 50
                toolTip.text: Math.round(value) + " px"
                onValueChanged: {
                    if (pressed && !page.syncingControls && backend) {
                        backend.setHideDepth(value)
                    }
                }
            }
        }
    }
}
