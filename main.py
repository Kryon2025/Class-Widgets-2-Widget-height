"""小组件布局调节插件（com.high）

无组件界面；在主程序设置页提供两个横向拉条：
- 展示高度：组件距屏幕顶部的距离（顶部停靠时生效）
- 隐藏深度：隐藏时保留在屏幕边缘的宽度

配置通过官方插件配置通道持久化（plugins.configs.com.high，见 configs.json）；
设置页通过 backend 槽读写，改动即保存（api.config.save()）。

插件加载时自动给主程序 WidgetsContainer.qml 打补丁（幂等）：
- 新增 displayTop / hideDepthOverride 属性 + 轮询 Timer（300ms）
  读取 Configs.data.plugins.configs["com.high"] 并实时应用，
  拖动拉条后小组件界面即时跟随，无需重启。
若主程序还原了文件，下次启动会自动重新打入。
"""

from pathlib import Path

from ClassWidgets.SDK import CW2Plugin, ConfigBaseModel, PluginAPI
from loguru import logger
from pydantic import Field
from PySide6.QtCore import Signal, Slot

PLUGIN_ID = "com.high"

PATCH_MARK = "// patched by com.high"
SYNC_MARK = "comHighSyncTimer"

CFG_KEY = "com.high"
CFG_DISPLAY = "display_height"
CFG_HIDE = "hide_depth"


class HighConfig(ConfigBaseModel):
    """插件配置（由主程序持久化到 plugins.configs.com.high）。"""

    display_height: float = -1   # 展示高度（组件距屏幕顶部距离 px；-1 = 跟随默认偏移）
    hide_depth: float = 24       # 隐藏深度（隐藏时保留在屏幕边缘的宽度 px）


def _root_dir() -> Path:
    # <主程序根>/plugins/com.high/main.py -> 主程序根
    return Path(__file__).resolve().parent.parent.parent


def _widgets_container_path() -> Path:
    return _root_dir() / "src" / "qml" / "ClassWidgets" / "Components" / "WidgetsContainer.qml"


# ---------------------------------------------------------------------------
# 补丁（幂等，可反复加载；v1 -> v2 -> v3 自动升级）
# ---------------------------------------------------------------------------

_HIDE_MARGIN_OLD = (
    "    property real hideMargin: {\n"
    "        switch (Qt.platform.os) {\n"
    "            case \"osx\":\n"
    "                return 48\n"
    "            default:\n"
    "                return 24\n"
    "        }\n"
    "    } // 隐藏时保留的可点击空间"
)

_HIDE_MARGIN_NEW = (
    "    // patched by com.high：展示高度 / 隐藏深度（Timer 实时同步插件配置）\n"
    "    property real displayTop: -1\n"
    "    property real hideDepthOverride: -1\n"
    "    property real hideMargin: {\n"
    "        var comHighDef = Qt.platform.os === \"osx\" ? 48 : 24\n"
    "        return hideDepthOverride >= 0 ? hideDepthOverride : comHighDef\n"
    "    } // 隐藏时保留的可点击空间"
)

