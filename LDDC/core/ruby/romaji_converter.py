# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
"""罗马音到平假名转换器模块

此模块将包含所有与罗马音转换相关的逻辑。
"""
import re

from LDDC.common.logger import logger

# 罗马音到平假名的映射表，按长度降序排列以优先匹配长音节
ROMA_HIRA_MAP = {
    # --- 3个字母 ---
    "cha": "ちゃ", "chu": "ちゅ", "cho": "ちょ",
    "sha": "しゃ", "shu": "しゅ", "sho": "しょ",
    "hya": "ひゃ", "hyu": "ひゅ", "hyo": "ひょ",
    "kya": "きゃ", "kyu": "きゅ", "kyo": "きょ",
    "gya": "ぎゃ", "gyu": "ぎゅ", "gyo": "ぎょ",
    "nya": "にゃ", "nyu": "にゅ", "nyo": "にょ",
    "rya": "りゃ", "ryu": "りゅ", "ryo": "りょ",
    "pya": "ぴゃ", "pyu": "ぴゅ", "pyo": "ぴょ",
    "bya": "びゃ", "byu": "びゅ", "byo": "びょ",
    "mya": "みゃ", "myu": "みゅ", "myo": "みょ",
    "ja": "じゃ", "ju": "じゅ", "jo": "じょ",
    "ssu": "っす",  # 口语化缩略音
    "tsa": "つぁ", "tsi": "つぃ", "tse": "つぇ", "tso": "つぉ",
    "thi": "てぃ", "dhi": "でぃ",
    "she": "しぇ", "che": "ちぇ",
    # --- 2个字母 ---
    "fa": "ふぁ", "fi": "ふぃ", "fe": "ふぇ", "fo": "ふぉ",
    "wi": "うぃ", "we": "うぇ",
    "va": "ゔぁ", "vi": "ゔぃ", "ve": "ゔぇ", "vo": "ゔぉ",
    "je": "じぇ",
    "shi": "し", "tsu": "つ", "chi": "ち",
    "za": "ざ", "ze": "ぜ", "zo": "ぞ",
    "da": "だ", "de": "で", "do": "ど",
    "ba": "ば", "bi": "び", "bu": "ぶ", "be": "べ", "bo": "ぼ",
    "pa": "ぱ", "pi": "ぴ", "pu": "ぷ", "pe": "ぺ", "po": "ぽ",
    "ga": "が", "gi": "ぎ", "gu": "ぐ", "ge": "げ", "go": "ご",
    "ka": "か", "ki": "き", "ku": "く", "ke": "け", "ko": "こ",
    "sa": "さ", "su": "す", "se": "せ", "so": "そ",
    "ta": "た", "te": "て", "to": "と",
    "na": "な", "ni": "に", "nu": "ぬ", "ne": "ね", "no": "の",
    "ha": "は", "hi": "ひ", "fu": "ふ", "he": "へ", "ho": "ほ",
    "ma": "ま", "mi": "み", "mu": "む", "me": "め", "mo": "も",
    "ya": "や", "yu": "ゆ", "yo": "よ",
    "ra": "ら", "ri": "り", "ru": "る", "re": "れ", "ro": "ろ",
    "wa": "わ", "wo": "を",
    "ji": "じ", "zu": "ず",
    "di": "ぢ", "du": "づ",
    # --- 长音 ---
    "aa": "ああ", "ii": "いい", "uu": "うう", "ee": "ええ", "oo": "おお",
    "ou": "おう",
    # --- 非标准/兼容性 ---
    "si": "し", "ti": "ち", "tu": "つ", "hu": "ふ",
    "la": "ら", "li": "り", "lu": "る", "le": "れ", "lo": "ろ",
    "xi": "し", "qi": "ち", "cu": "つ",
    # --- 1个字母 ---
    "a": "あ", "i": "い", "u": "う", "e": "え", "o": "お",
    "n": "ん",
}

VOWELS = "aiueo"
CONSONANTS = "bcdfghjklmnpqrstvwxyz"


def _preprocess_romaji(romaji: str) -> str:
    """对输入的罗马音进行预处理，使其更规范。"""
    text = romaji.lower().strip()
    # 移除末尾的撇号
    if text.endswith("'"):
        text = text[:-1].strip()

    # 将长音符'-'转换为对应的元音
    # 例如：ko-hi- -> koohii
    # 使用正则表达式的回调函数来处理
    def replace_long_vowel(match: re.Match) -> str:
        # 获取'-'前的那个字符
        prev_char = match.group(0)[0]
        if prev_char in VOWELS:
            return prev_char * 2
        # 如果'-'前不是元音，则可能是一个错误的用法，暂时保留
        return match.group(0)

    text = re.sub(r"([a-z])-", replace_long_vowel, text)

    # 修正一些常见的错误拼写
    return re.sub(r"\buta\b", "futa", text)


def roma_to_hiragana(romaji: str) -> str:
    """将罗马音字符串转换为平假名字符串（重构版）。"""
    romaji = _preprocess_romaji(romaji)
    hiragana = []
    i = 0
    n = len(romaji)

    while i < n:
        # 0. 跳过空格
        if romaji[i].isspace():
            hiragana.append(romaji[i])
            i += 1
            continue

        # 1. 优先匹配长音节 (3, 2, 1个字母)
        matched = False
        for length in range(3, 0, -1):
            if i + length <= n:
                sub = romaji[i : i + length]
                if sub in ROMA_HIRA_MAP:
                    hiragana.append(ROMA_HIRA_MAP[sub])
                    i += length
                    matched = True
                    break
        if matched:
            continue

        # 2. 处理促音 (っ) - 由重复的辅音产生
        # 例如: 'kko', 'tta'
        if i + 1 < n and romaji[i] in CONSONANTS and romaji[i] == romaji[i + 1]:
            hiragana.append("っ")
            i += 1
            continue

        # 3. 处理 'n' 和 'm' 作为 'ん'
        # 'n' 或 'm' 后面是辅音 (b, p除外), 或在词尾
        is_n_char = romaji[i] == "n"
        is_m_char_as_n = romaji[i] == "m" and i + 1 < n and romaji[i + 1] not in VOWELS and romaji[i + 1] not in "y' "
        if is_n_char or is_m_char_as_n:
            # 检查 'n' 后面是否是元音或 'y'，如果是，则它不是 'ん'，而是下一个音节的开头
            if i + 1 < n and romaji[i + 1] in VOWELS + "y'":
                # 这是 'na', 'ni' 等情况，会在第一步的音节匹配中处理
                # 如果代码执行到这里，说明它是一个无法匹配的序列
                pass
            else:
                hiragana.append("ん")
                i += 1
                continue

        # 4. 处理撇号(')，通常用于分隔 'n' 和元音，或作为促音
        if romaji[i] == "'":
            # 如果撇号前的字符不是 'n'，则它可能表示一个促音
            if not (i > 0 and romaji[i - 1] == "n"):
                hiragana.append("っ")
            i += 1
            continue

        # 5. 如果所有规则都匹配不上，保留原字符并记录警告
        hiragana.append(romaji[i])
        logger.debug(f"在罗马音转换中保留未知字符或序列: '{romaji[i]}' at position {i} in '{romaji}'")
        i += 1

    return "".join(hiragana)
