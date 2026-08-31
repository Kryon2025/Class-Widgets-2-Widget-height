"""小组件高度/深度调节插件（com.kryon.widgets-high）

无组件界面；在主程序设置页提供两个横向拉条：
- 展示高度：组件距屏幕顶部的距离（顶部停靠时生效；-1 = 跟随主程序 Y 偏移）
- 隐藏深度：隐藏时保留在屏幕边缘的宽度

配置经官方插件配置通道持久化（plugins.configs.com.kryon.widgets-high），
设置页通过 backend 槽读写，改动即 api.config.save() 保存。

插件加载时自动给主程序 WidgetsContainer.qml 打补丁（幂等）：
- 新增 displayTop / hideDepthOverride 属性 + 轮询 Timer（300ms）
  读取 Configs.data.plugins.configs["com.kryon.widgets-high"] 并实时应用；
- hideMargin 支持可配置深度（保留新版 floatingMode 逻辑）；
- calcY 顶部停靠偏移支持可配置展示高度。
主程序还原文件后，下次启动会自动重新打入。
"""

import json
from pathlib import Path

from ClassWidgets.SDK import CW2Plugin, ConfigBaseModel, PluginAPI
from loguru import logger
from pydantic import Field
from PySide6.QtCore import Signal, Slot

PLUGIN_ID = "com.kryon.widgets-high"
CFG_KEY = "com.kryon.widgets-high"
OLD_CFG_KEY = "com.high"  # 历史版本插件 id，用于迁移旧配置

PATCH_MARK = "// patched by com.kryon.widgets-high"
SYNC_MARK = "kryonWidgetsHighSyncTimer"


class HighConfig(ConfigBaseModel):
    """插件配置（由主程序持久化到 plugins.configs.com.kryon.widgets-high）。"""

    display_height: float = -1   # 展示高度（组件距屏幕顶部距离 px；-1 = 跟随默认偏移）
    hide_depth: float = 24       # 隐藏深度（隐藏时保留在屏幕边缘的宽度 px）


def _root_dir() -> Path:
    # <主程序根>/plugins/com.kryon.widgets-high/main.py -> 主程序根
    return Path(__file__).resolve().parent.parent.parent


def _widgets_container_path() -> Path:
    return _root_dir() / "src" / "qml" / "ClassWidgets" / "Components" / "WidgetsContainer.qml"


# ---------------------------------------------------------------------------
# 补丁片段
# ---------------------------------------------------------------------------

# 新版主程序（含 floatingMode）的 hideMargin 块
_HIDE_MARGIN_OLD = (
    "    property real hideMargin: {\n"
    "        if (floatingMode) return 0  // 浮窗模式下完全移出窗口\n"
    "        switch (Qt.platform.os) {\n"
    "            case \"osx\":\n"
    "                return 48\n"
    "            default:\n"
    "                return 24\n"
    "        }\n"
    "    } // 隐藏时保留的可点击空间"
)

_HIDE_MARGIN_NEW = (
    "    // patched by com.kryon.widgets-high：展示高度 / 隐藏深度（Timer 实时同步）\n"
    "    property real displayTop: -1\n"
    "    property real hideDepthOverride: -1\n"
    "    property real hideMargin: {\n"
    "        if (floatingMode) return 0  // 浮窗模式下完全移出窗口\n"
    "        var comHighDef = Qt.platform.os === \"osx\" ? 48 : 24\n"
    "        return hideDepthOverride >= 0 ? hideDepthOverride : comHighDef\n"
    "    } // 隐藏时保留的可点击空间"
)

_TIMER_BLOCK = (
    "\n    // patched by com.kryon.widgets-high：实时同步插件配置（展示高度 / 隐藏深度）\n"
    "    Timer {\n"
    "        id: " + SYNC_MARK + "\n"
    "        interval: 300\n"
    "        repeat: true\n"
    "        running: true\n"
    "        onTriggered: {\n"
    "            var cfg = (typeof Configs !== \"undefined\" && Configs.data.plugins\n"
    "                && Configs.data.plugins.configs)\n"
    "                ? Configs.data.plugins.configs[\"" + CFG_KEY + "\"] : null\n"
    "            var dt = (cfg && cfg.display_height !== undefined && cfg.display_height !== null)\n"
    "                ? cfg.display_height : -1\n"
    "            var hd = (cfg && cfg.hide_depth !== undefined && cfg.hide_depth !== null)\n"
    "                ? cfg.hide_depth : -1\n"
    "            widgetsContainer.displayTop = dt\n"
    "            widgetsContainer.hideDepthOverride = hd\n"
    "        }\n"
    "    }\n"
)

