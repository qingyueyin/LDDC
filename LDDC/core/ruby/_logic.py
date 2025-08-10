# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
"""日语歌词平假名注音生成器的核心逻辑实现模块"""

import re

from LDDC.common.logger import logger

from .char_utils import is_latin, katakana_to_hiragana
from .dictionary import JP_VOCAB_TRIE, find_word
from .models import CharType, RuleType, Token
from .romaji_converter import roma_to_hiragana
from .rules import ALL_RULES

PLACEHOLDER = "█"


def _generate_variants(
    base_anchor: str,
    tokens: list[Token],
    current_token: Token,
    hira_for_match: str,
) -> list[tuple[str, int, list[str]]]:
    """新的统一变体生成引擎。

    Args:
        base_anchor (str): 要为其生成变体的基础字符串。
        tokens (list[Token]): 完整的Token列表，用于函数规则的上下文。
        current_token (Token): 当前正在处理的Token。
        hira_for_match (str): 用于匹配的目标平假名字符串，用于预过滤规则。

    Returns:
        list[tuple[str, int, list[str]]]: 一个元组列表，每个元组包含
                                           (变体字符串, 总代价, [应用的规则名称])。
                                           列表按代价升序排列。

    """
    # 1. 规则预过滤 (性能优化)
    target_chars = set(hira_for_match)
    applicable_rules = [rule for rule in ALL_RULES if not rule.introduced_chars or rule.introduced_chars.intersection(target_chars)]

    # 2. 生成变体
    # 使用字典来存储变体，以避免重复，键为变体文本，值为 (代价, [规则])
    variants: dict[str, tuple[int, list[str]]] = {base_anchor: (0, ["base"])}

    # 为了控制复杂度，我们只对基础锚点应用单层规则
    # 更复杂的引擎可以设计为递归或多层应用
    for rule in applicable_rules:
        new_variants = {}
        for text, (cost, reasons) in variants.items():
            if rule.rule_type == RuleType.SUBSTITUTION:
                frm, to = rule.content
                if frm in text:
                    new_text = text.replace(frm, to)
                    if new_text not in variants and new_text not in new_variants:
                        new_variants[new_text] = (cost + rule.cost, [*reasons, rule.name])

            elif rule.rule_type == RuleType.FUNCTION:
                # 函数规则需要更复杂的处理，因为它可能依赖于上下文
                new_text = rule.content(text, tokens, current_token)
                if new_text != text and new_text not in variants and new_text not in new_variants:
                    new_variants[new_text] = (cost + rule.cost, [*reasons, rule.name])

        variants.update(new_variants)

    # 3. 格式化并排序输出
    result = [(text, cost, reasons[1:]) for text, (cost, reasons) in variants.items()]

    return sorted(result, key=lambda x: x[1])


def _handle_kana_token(
    token: Token,
    hira_for_match: str,
    hira_match_idx: int,
    tokens: list[Token],
) -> int:
    """处理单个假名Token，同步其在平假名字符串中的位置。"""
    anchor_hira = "".join(katakana_to_hiragana(token.text).split())

    # 使用新引擎生成所有变体
    variants = _generate_variants(anchor_hira, tokens, token, hira_for_match[hira_match_idx:])

    for fuzzy_text, cost, reasons in variants:
        if hira_for_match.startswith(fuzzy_text, hira_match_idx):
            if cost == 0:
                logger.debug(f"同步假名锚点 '{token.text}' -> 精确匹配到 '{fuzzy_text}'")
            else:
                log_msg = f"({'+'.join(reasons)}) '{fuzzy_text}' (代价: {cost})"
                logger.warning(f"假名锚点 '{token.text}' 通过模糊匹配{log_msg} 成功。")
            return hira_match_idx + len(fuzzy_text)

    logger.warning(f"假名锚点失配: 原文 '{token.text}', 期望在 '{hira_for_match}' 的 {hira_match_idx} 处找到。")
    return hira_match_idx


