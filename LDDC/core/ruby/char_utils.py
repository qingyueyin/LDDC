# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
"""字符处理工具函数模块"""

from .models import CharType


def get_char_type(char: str) -> CharType:
    """判断单个字符的类型

    Args:
        char (str): 单个字符

    Returns:
        CharType: 字符类型

    """
    # 日文汉字 (Kanji)
    if "\u4e00" <= char <= "\u9fff":
        return CharType.KANJI
    # 々 (iteration mark) 经常像汉字一样使用
    if char == "々":
        return CharType.KANJI
    # 纯符号列表，包含常见的日文、中文和英文标点
    # 这些符号通常在罗马音中没有对应发音
    if char in "「」『』【】、。，．・〜？！（）(),.?!'\"：:":
        return CharType.SYMBOL
    # 平假名 (Hiragana)
    if "\u3040" <= char <= "\u309f":
        return CharType.HIRAGANA
    # 片假名 (Katakana)
    if "\u30a0" <= char <= "\u30ff":
        return CharType.KATAKANA
    # 其他所有字符，包括拉丁字母、数字、其他标点符号
    return CharType.OTHER


def katakana_to_hiragana(text: str) -> str:
    """将字符串中的所有片假名转换为平假名

    Args:
        text (str): 输入字符串

    Returns:
        str: 转换后的字符串

    """
    return "".join(chr(ord(char) - 96) if "ァ" <= char <= "ヶ" else char for char in text)


def is_latin(text: str) -> bool:
    """检查字符串是否主要由拉丁字母组成，以判断其是否可能为英文。"""
    # 只计算非空白字符
    stripped_text = "".join(text.split())
    if not stripped_text:
        return False

    latin_chars = 0
    for char in stripped_text:
        if "a" <= char.lower() <= "z":
            latin_chars += 1
    total_chars = len(stripped_text)

    # 如果拉丁字母占一半以上，则认为是英文
    return (latin_chars / total_chars) > 0.5