_TIMER_BLOCK = (
    "\n    // patched by com.high：实时同步插件配置（展示高度 / 隐藏深度）\n"
    "    Timer {\n"
    "        id: comHighSyncTimer\n"
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

# v2 实际写入的 hideMargin 块（注释带"由"字，与 v3 略有差异）
_HIDE_MARGIN_V2 = (
    "    // patched by com.high：展示高度 / 隐藏深度（由 Timer 实时同步插件配置）\n"
    "    property real displayTop: -1\n"
    "    property real hideDepthOverride: -1\n"
    "    property real hideMargin: {\n"
    "        var comHighDef = Qt.platform.os === \"osx\" ? 48 : 24\n"
    "        return hideDepthOverride >= 0 ? hideDepthOverride : comHighDef\n"
    "    } // 隐藏时保留的可点击空间"
)

# v2 实际写入的 Timer 块（读 plugins.com_high），精确匹配以便整体移除
_TIMER_V2 = (
    "\n"
    "    // patched by com.high：实时同步插件配置（展示高度 / 隐藏深度）\n"
    "    Timer {\n"
    "        id: comHighSyncTimer\n"
    "        interval: 300\n"
    "        repeat: true\n"
    "        running: true\n"
    "        onTriggered: {\n"
    "            var sec = (typeof Configs !== \"undefined\" && Configs.data.plugins\n"
    "                && Configs.data.plugins.com_high) ? Configs.data.plugins.com_high : null\n"
    "            var dt = (sec && sec.display_height !== undefined && sec.display_height !== null)\n"
    "                ? sec.display_height : -1\n"
    "            var hd = (sec && sec.hide_depth !== undefined && sec.hide_depth !== null)\n"
    "                ? sec.hide_depth : -1\n"
    "            widgetsContainer.displayTop = dt\n"
    "            widgetsContainer.hideDepthOverride = hd\n"
    "        }\n"
    "    }\n"
)


def _strip_any_old_patch(t: str) -> str:
    """移除任意旧版补丁（v1 绑定式 / v2 轮询式），还原原文件。"""
    # v1/v2 的 hideMargin 前置 displayTop 行（v1 绑定式）
    t = t.replace(
        "    property real displayTop: Configs.data.plugins.com_high.display_height ?? -1"
        " // patched by com.high\n", "", 1)
    # v1 的 hide_depth 读配置（v1 特有）
    t = t.replace(
        "case \"osx\":\n                return Configs.data.plugins.com_high.hide_depth ?? 48",
        "case \"osx\":\n                return 48", 1)
    t = t.replace(
        "default:\n                return Configs.data.plugins.com_high.hide_depth ?? 24",
        "default:\n                return 24", 1)
    # v2/v3 的 hideMargin 整体块（含 displayTop/hideDepthOverride 属性）
    for blk in (_HIDE_MARGIN_V2, _HIDE_MARGIN_NEW):
        if blk in t:
            t = t.replace(blk, _HIDE_MARGIN_OLD, 1)
            break
    # v2 Timer 块（精确整块移除）
    t = t.replace(_TIMER_V2, "", 1)
    # calcY
    t = t.replace(_CALCY_NEW, _CALCY_OLD)
    return t


def _apply_v3_patch(t: str) -> str:
    """打入 v3 补丁。锚点缺失返回空串。"""
    if _HIDE_MARGIN_OLD not in t:
        logger.warning("[com.high] 补丁锚点 hideMargin 未找到")
        return ""
    t = t.replace(_HIDE_MARGIN_OLD, _HIDE_MARGIN_NEW, 1)

    if _SIGNAL_ANCHOR not in t:
        logger.warning("[com.high] 补丁锚点 contentGeometryChanged 未找到")
        return ""
    t = t.replace(_SIGNAL_ANCHOR, _TIMER_BLOCK + _SIGNAL_ANCHOR, 1)

    cnt = t.count(_CALCY_OLD)
    if cnt == 0:
        logger.warning("[com.high] calcY 锚点未找到")
        return ""
    t = t.replace(_CALCY_OLD, _CALCY_NEW)
    return t


def apply_patch(target: Path | None = None) -> bool:
    """给 WidgetsContainer.qml 打补丁（幂等）。"""
    target = target or _widgets_container_path()
    if not target.exists():
        logger.warning("[com.high] 未找到 WidgetsContainer.qml: {}", target)
        return False

    t = target.read_text(encoding="utf-8")
    if SYNC_MARK in t and _TIMER_BLOCK in t:
        logger.info("[com.high] 补丁已是最新版，跳过")
        return True

    if PATCH_MARK in t:
        t = _strip_any_old_patch(t)
        logger.info("[com.high] 已移除旧版补丁，重新打入最新版")

    t = _apply_v3_patch(t)
    if not t:
        return False

    try:
        target.write_text(t, encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        logger.error("[com.high] 补丁写回失败: {}", e)
        return False

    logger.info("[com.high] 最新补丁已打入")
    return True


# ---------------------------------------------------------------------------
# 插件主体
# ---------------------------------------------------------------------------

class Plugin(CW2Plugin):
    """小组件布局调节插件（无组件界面）。"""

    configChanged = Signal()

    def __init__(self, api: PluginAPI):
        super().__init__(api)
        self._config = HighConfig()

    def on_load(self):
        super().on_load()
        try:
            self.api.config.register_plugin_model(self.pid, self._config)
            logger.info("[com.high] 配置模型注册成功: plugins.configs.{}", self.pid)
        except Exception as e:  # noqa: BLE001
            logger.warning("[com.high] 注册配置模型失败: {}", e)
        # 设置页注册到主程序设置页
        self.api.ui.register_settings_page(
            Path("qml") / "SettingsPage.qml",
            title="小组件布局",
            icon="ic_fluent_resize_20_regular",
        )
        apply_patch()
        logger.info("[com.high] 插件已加载")

    def on_unload(self):
        logger.info("[com.high] 插件已卸载")

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
            logger.warning("[com.high] 保存配置失败: {}", e)
