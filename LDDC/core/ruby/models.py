# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
"""数据模型定义模块"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from typing import Literal, NamedTuple

# --- 我们自己定义的内部数据结构 ---


class CharType(Enum):
    """字符类型枚举"""

    KANJI = auto()  # 日文汉字
    HIRAGANA = auto()  # 平假名
    KATAKANA = auto()  # 片假名
    SYMBOL = auto()  # 纯符号 (两边是日文)
    OTHER = auto()  # 其他 (英文, 数字, 混合符号等)


class Token(NamedTuple):
    """分词后的数据单元"""

    text: str
    char_type: CharType
    start: int  # 在原始字符串中的开始索引
    end: int  # 在原始字符串中的结束索引
    group_id: int | None = None  # 来自同一词典词的Token共享一个group_id


# --- 以下是为新匹配引擎建议添加的模型 ---


class RuleType(Enum):
    """匹配规则的类型"""

    # 简单替换规则，例如 ("づ", "ず")
    SUBSTITUTION = auto()
    # 需要调用特定函数进行处理的复杂规则，例如长音符 'ー' 的处理
    FUNCTION = auto()


@dataclass(frozen=True, slots=True)
class MatchRule:
    """定义一条匹配规则。"""

    name: str  # 规则的唯一名称，便于调试，例如 "particle_ha_wa"
    cost: int  # 应用此规则的代价，0表示等价替换
    rule_type: RuleType  # 规则类型
    content: Callable[[str, list[Token], Token], str]  | tuple[str, str]  # 规则内容。对于SUBSTITUTION，是(from, to)元组,对于FUNCTION，是可调用对象。
    # 预计算此规则可能引入的字符集合，用于快速过滤。
    # 例如，对于 ("は", "わ")，此集合为 {'わ'}。
    # 如果目标字符串中不包含 'わ'，则此规则可以被安全地跳过。
    introduced_chars: set[str]


class FuncRule(MatchRule):
    """定义一个函数匹配规则。"""

    rule_type: Literal[RuleType.FUNCTION]
    content: Callable[[str, list[Token], Token], str]


class SubstitutionRule(MatchRule):
    """定义一个替换规则。"""

    rule_type: Literal[RuleType.SUBSTITUTION]
    content: tuple[str, str]  # (from, to) 元组