def _find_next_anchor(start_idx: int, token_stream: list[Token]) -> Token | None:
    """从指定索引开始，寻找下一个有效的假名锚点。"""
    for i in range(start_idx, len(token_stream)):
        t = token_stream[i]
        if t.char_type in (CharType.HIRAGANA, CharType.KATAKANA):
            # 检查是否是 `汉字(注音)` 格式中的假名，如果是则跳过
            is_in_parens = (
                i > 1
                and token_stream[i - 2].char_type == CharType.KANJI
                and token_stream[i - 1].text == "("
                and i + 1 < len(token_stream)
                and token_stream[i + 1].text == ")"
            )
            if not is_in_parens:
                return t
    return None


def _select_best_reading(
    readings: tuple[str, ...],
    hira_for_match: str,
    next_anchor: Token | None,
) -> tuple[str, int] | None:
    """从多个读音中选择最优的一个，优先选择最长的匹配。"""
    possible_matches = [reading for reading in readings if hira_for_match.startswith(reading)]

    if not possible_matches:
        return None

    # 优先选择最长的匹配项，因为这通常意味着更精确的匹配
    possible_matches.sort(key=len, reverse=True)

    for reading in possible_matches:
        # 检查送假名。如果一个读音包含了下一个锚点的读音，
        # 那么我们就从这个读音中把它剥离。
        # 例如，词典词是 "歌う", 读音是 "うたう", 下一个锚点是 "う"。
        # 那么 "歌" 的注音就是 "うた"。
        final_reading = reading
        hira_consumed = len(reading)

        if next_anchor:
            anchor_hira = katakana_to_hiragana(next_anchor.text)
            # 确保 reading 确实以 anchor_hira 结尾，并且 reading 本身不完全等于 anchor_hira
            if reading.endswith(anchor_hira) and reading != anchor_hira:
                # 这个选择是合理的，我们认为送假名匹配成功
                final_reading = reading[: -len(anchor_hira)]
                # 消耗的平假名仍然是整个词的读音
                hira_consumed = len(reading)
                logger.debug(f"读音 '{reading}' 包含送假名 '{anchor_hira}'，修正为 '{final_reading}'。")
                return final_reading, hira_consumed

        # 如果没有送假名，或者送假名不匹配，直接返回当前最长的读音
        return final_reading, hira_consumed

    return None


