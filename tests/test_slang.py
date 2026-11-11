"""黑话存取/合并/注入段的单元测试（纯函数）。"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nonebot_plugin_fishslang"))

import store  # noqa: E402


def _file():
    return os.path.join(tempfile.mkdtemp(), "slang.json")


def test_put_get_roundtrip():
    p = _file()
    ok, msg = store.put(p, "123", "答辩", "大便")
    assert ok and "答辩" in msg
    data = store.load(p)
    assert data["123"]["答辩"] == "大便"


def test_put_rejects_empty_and_long():
    p = _file()
    assert store.put(p, "1", "", "x")[0] is False
    assert store.put(p, "1", "词", "")[0] is False
    assert store.put(p, "1", "词" * 30, "x")[0] is False
    assert store.put(p, "1", "词", "x" * 200)[0] is False


def test_merge_global_then_group_override():
    p = _file()
    store.put(p, "*", "答辩", "大便")
    store.put(p, "*", "绷不住", "笑了")
    store.put(p, "123", "答辩", "本群说法")
    data = store.load(p)
    m = store.merged(data, "123")
    assert m["答辩"] == "本群说法"
    assert m["绷不住"] == "笑了"
    m2 = store.merged(data, "999")
    assert m2["答辩"] == "大便" and "本群说法" not in m2.values()


def test_drop_and_empty_bucket_cleanup():
    p = _file()
    store.put(p, "123", "词1", "说明")
    ok, _ = store.drop(p, "123", "词1")
    assert ok
    assert "123" not in store.load(p)
    assert store.drop(p, "123", "不存在")[0] is False


def test_mtime_cache_reloads_after_write():
    p = _file()
    cache = {"mtime": None, "data": None}
    store.load(p, cache=cache)
    store.put(p, "1", "词", "说明")
    import time
    time.sleep(0.01)
    fresh = store.load(p, cache=cache)
    assert "1" in fresh


def test_clean_filters_junk():
    p = _file()
    with open(p, "w", encoding="utf-8") as f:
        f.write('{"1": {"a": "b", "": "x", "c": ""}, "2": "not-a-dict"}')
    data = store.load(p)
    assert data == {"1": {"a": "b"}}


def test_rank_prefers_recent_then_longer():
    # 「最近聊天里出现过」按**子串**判定：所以 "绷" 也算出现过（它就在 "绷不住了" 里）
    words = {"答辩": "大便", "绷": "笑", "绷不住了": "笑死", "老六": "阴人"}
    rows = store.rank(words, recent_text="他绷不住了", limit=4)
    got = [k for k, _ in rows]
    assert got[0] == "绷不住了"                  # 同属"最近"，按词长优先
    assert got[1] == "绷"
    assert got[2:] == ["答辩", "老六"]            # 没出现的按词长


def test_block_shape_and_limits():
    words = {"词%d" % i: "说明%d" % i for i in range(40)}
    text = store.block(words, "", limit=5, max_chars=60)
    assert text.startswith("【这个群的黑话")
    assert text.count("=") <= 5
    assert store.block({}, "") == ""

