"""配置（.env 前缀 FISHSLANG_）。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Config(BaseModel):
    fishslang_enabled: bool = Field(default=True, description="总开关")
    fishslang_file: str = Field(default="", description="词典文件；留空 = <cwd>/data/fishslang/slang.json")
    fishslang_global_key: str = Field(default="*", description="全局黑话存在这个键下")
    fishslang_max: int = Field(default=12, description="每次注入最多几条")
    fishslang_max_chars: int = Field(default=600, description="注入段最长字符数")
    fishslang_admin_dm: bool = Field(default=True, description="是否允许私聊里改（默认允许）")