def _handle_kanji_block(
    block: list[Token],
    hira_for_match: str,
    full_token_stream: list[Token],
) -> list[tuple[int, int, str]]:
    """处理一个连续的汉字/OTHER Token块，为其生成注音。"""
    # --- 豁免检查 (Exemption Check) ---
    is_latin_block = all(t.char_type == CharType.OTHER and all(is_latin(c) or c.isspace() for c in t.text) for t in block)
    if is_latin_block:
        logger.debug(f"检测到纯拉丁/数字块 '{''.join(t.text for t in block)}'，跳过注音。")
        return []

    # 1. 寻找并评估所有后续的潜在锚点 (假名或词典词)
    last_token_in_block = block[-1]
    start_search_idx = full_token_stream.index(last_token_in_block) + 1 if last_token_in_block in full_token_stream else len(full_token_stream)

    overall_best_match = None
    # 更精确地计算块内需要注音的字符数
    punctuated_len = sum(len(t.text) for t in block if t.char_type == CharType.KANJI or (t.char_type == CharType.OTHER and t.text.strip()))
    search_window = punctuated_len * 5 + 10

    cursor = start_search_idx
    while cursor < len(full_token_stream):
        potential_anchor_token = full_token_stream[cursor]
        variants_with_cost = []
        original_anchor_text = ""

        # --- 收集当前锚点的变体 ---
        if potential_anchor_token.char_type in (CharType.HIRAGANA, CharType.KATAKANA):
            original_anchor_text = katakana_to_hiragana(potential_anchor_token.text)
            variants_with_cost = _generate_variants(original_anchor_text, full_token_stream, potential_anchor_token, hira_for_match)
            cursor += 1
        elif potential_anchor_token.group_id is not None:
            group_id = potential_anchor_token.group_id
            grouped_tokens = [potential_anchor_token]
            end_of_group_idx = cursor + 1
            while end_of_group_idx < len(full_token_stream) and full_token_stream[end_of_group_idx].group_id == group_id:
                grouped_tokens.append(full_token_stream[end_of_group_idx])
                end_of_group_idx += 1

            grouped_text = "".join(t.text for t in grouped_tokens)
            readings = find_word(JP_VOCAB_TRIE, grouped_text)
            if readings:
                original_anchor_text = grouped_text
                # 词典匹配是最高优先级的，代价为0
                variants_with_cost = [(reading, 0, ["dict_match"]) for reading in readings]
            cursor = end_of_group_idx
        else:
            cursor += 1
            continue

        # --- 对当前锚点的所有变体进行评分 ---
        if not variants_with_cost:
            continue

        anchor_best_match = None
        for fuzzy_text, cost, _reasons in variants_with_cost:
            search_pos = 0
            while True:
                pos = hira_for_match.find(fuzzy_text, search_pos, search_pos + search_window)
                if pos == -1:
                    break

                ruby_len = pos
                # --- 评分逻辑 ---
                # 分数越低越好。主要惩罚项是跳过的原文Token数量。
                skipped_tokens = cursor - start_search_idx
                score = float(skipped_tokens * 100)

                # 加上模糊匹配规则本身的代价
                score += float(cost)

                # 惩罚不合理的注音/汉字长度比
                if punctuated_len > 0 and ruby_len > 0:
                    ratio = ruby_len / punctuated_len
                    if ratio > 5.0 or ratio < 0.25:
                        score += 50  # 较大惩罚
                    else:
                        # 对偏离理想值(约2.0)的情况进行惩罚
                        score += abs(ratio - 2.0) * 5
                elif ruby_len == 0 and punctuated_len > 0:
                    # 为没有注音的方案增加一个固定的、较小的惩罚
                    # 以鼓励算法在可能的情况下寻找注音
                    score += 10

                # 使用注音在平假名流中的位置作为微小的、打破僵局的惩罚项
                score += pos * 0.01

                current_match_info = (pos, cost, fuzzy_text, score, original_anchor_text)
                if anchor_best_match is None or score < anchor_best_match[3]:
                    anchor_best_match = current_match_info

                search_pos = pos + 1

        # --- 更新全局最佳匹配 ---
        if anchor_best_match and (overall_best_match is None or anchor_best_match[3] < overall_best_match[3]):
            overall_best_match = anchor_best_match

    # 2. 如果找到了最佳的分割点
    if overall_best_match:
        found_pos, _, _, _, original_anchor_text = overall_best_match
        # --- 促音窃取修正 ---
        if found_pos > 0 and hira_for_match[found_pos - 1] == "っ" and not overall_best_match[2].startswith("っ") and original_anchor_text.startswith("っ"):
            logger.debug(f"检测到促音窃取：将 '{hira_for_match[:found_pos]}' 的末尾 'っ' 修正。")
            found_pos -= 1

        ruby = hira_for_match[:found_pos]
        block_text = "".join(t.text for t in block)
        if ruby:
            # --- 合理性检查 ---
            if punctuated_len > 0 and (len(ruby) / punctuated_len > 5.0):
                logger.warning(
                    f"锚点匹配逻辑检测到严重不匹配。汉字块 '{block_text}' ({punctuated_len}字) 与注音 '{ruby}' ({len(ruby)}字) 长度比例失衡，放弃注音。",
                )
                return []  # 放弃这个离谱的注音

            logger.debug(f"锚点匹配: 汉字块 '{block_text}' -> '{ruby}'")
            last_meaningful_token = next((t for t in reversed(block) if t.text.strip()), None)
            if last_meaningful_token:
                return [(block[0].start, last_meaningful_token.end, ruby)]
    else:
        # 3. 如果完全没有找到任何锚点(增强版回退逻辑)
        block_text = "".join(t.text for t in block).strip()
        if not block_text:
            return []

        # 尝试将整个块作为一个词在词典中查找
        readings = find_word(JP_VOCAB_TRIE, block_text)
        if readings:
            # 在剩余的平假名中寻找最长的、可能的读音
            possible_readings = [r for r in readings if r in hira_for_match]
            if possible_readings:
                best_reading = max(possible_readings, key=len)
                logger.debug(f"行末回退: 词典匹配成功。汉字块 '{block_text}' -> '{best_reading}'")
                last_meaningful_token = next((t for t in reversed(block) if t.text.strip()), None)
                if last_meaningful_token:
                    return [(block[0].start, last_meaningful_token.end, best_reading)]

        # 如果词典查找失败，则此块获得剩余所有注音 (旧逻辑，但带有合理性检查)
        ruby = hira_for_match
        if ruby and block_text.strip():
            # --- 合理性检查 ---
            # 检查注音与汉字的长度比例，防止在严重不匹配时产生荒谬的结果
            last_meaningful_token = next((t for t in reversed(block) if t.text.strip()), None)
            if last_meaningful_token:
                # 使用上面更精确的 punctuated_len
                if punctuated_len > 0 and (len(ruby) / punctuated_len > 5.0):
                    logger.warning(
                        f"行末回退逻辑检测到严重不匹配。汉字块 '{block_text}' ({punctuated_len}字) 与注音 '{ruby}' ({len(ruby)}字) 长度比例失衡，放弃注音。",
                    )
                    return []

                logger.debug(f"找到行末汉字块 '{block_text}' 的注音: '{ruby}'")
                return [(block[0].start, last_meaningful_token.end, ruby)]

    return []


