<div align="center">

<img src="icon.png" height="120" alt="小组件自定义高度">
<h1>小组件布局</h1>

[![版本](https://img.shields.io/badge/%E7%89%88%E6%9C%AC-1.0.2-5A9BFF?style=for-the-badge)](https://github.com/Kryon2025/Class-Widgets-2-Widget-height/releases)
[![星标](https://img.shields.io/github/stars/Kryon2025/Class-Widgets-2-Widget-height?style=for-the-badge&color=orange&label=%E6%98%9F%E6%A0%87)](https://github.com/Kryon2025/Class-Widgets-2-Widget-height)
[![开源许可](https://img.shields.io/github/license/Kryon2025/Class-Widgets-2-Widget-height?style=for-the-badge&label=%E5%BC%80%E6%BA%90%E8%AE%B8%E5%8F%AF%E8%AF%81)](https://github.com/Kryon2025/Class-Widgets-2-Widget-height/blob/main/LICENSE)
[![下载量](https://img.shields.io/github/downloads/Kryon2025/Class-Widgets-2-Widget-height/total.svg?label=%E4%B8%8B%E8%BD%BD%E9%87%8F&color=green&style=for-the-badge)](https://github.com/Kryon2025/Class-Widgets-2-Widget-height/releases)

</div>

> [!NOTE]
> 当前版本 **1.0.2**，要求 Class Widgets 2 的插件 API `>=0.6.0`。

无组件界面的辅助插件。由Deepseek V4 Pro开发。

> <span style="color:red;">该插件不再更新，所有插件功能已转移至“Kryon的更多设置”</span>

## 功能特色

为Class Widgets 2增加自定义小组件显示高度及隐藏深度功能，避免隐藏时出现漏字情况。

## 在主程序「设置 - 小组件布局」中提供两个调节项：

- **展示高度**：组件距屏幕顶部的距离（顶部停靠时生效，-1 为默认偏移）
- **隐藏深度**：隐藏时组件保留在屏幕边缘的宽度

插件加载时会自动为主程序 `WidgetsContainer.qml` 打入补丁（幂等，可重复加载），
使上述配置生效；若主程序还原了该文件，下次启动会自动重新打入。

> 修改配置后不需要重启主程序
