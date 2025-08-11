# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
"""日语歌词平假名注音生成器主模块"""

import re
import unicodedata

from LDDC.common.logger import logger
from LDDC.common.models import FSLyricsLine

from ._logic import process_line
from .char_utils import get_char_type
from .dictionary import JP_VOCAB_TRIE, find_all_prefix_matches
from .mapper import IndexMapper
from .models import CharType, Token
from .romaji_converter import roma_to_hiragana

__all__ = ["generate_ruby", "roma_to_hiragana"]

PLACEHOLDER = "█"


def contains_kana(text: str) -> bool:
    """判断文本中是否包含假名"""
    return any("\u3040" <= char <= "\u309f" or "\u30a0" <= char <= "\u30ff" for char in text)


def contains_Kanji(text: str) -> bool:
    """判断文本中是否包含汉字"""
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _tokenize_orig_line(text: str) -> list[Token]:
    """将原始歌词文本分词为Token列表，并在分词阶段处理送假名。"""
    if not text:
        return []

    tokens: list[Token] = []
    i = 0
    n = len(text)
    group_id_counter = 0

    while i < n:
        # 1. 优先使用Trie树进行最大前向匹配
        matches = find_all_prefix_matches(JP_VOCAB_TRIE, text[i:])

        if matches:
            longest_match, _ = matches[0]
            match_len = len(longest_match)

            # 统一使用按字符类型分解的模式
            group_id_counter += 1
            decomposed_start = i
            sub_i = 0
            while sub_i < match_len:
                # 确定当前字符类型
                current_char_type = get_char_type(longest_match[sub_i])

                # 寻找同类型字符的连续片段
                sub_j = sub_i + 1
                while sub_j < match_len and get_char_type(longest_match[sub_j]) == current_char_type:
                    sub_j += 1

                # 创建这个同类型片段的Token
                segment = longest_match[sub_i:sub_j]
                tokens.append(
                    Token(
                        text=segment,
                        char_type=current_char_type,
                        start=decomposed_start + sub_i,
                        end=decomposed_start + sub_j,
                        group_id=group_id_counter,
                    ),
                )

                # 移动到下一个片段
                sub_i = sub_j

            i += match_len
        else:
            # 按字符类型分词 (无 group_id)
            char = text[i]
            char_type = get_char_type(char)
            j = i + 1
            while j < n and get_char_type(text[j]) == char_type:
                j += 1
            segment = text[i:j]
            tokens.append(Token(segment, char_type, i, j, group_id=None))
            i = j

    # 合并连续的 OTHER token
    if not tokens:
        return []

    merged_tokens: list[Token] = [tokens[0]]
    for i in range(1, len(tokens)):
        prev_token = merged_tokens[-1]
        curr_token = tokens[i]

        if prev_token.char_type == CharType.OTHER and curr_token.char_type == CharType.OTHER and prev_token.group_id is None and curr_token.group_id is None:
            merged_text = prev_token.text + curr_token.text
            merged_tokens[-1] = Token(merged_text, CharType.OTHER, prev_token.start, curr_token.end, group_id=None)
        else:
            merged_tokens.append(curr_token)

    return merged_tokens


def generate_ruby(orig_line: FSLyricsLine, roma_line: FSLyricsLine) -> list[tuple[int, int, str]]:
    """生成日语歌词的平假名注音"""
    orig_text_raw = "".join(word.text for word in orig_line.words)
    roma_text_raw = "".join(word.text for word in roma_line.words)

    # 1. 初始化索引映射器，并获取归一化后的文本
    mapper = IndexMapper(orig_text_raw)
    orig_text = mapper.normalized_text  # 使用归一化后的文本进行处理
    roma_text = unicodedata.normalize("NFKC", roma_text_raw)

    if not contains_Kanji(orig_text):
        logger.debug("原文中不包含汉字，无需生成平假名注音")
        return []
    if not roma_text.strip():
        logger.debug("罗马音为空，无法生成平假名注音")
        return []

    logger.debug(f"开始处理原文 (归一化后): '{orig_text}'")
    logger.debug(f"对应罗马音 (归一化后): '{roma_text}'")

    # --- 分句处理逻辑 ---
    # 仅当原文和罗马音中都存在明确的分隔符时，才尝试分句
    # 原文分隔符: ' ' (一个或多个空格)
    # 罗马音分隔符: '  ' (两个或更多空格)
    orig_segments = re.split(r" +", orig_text)
    roma_segments = re.split(r" {2,}", roma_text)

    if len(orig_segments) > 1 and len(orig_segments) == len(roma_segments):
        logger.debug(f"检测到分句标识，成功分割为 {len(orig_segments)} 个分句。")
        all_results: list[tuple[int, int, str]] = []
        norm_offset = 0
        # 使用 finditer 来定位分隔符，以便正确计算偏移量
        orig_seps = [m.group(0) for m in re.finditer(r" +", orig_text)]

        for i in range(len(orig_segments)):
            orig_seg = orig_segments[i]
            roma_seg = roma_segments[i]

            logger.debug(f"--- 处理分句 {i + 1}/{len(orig_segments)} ---")
            logger.debug(f"原文分句: '{orig_seg}'")
            logger.debug(f"罗马音分句: '{roma_seg}'")

            tokens = _tokenize_orig_line(orig_seg)
            # process_line 返回的是基于分句的、归一化的坐标
            segment_results = process_line(roma_seg, tokens)

            # 将分句坐标转换为整行归一化坐标，然后再转换为原始坐标
            for start, end, ruby in segment_results:
                norm_start = start + norm_offset
                norm_end = end + norm_offset
                orig_start, orig_end = mapper.to_original_indices(norm_start, norm_end)
                all_results.append((orig_start, orig_end, ruby))

            # 加上当前分句的长度和分隔符的长度
            norm_offset += len(orig_seg)
            if i < len(orig_seps):
                norm_offset += len(orig_seps[i])

        return all_results

    if len(orig_segments) > 1 and len(orig_segments) != len(roma_segments):
        logger.warning(
            f"原文分句 ({len(orig_segments)}) 与罗马音分句 ({len(roma_segments)}) 数量不匹配。将回退到整行处理模式。",
        )

    logger.debug("未检测到有效分句，或分句失败，将整行处理。")
    tokens = _tokenize_orig_line(orig_text)
    # process_line 返回的是基于整行归一化文本的坐标
    results_in_norm_space = process_line(roma_text, tokens)

    # 将归一化坐标转换为原始坐标
    return [(*mapper.to_original_indices(start, end), ruby) for start, end, ruby in results_in_norm_space]