def _align_and_generate_ruby_for_word(
    grouped_tokens: list[Token],
    reading: str,
) -> list[tuple[int, int, str]]:
    """将一个词的完整读音，精确地分配给这个词中的各个汉字部分。"""
    results: list[tuple[int, int, str]] = []

    # 如果整个词组只有一个Token，且是汉字，则直接返回整个读音
    if len(grouped_tokens) == 1 and grouped_tokens[0].char_type in (CharType.KANJI, CharType.OTHER):
        token = grouped_tokens[0]
        if reading:
            return [(token.start, token.end, reading)]
        return []

    # 如果读音和词的原文（转为平假名后）完全一样，说明没有需要注音的汉字
    word_text_hira = katakana_to_hiragana("".join(t.text for t in grouped_tokens))
    if word_text_hira == reading:
        return []

    reading_cursor = 0
    current_kanji_block: list[Token] = []

    token_idx = 0
    while token_idx < len(grouped_tokens):
        token = grouped_tokens[token_idx]

        if token.char_type in (CharType.KANJI, CharType.OTHER):
            current_kanji_block.append(token)
        elif token.char_type in (CharType.HIRAGANA, CharType.KATAKANA):
            # 遇到假名，说明之前的汉字块（如果有）结束了
            hira_anchor = katakana_to_hiragana(token.text)

            # 1. 处理前面的汉字块
            if current_kanji_block:
                anchor_pos_in_reading = reading.find(hira_anchor, reading_cursor)

                if anchor_pos_in_reading != -1:
                    ruby_text = reading[reading_cursor:anchor_pos_in_reading]
                    if ruby_text:
                        start_pos = current_kanji_block[0].start
                        end_pos = current_kanji_block[-1].end
                        results.append((start_pos, end_pos, ruby_text))
                    reading_cursor = anchor_pos_in_reading
                else:
                    # 读音中不包含预期的假名，这是一个错误情况
                    logger.warning(f"词典对齐失败：读音 '{reading}' 中找不到锚点 '{hira_anchor}'。将剩余读音分配给剩余汉字。")
                    remaining_kanji_tokens = [t for t in grouped_tokens[token_idx:] if t.char_type in (CharType.KANJI, CharType.OTHER)]
                    if remaining_kanji_tokens:
                        ruby_text = reading[reading_cursor:]
                        if ruby_text:
                            start_pos = remaining_kanji_tokens[0].start
                            end_pos = remaining_kanji_tokens[-1].end
                            results.append((start_pos, end_pos, ruby_text))
                    return results  # 中止处理

            # 2. 在读音中跳过这个假名锚点
            if reading.startswith(hira_anchor, reading_cursor):
                reading_cursor += len(hira_anchor)
            else:
                logger.warning(f"词典对齐警告：读音 '{reading}' 在位置 {reading_cursor} 处与锚点 '{hira_anchor}' 不匹配。")

            current_kanji_block = []

        token_idx += 1

    # 处理末尾的汉字块（如果存在）
    if current_kanji_block:
        ruby_text = reading[reading_cursor:]
        if ruby_text:
            start_pos = current_kanji_block[0].start
            end_pos = current_kanji_block[-1].end
            results.append((start_pos, end_pos, ruby_text))

    return results


