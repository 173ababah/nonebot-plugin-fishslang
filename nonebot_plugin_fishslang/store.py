"""黑话词典的存取与合并（纯函数为主，可直接单测）。

文件结构：`{"<群号>": {"词": "说明"}, "*": {"词": "说明"}}`

为什么用 `*` 存全局：用户要的是「全局一份 + 每个群自己一份」，
全局那份所有群都认，群自己那份用来**覆盖/补充**（同名词以本群为准）。
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Tuple

GLOBAL_KEY = "*"
_lock = threading.Lock()


def _clean(raw: Any) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    if not isinstance(raw, dict):
        return out
    for gid, words in raw.items():
        if not isinstance(words, dict):
            continue
        bucket = {}
        for k, v in words.items():
            k, v = str(k).strip(), str(v).strip()
            if k and v:
                bucket[k] = v
        if bucket:
            out[str(gid)] = bucket
    return out


def load(path: str, *, cache: dict | None = None) -> Dict[str, Dict[str, str]]:
    """按 mtime 热读（控制台/别的进程改完立刻生效）。`cache` 传一个 dict 复用就能省 IO。"""
    try:
        mt = os.stat(path).st_mtime
    except OSError:
        return {}
    if cache is not None and cache.get("mtime") == mt and cache.get("data") is not None:
        return cache["data"]
    data: Dict[str, Dict[str, str]] = {}
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = _clean(json.load(f))
    except (OSError, ValueError):
        data = {}
    if cache is not None:
        cache["mtime"], cache["data"] = mt, data
    return data


def save(path: str, data: Dict[str, Dict[str, str]]) -> bool:
    try:
        d = os.path.dirname(os.path.abspath(path))
        os.makedirs(d, exist_ok=True)
        tmp = path + ".tmp"
        with _lock:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(_clean(data), f, ensure_ascii=False, indent=1)
            os.replace(tmp, path)
        return True
    except OSError:
        return False


def merged(all_data: Dict[str, Dict[str, str]], gid: str,
           *, global_key: str = GLOBAL_KEY) -> Dict[str, str]:
    """这个群实际生效的黑话 = 全局 ∪ 本群（同名词以本群为准）。"""
    m: Dict[str, str] = {}
    m.update(all_data.get(str(global_key)) or {})
    m.update(all_data.get(str(gid)) or {})
    return m


def put(path: str, gid: str, word: str, desc: str, *, global_key: str = GLOBAL_KEY) -> Tuple[bool, str]:
    """加/改一条。`gid` 传 `*`（或 global_key）= 全局。"""
    word, desc = str(word or "").strip(), str(desc or "").strip()
    if not word or not desc:
        return False, "词和说明都要有"
    if len(word) > 24:
        return False, "词太长了（24 字以内）"
    if len(desc) > 120:
        return False, "说明太长了（120 字以内）"
    data = load(path)
    key = str(gid or global_key)
    data.setdefault(key, {})[word] = desc
    return (True, "记下了：%s=%s" % (word, desc)) if save(path, data) else (False, "写文件失败")


def drop(path: str, gid: str, word: str) -> Tuple[bool, str]:
    data = load(path)
    key = str(gid or "")
    bucket = data.get(key) or {}
    if str(word) not in bucket:
        return False, "这个词不在「%s」里" % (key or "本群")
    bucket.pop(str(word), None)
    if not bucket:
        data.pop(key, None)
    return (True, "删掉了「%s」" % word) if save(path, data) else (False, "写文件失败")


def rank(words: Dict[str, str], recent_text: str, *, limit: int = 12) -> List[Tuple[str, str]]:
    """按「最近聊天里出现过」优先排序，再按词长（长的更具体）。

    这样注入的是**这个群此刻用得上的**黑话，而不是一整本词典。
    """
    recent = str(recent_text or "")
    rows = sorted(words.items(),
                  key=lambda kv: (0 if kv[0] in recent else 1, -len(kv[0]), kv[0]))
    return rows[:max(1, int(limit))]


def block(words: Dict[str, str], recent_text: str, *,
          limit: int = 12, max_chars: int = 600) -> str:
    """生成要注入提示词的那段。没有词就返回空串（调用方据此跳过拼装）。"""
    rows = rank(words, recent_text, limit=limit)
    if not rows:
        return ""
    parts: List[str] = []
    used = 0
    for k, v in rows:
        piece = "%s=%s" % (k, v)
        if used + len(piece) + 1 > max_chars:
            break
        parts.append(piece)
        used += len(piece) + 1
    if not parts:
        return ""
    return ("【这个群的黑话（群里懂、外面不懂；你自己知道意思就行，别解释、别问）】"
            + "；".join(parts))