_CALCY_OLD = "y = preferences.widgets_offset_y"
_CALCY_NEW = "y = (displayTop >= 0 ? displayTop : preferences.widgets_offset_y)"
_SIGNAL_ANCHOR = "    signal contentGeometryChanged()\n"


def apply_patch(target: Path | None = None) -> bool:
    """给 WidgetsContainer.qml 打补丁（幂等）。"""
    target = target or _widgets_container_path()
    if not target.exists():
        logger.warning("[com.kryon.widgets-high] 未找到 WidgetsContainer.qml: {}", target)
        return False

    t = target.read_text(encoding="utf-8")

    # 已是最新补丁
    if SYNC_MARK in t and _TIMER_BLOCK in t:
        logger.info("[com.kryon.widgets-high] 补丁已是最新版，跳过")
        return True

    # 锚点缺失（可能被旧版 com.high 补丁污染或主程序结构再次变化）
    if _HIDE_MARGIN_OLD not in t:
        logger.warning("[com.kryon.widgets-high] hideMargin 锚点未找到，跳过打补丁（主程序结构可能已变化）")
        return False

    t = t.replace(_HIDE_MARGIN_OLD, _HIDE_MARGIN_NEW, 1)
    t = t.replace(_SIGNAL_ANCHOR, _TIMER_BLOCK + _SIGNAL_ANCHOR, 1)

    cnt = t.count(_CALCY_OLD)
    if cnt == 0:
        logger.warning("[com.kryon.widgets-high] calcY 锚点未找到，跳过")
        return False
    t = t.replace(_CALCY_OLD, _CALCY_NEW)

    try:
        target.write_text(t, encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        logger.error("[com.kryon.widgets-high] 补丁写回失败: {}", e)
        return False

    logger.info("[com.kryon.widgets-high] 补丁已打入（calcY {} 处）", cnt)
    return True


# ---------------------------------------------------------------------------
# 插件主体
# ---------------------------------------------------------------------------

class Plugin(CW2Plugin):
    """小组件高度/深度调节插件（无组件界面）。"""

    configChanged = Signal()

    def __init__(self, api: PluginAPI):
        super().__init__(api)
        self._config = HighConfig()

    def on_load(self):
        super().on_load()
        try:
            self.api.config.register_plugin_model(self.pid, self._config)
            logger.info("[com.kryon.widgets-high] 配置模型注册成功: plugins.configs.{}", self.pid)
        except Exception as e:  # noqa: BLE001
            logger.warning("[com.kryon.widgets-high] 注册配置模型失败: {}", e)
        self._migrate_old_config()
        self.api.ui.register_settings_page(
            Path("qml") / "SettingsPage.qml",
            title="小组件布局",
            icon="ic_fluent_resize_20_regular",
        )
        apply_patch()
        logger.info("[com.kryon.widgets-high] 插件已加载")

    def on_unload(self):
        logger.info("[com.kryon.widgets-high] 插件已卸载")

    # ---- 旧配置迁移（com.high -> com.kryon.widgets-high）----

    def _migrate_old_config(self) -> None:
        try:
            cfg_file = _root_dir() / "configs" / "configs.json"
            data = json.loads(cfg_file.read_text(encoding="utf-8"))
            old = data.get("plugins", {}).get("configs", {}).get(OLD_CFG_KEY)
            if not old:
                return
            # 仅在当前仍为默认值时才迁移，避免覆盖用户已设置的值
            if self._config.display_height == -1 and "display_height" in old:
                self._config.display_height = float(old["display_height"])
            if self._config.hide_depth == 24 and "hide_depth" in old:
                self._config.hide_depth = float(old["hide_depth"])
            self._save_config()
            logger.info("[com.kryon.widgets-high] 已迁移旧配置 {} -> {}", OLD_CFG_KEY, CFG_KEY)
        except Exception as e:  # noqa: BLE001
            logger.warning("[com.kryon.widgets-high] 迁移旧配置失败: {}", e)

    # ---- 设置页 backend ----

    @Slot(result=dict)
    def getConfig(self) -> dict:
        return self._config.model_dump()

    @Slot(float)
    def setDisplayHeight(self, value: float) -> None:
        self._config.display_height = float(value)
        self._save_config()
        self.configChanged.emit()

    @Slot(float)
    def setHideDepth(self, value: float) -> None:
        self._config.hide_depth = float(value)
        self._save_config()
        self.configChanged.emit()

    def _save_config(self) -> None:
        try:
            self.api.config.save()
        except Exception as e:  # noqa: BLE001
            logger.warning("[com.kryon.widgets-high] 保存配置失败: {}", e)