def generate_ruby_for_chunk(tokens: list[Token], hira_for_match: str) -> list[tuple[int, int, str]]:
    """对一个纯净的Token列表和其对应的平假名字符串生成注音。"""
    results: list[tuple[int, int, str]] = []
    token_stream = list(tokens)
    hira_idx = 0

    cursor = 0
    while cursor < len(token_stream):
        current_token = token_stream[cursor]

        # --- 1. 处理 `汉字(注音)` 模式 (支持送假名) ---
        is_annotated_kanji = (
            current_token.char_type == CharType.KANJI
            and cursor + 3 < len(token_stream)
            and token_stream[cursor + 1].text == "("
            and token_stream[cursor + 2].char_type in (CharType.HIRAGANA, CharType.KATAKANA)
            and token_stream[cursor + 3].text == ")"
        )
        if is_annotated_kanji:
            kanji_token = current_token
            hint_token = token_stream[cursor + 2]
            hint_hira = katakana_to_hiragana(hint_token.text)

            # 检查是否存在送假名
            okurigana_token = None
            okurigana_hira = ""
            if cursor + 4 < len(token_stream) and token_stream[cursor + 4].char_type in (CharType.HIRAGANA, CharType.KATAKANA):
                okurigana_token = token_stream[cursor + 4]
                okurigana_hira = katakana_to_hiragana(okurigana_token.text)

            # 尝试将 '注音' 和 '送假名' 作为一个整体来匹配
            if okurigana_token and hira_for_match.startswith(hint_hira, hira_idx):
                temp_hira_idx = hira_idx + len(hint_hira)
                if hira_for_match.startswith(okurigana_hira, temp_hira_idx):
                    final_ruby = hira_for_match[hira_idx : temp_hira_idx + len(okurigana_hira)]
                    logger.debug(f"匹配到预标注及送假名 '{kanji_token.text}{okurigana_token.text}' -> '{final_ruby}'")
                    results.append((kanji_token.start, kanji_token.end, final_ruby))
                    hira_idx += len(final_ruby)
                    cursor += 5
                    continue

            # 如果带送假名的匹配失败，或根本没有送假名，再尝试只匹配括号内的注音
            if hira_for_match.startswith(hint_hira, hira_idx):
                logger.debug(f"匹配到预标注汉字 '{kanji_token.text}({hint_token.text})' -> '{hint_hira}'")
                results.append((kanji_token.start, kanji_token.end, hint_hira))
                hira_idx += len(hint_hira)
                cursor += 4
                continue

            logger.warning(f"预标注汉字 '{kanji_token.text}({hint_token.text})' 与平假名流不匹配，将作为普通汉字处理。")

        # --- 2. 处理常规假名和符号 ---
        if current_token.char_type in (CharType.HIRAGANA, CharType.KATAKANA):
            hira_idx = _handle_kana_token(current_token, hira_for_match, hira_idx, token_stream)
            cursor += 1
            continue
        if current_token.char_type == CharType.SYMBOL or not current_token.text.strip():
            cursor += 1
            continue

        # --- 3. 策略A: 词典优先 ---
        # 检查当前token是否属于一个词典词组
        if current_token.group_id is not None:
            group_id = current_token.group_id
            # 收集所有属于同一组的连续token
            grouped_tokens = [current_token]
            next_idx = cursor + 1
            while next_idx < len(token_stream) and token_stream[next_idx].group_id == group_id:
                grouped_tokens.append(token_stream[next_idx])
                next_idx += 1

            grouped_text = "".join(t.text for t in grouped_tokens)
            readings = find_word(JP_VOCAB_TRIE, grouped_text)

            if readings:
                next_anchor = _find_next_anchor(next_idx, token_stream)
                best_match = _select_best_reading(readings, hira_for_match[hira_idx:], next_anchor)

                if best_match:
                    reading, hira_consumed = best_match
                    logger.debug(f"词典匹配成功 (策略A): '{grouped_text}' -> '{reading}'")

                    # 对混合词进行对齐，只为汉字部分生成注音
                    aligned_results = _align_and_generate_ruby_for_word(grouped_tokens, reading)
                    results.extend(aligned_results)

                    hira_idx += hira_consumed
                    cursor = next_idx  # 跳过整个词组
                    continue

        # --- 4. 策略B: 锚点匹配 (回退) ---
        # 只有当策略A不适用或失败时，才会执行到这里
        # 识别连续的 KANJI/OTHER 块
        block_start_idx = cursor
        block_end_idx = cursor
        while block_end_idx + 1 < len(token_stream):
            next_token = token_stream[block_end_idx + 1]
            # 块只能由 KANJI 和 OTHER 组成
            if next_token.char_type not in (CharType.KANJI, CharType.OTHER):
                break
            if next_token.group_id is not None:
                # --- 智能锚点判断 ---
                # 检查这个词典词是否是一个“真实”的锚点。
                # “真实”意味着它的至少一个读音存在于剩余的平假名流中。
                # 如果不存在，它很可能是一个因为源数据错误而无法匹配的词，
                # 应该被吸收到当前的汉字块中进行统一处理，而不是成为一个独立的锚点。
                group_id = next_token.group_id
                grouped_tokens_for_check = [next_token]
                peek_idx = block_end_idx + 2
                while peek_idx < len(token_stream) and token_stream[peek_idx].group_id == group_id:
                    grouped_tokens_for_check.append(token_stream[peek_idx])
                    peek_idx += 1
                grouped_text_for_check = "".join(t.text for t in grouped_tokens_for_check)

                readings = find_word(JP_VOCAB_TRIE, grouped_text_for_check)
                is_true_anchor = False
                if readings:
                    hira_window = hira_for_match[hira_idx : hira_idx + 100]
                    if any(reading in hira_window for reading in readings):
                        is_true_anchor = True

                if is_true_anchor:
                    break  # 是真实锚点，结束当前块
                # else: 是“虚假”锚点，继续循环，将其吸收到块中
            block_end_idx += 1

        token_block = token_stream[block_start_idx : block_end_idx + 1]
        remaining_hira = hira_for_match[hira_idx:]
        block_results = _handle_kanji_block(token_block, remaining_hira, token_stream)

        if block_results:
            results.extend(block_results)
            ruby_len = sum(len(res[2]) for res in block_results)
            hira_idx += ruby_len
        else:
            block_text = "".join(t.text for t in token_block)
            if any(t.char_type == CharType.KANJI for t in token_block):
                logger.error(f"无法为汉字块 '{block_text}' 生成注音，跳过此块。")

        cursor = block_end_idx + 1

    return results


