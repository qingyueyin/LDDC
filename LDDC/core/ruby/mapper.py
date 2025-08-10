# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
"""索引映射器模块，用于处理原始坐标和归一化坐标之间的转换。"""

import unicodedata


class IndexMapper:
    """管理原始字符串和其NFKC归一化版本之间的索引映射。

    这个类解决了因 `unicodedata.normalize("NFKC", ...)` 改变字符串长度
    （例如，将全角省略号 '…' 转换为三个半角点 '...'）而导致的索引偏移问题。

    它生成一个从“归一化后”的索引到“原始”索引的映射表，
    允许核心逻辑在稳定的归一化文本上运行，同时能够在最后输出精确的原始坐标。
    """

    __slots__ = ("_normalized_to_original_map", "normalized_text", "original_text")

    def __init__(self, original_text: str) -> None:
        """初始化映射器并构建索引映射。

        Args:
            original_text (str): 未经处理的原始字符串。

        """
        self.original_text: str = original_text
        self.normalized_text: str
        self._normalized_to_original_map: list[int]

        self.normalized_text, self._normalized_to_original_map = self._build_map(original_text)

    def _build_map(self, text: str) -> tuple[str, list[int]]:
        """构建从归一化文本索引到原始文本索引的映射。

        通过迭代原始字符串的每个字符并跟踪其在归一化版本中的扩展，
        我们可以为归一化后字符串的每个字符找到其对应的原始索引。

        Returns:
            tuple[str, list[int]]: 一个元组，包含:
                - 归一化后的字符串。
                - 一个列表，其索引是归一化字符串的索引，值是对应的原始字符串索引。

        """
        normalized_builder: list[str] = []
        mapping: list[int] = []

        for i, char in enumerate(text):
            normalized_char = unicodedata.normalize("NFKC", char)
            normalized_builder.append(normalized_char)
            # 将当前原始索引 `i` 重复 `len(normalized_char)` 次
            # 例如，如果 '…' (len 1) 变成了 '...' (len 3)，
            # 映射中会有三个连续的条目指向同一个原始索引。
            mapping.extend([i] * len(normalized_char))

        return "".join(normalized_builder), mapping

    def to_original_indices(self, start: int, end: int) -> tuple[int, int]:
        """将归一化文本中的索引范围转换为原始文本中的索引范围。

        Args:
            start (int): 归一化文本中的开始索引。
            end (int): 归一化文本中的结束索引。

        Returns:
            tuple[int, int]: 对应的原始文本中的 (开始索引, 结束索引) 元组。

        """
        if not self._normalized_to_original_map:
            return start, end

        # 边界检查
        norm_len = len(self._normalized_to_original_map)
        if start >= norm_len:
            # 如果开始索引超出范围，返回一个无效但安全的范围
            orig_len = len(self.original_text)
            return orig_len, orig_len

        # 映射开始索引
        original_start = self._normalized_to_original_map[start]

        # 映射结束索引
        # `end` 是一个开区间，所以我们需要映射 `end - 1` 的位置，
        # 然后在原始坐标系中加1来恢复开区间。
        if end > 0 and end <= norm_len:
            original_end_char_index = self._normalized_to_original_map[end - 1]
            original_end = original_end_char_index + 1
        else:
            # 如果 `end` 在字符串末尾或之外，则直接映射到原始字符串的末尾
            original_end = len(self.original_text)

        return original_start, original_end
