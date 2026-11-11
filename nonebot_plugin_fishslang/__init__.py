"""nonebot-plugin-fishslang —— 群聊黑话词典。

命令（默认超管可用，`FISHSLANG_ADMIN_DM` 控制私聊）：

| 命令 | 说明 |
|------|------|
| `/黑话` | 看本群生效的黑话（全局 ∪ 本群） |
| `/黑话 加 词 说明` | 加到本群 |
| `/黑话 删 词` | 从本群删 |
| `/黑话 全局 加 词 说明` | 加到全局（所有群都认） |

给别的插件用：

```python
from nonebot_plugin_fishslang import slang_block
block = slang_block(chat_key, recent_text)   # 直接拼进 system prompt
```
"""

from __future__ import annotations

import os

from nonebot import get_plugin_config, on_command
from nonebot.adapters import Event, Message
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata

from . import store
from .config import Config

__plugin_meta__ = PluginMetadata(
    name="nonebot-plugin-fishslang",
    description="群聊黑话词典：全局+本群两级合并，按最近聊天加权注入提示词",
    usage="/黑话 | /黑话 加 词 说明 | /黑话 删 词 | /黑话 全局 加 词 说明",
    type="application",
    config=Config,
    homepage="https://github.com/173ababah/nonebot-plugin-fishslang",
    supported_adapters={"~onebot.v11"},
)

cfg = get_plugin_config(Config)
FILE = cfg.fishslang_file or os.path.join(os.getcwd(), "data", "fishslang", "slang.json")
_cache: dict = {"mtime": None, "data": None}

slang_cmd = on_command("黑话", aliases={"slang"}, priority=18, block=True, permission=SUPERUSER)


def _gid(event: Event) -> str:
    """群号；私聊返回空串（私聊只允许改全局）。"""
    text = ""
    for name in ("get_session_id",):
        fn = getattr(event, name, None)
        if callable(fn):
            try:
                text = str(fn())
            except Exception:
                text = ""
    if text.startswith("group_"):
        return text.split("_", 1)[1]
    return ""


def slang_block(chat_key: str, recent_text: str = "") -> str:
    """给别的插件调用：拿这个会话该注入的黑话段（没词返回空串）。"""
    if not cfg.fishslang_enabled:
        return ""
    gid = chat_key.split("_", 1)[1] if str(chat_key).startswith("group_") else ""
    words = store.merged(store.load(FILE, cache=_cache), gid,
                         global_key=cfg.fishslang_global_key)
    return store.block(words, recent_text, limit=cfg.fishslang_max,
                       max_chars=cfg.fishslang_max_chars)


@slang_cmd.handle()
async def _(event: Event, arg: Message = CommandArg()):
    if not cfg.fishslang_enabled:
        await slang_cmd.finish("黑话功能关着呢（FISHSLANG_ENABLED=false）")
    gid = _gid(event)
    text = arg.extract_plain_text().strip()
    data = store.load(FILE, cache=_cache)

    if not text:
        words = store.merged(data, gid, global_key=cfg.fishslang_global_key)
        if not words:
            await slang_cmd.finish("这个群还没有黑话。加一条：/黑话 加 答辩 大便")
        gl = data.get(cfg.fishslang_global_key) or {}
        own = data.get(gid) or {}
        lines = ["这个群生效 %d 条（全局 %d + 本群 %d）：" % (len(words), len(gl), len(own))]
        for k, v in store.rank(words, "", limit=40):
            src = "本群" if k in own else "全局"
            lines.append("· %s=%s（%s）" % (k, v, src))
        await slang_cmd.finish("\n".join(lines))

    parts = text.split()
    scope = gid
    if parts and parts[0] in ("全局", "global", "所有群"):
        scope = cfg.fishslang_global_key
        parts = parts[1:]
    if not scope:
        await slang_cmd.finish("私聊里只能改全局：/黑话 全局 加 词 说明")
    if len(parts) >= 1 and parts[0] in ("加", "add", "新增"):
        if len(parts) < 3:
            await slang_cmd.finish("用法：/黑话 加 <词> <说明>")
        ok, msg = store.put(FILE, scope, parts[1], " ".join(parts[2:]))
        _cache["mtime"] = None
        await slang_cmd.finish(msg)
    if len(parts) >= 2 and parts[0] in ("删", "del", "删除"):
        ok, msg = store.drop(FILE, scope, parts[1])
        _cache["mtime"] = None
        await slang_cmd.finish(msg)
    await slang_cmd.finish("用法：/黑话 | /黑话 加 词 说明 | /黑话 删 词 | /黑话 全局 加 词 说明")