def process_line(roma_text: str, tokens: list[Token]) -> list[tuple[int, int, str]]:
    """处理单行（或分句后的单段）的核心逻辑，包含分块处理"""
    # 1. 识别作为硬分割符的 SYMBOL 和部分 OTHER token
    processed_roma = roma_text
    dividing_token_indices = set()
    for token in tokens:
        # SYMBOL 总是作为分割符
        if token.char_type == CharType.SYMBOL and token.text.strip():
            try:
                # 由于上游已进行NFKC归一化，这里可以直接构建pattern
                pattern = r"\s*".join(map(re.escape, list(token.text)))
                new_roma, count = re.subn(pattern, PLACEHOLDER, processed_roma, count=1, flags=re.IGNORECASE)
                if count > 0:
                    processed_roma = new_roma
                    dividing_token_indices.add(token.start)
            except re.error:
                logger.warning(f"处理符号锚点 '{token.text}' 时正则表达式出错，跳过。")
        # OTHER token 只有当其字面量存在于罗马音中时才作为分割符
        elif token.char_type == CharType.OTHER and token.text.strip():
            try:
                pattern = r"\s*".join(map(re.escape, list(token.text.replace(" ", ""))))
                match = re.search(pattern, processed_roma, flags=re.IGNORECASE)
                if match:
                    # 使用 re.subn 替换第一个匹配项
                    new_roma, count = re.subn(pattern, PLACEHOLDER, processed_roma, count=1, flags=re.IGNORECASE)
                    if count > 0:
                        processed_roma = new_roma
                        dividing_token_indices.add(token.start)
            except re.error:
                logger.warning(f"处理OTHER锚点 '{token.text}' 时正则表达式出错，跳过。")

    logger.debug(f"处理锚点后的罗马音: '{processed_roma}'")

    hira_from_roma_raw = roma_to_hiragana(processed_roma)
    logger.debug(f"从罗马音转换得到的带占位符的平假名串: '{hira_from_roma_raw}'")

    # 2. 分块处理
    # 根据占位符分割平假名字符串
    hira_chunks = [chunk for chunk in hira_from_roma_raw.split(PLACEHOLDER) if chunk.strip()]

    # 根据真正造成分割的Token来分割Token列表
    token_chunks: list[list[Token]] = []
    current_chunk: list[Token] = []
    for token in tokens:
        if token.start in dividing_token_indices:
            if current_chunk:
                token_chunks.append(current_chunk)
            # 分割符本身不进入任何一个chunk
            current_chunk = []
        else:
            current_chunk.append(token)
    if current_chunk:
        token_chunks.append(current_chunk)

    if len(hira_chunks) != len(token_chunks):
        logger.warning(
            f"平假名块 ({len(hira_chunks)}) 与Token块 ({len(token_chunks)}) 数量不匹配。将回退到整块处理模式。",
        )
        logger.debug(f"平假名块: {hira_chunks}")
        logger.debug(f"Token块: {[t.text for chunk in token_chunks for t in chunk]}")
        # 回退逻辑：将整个原始罗马音转换为平假名，并使用完整的Token列表进行处理
        hira_for_match = "".join(c for c in roma_to_hiragana(roma_text) if "\u3040" <= c <= "\u309f")
        logger.debug("--- 回退到整块处理 ---")
        logger.debug(f"Token块: {tokens}")
        logger.debug(f"平假名块: '{hira_for_match}'")
        return generate_ruby_for_chunk(tokens, hira_for_match)

    # 3. 对每一块进行处理并合并结果
    all_results: list[tuple[int, int, str]] = []
    for i in range(len(token_chunks)):
        token_chunk = token_chunks[i]
        hira_chunk_raw = hira_chunks[i]
        hira_for_match = "".join(c for c in hira_chunk_raw if "\u3040" <= c <= "\u309f")

        logger.debug(f"--- 处理块 {i + 1}/{len(token_chunks)} ---")
        logger.debug(f"Token块: {token_chunk}")
        logger.debug(f"平假名块: '{hira_for_match}'")

        chunk_results = generate_ruby_for_chunk(token_chunk, hira_for_match)
        all_results.extend(chunk_results)

    return all_results
