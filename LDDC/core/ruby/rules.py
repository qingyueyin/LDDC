# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
"""日语注音模糊匹配的规则库。"""

from .char_utils import katakana_to_hiragana
from .models import FuncRule, RuleType, SubstitutionRule, Token

# --- Data Maps ---
VOWEL_MAP = {
    "あ": "あ", "か": "あ", "さ": "あ", "た": "あ", "な": "あ", "は": "あ", "ま": "あ", "や": "あ", "ら": "あ", "わ": "あ",
    "が": "あ", "ざ": "あ", "だ": "あ", "ば": "あ", "ぱ": "あ", "ゃ": "あ", "ぁ": "あ", "ゎ": "あ",
    "い": "い", "き": "い", "し": "い", "ち": "い", "に": "い", "ひ": "い", "み": "い", "り": "い",
    "ぎ": "い", "じ": "い", "ぢ": "い", "び": "い", "ぴ": "い", "ぃ": "い",
    "う": "う", "く": "う", "す": "う", "つ": "う", "ぬ": "う", "ふ": "う", "む": "う", "ゆ": "う", "る": "う",
    "ぐ": "う", "ず": "う", "づ": "う", "ぶ": "う", "ぷ": "う", "ゅ": "う", "ぅ": "う",
    "え": "え", "け": "え", "せ": "え", "て": "え", "ね": "え", "へ": "え", "め": "え", "れ": "え",
    "げ": "え", "ぜ": "え", "で": "え", "べ": "え", "ぺ": "え", "ぇ": "え",
    "お": "お", "こ": "お", "そ": "お", "と": "お", "の": "お", "ほ": "お", "も": "お", "よ": "お", "ろ": "お", "を": "お",
    "ご": "お", "ぞ": "お", "ど": "お", "ぼ": "お", "ぽ": "お", "ょ": "お", "ぉ": "お",
}


# --- Rule Constants ---
COST_EQUIVALENT = 0  # 等价替换，如助词 は -> わ
COST_COMMON_VARIANT = 1  # 常见变体，如小假名展开 ゃ -> や
COST_RARE_VARIANT = 2  # 不常见或代价更高的变体，如清浊音互换 か -> が


# --- Rule Functions ---
def _handle_long_vowel(anchor: str, tokens: list[Token], current_token: Token) -> str:
    """处理长音符 'ー' 的函数规则。"""
    if "ー" not in anchor:
        return anchor

    new_anchor = ""
    for i, char in enumerate(anchor):
        if char != "ー":
            new_anchor += char
            continue

        # 确定 'ー' 前面的字符
        prev_char = ""
        if i > 0:
            prev_char = anchor[i - 1]
        else:
            # 如果 'ー' 是 token 的开头, 尝试从上一个 token 获取上下文
            try:
                current_token_idx = tokens.index(current_token)
                if current_token_idx > 0:
                    prev_token_text = tokens[current_token_idx - 1].text
                    if prev_token_text:
                        prev_char = katakana_to_hiragana(prev_token_text[-1])
            except ValueError:
                # 在lookahead的场景下，current_token可能不在tokens里
                pass

        # 转换长音
        vowel = VOWEL_MAP.get(prev_char)
        if vowel:
            new_anchor += vowel
        else:
            new_anchor += "ー"  # 保留无法转换的长音

    return new_anchor


# --- Rule Generation Helpers ---
def _create_substitution_rules(
    pairs: list[tuple[str, str]],
    base_name: str,
    cost_a_to_b: int,
    cost_b_to_a: int | None = None,
) -> list[SubstitutionRule]:
    """根据配对列表，生成替换规则。可以处理对称和非对称代价。"""
    rules = []
    # 如果未提供反向代价，则视为对称
    cost_b_to_a = cost_a_to_b if cost_b_to_a is None else cost_b_to_a

    for a, b in pairs:
        # Rule A -> B
        rules.append(
            SubstitutionRule(
                name=f"{base_name}_{a}_to_{b}",
                cost=cost_a_to_b,
                rule_type=RuleType.SUBSTITUTION,
                content=(a, b),
                introduced_chars=set(b),
            ),
        )
        # Rule B -> A
        rules.append(
            SubstitutionRule(
                name=f"{base_name}_{b}_to_{a}",
                cost=cost_b_to_a,
                rule_type=RuleType.SUBSTITUTION,
                content=(b, a),
                introduced_chars=set(a),
            ),
        )
    return rules


# --- Programmatically generated rules ---

# 1. 长音等价规则 (e.g., こう -> こお)
o_dan = "".join(k for k, v in VOWEL_MAP.items() if v == "お")
e_dan = "".join(k for k, v in VOWEL_MAP.items() if v == "え")
_long_vowel_pairs = [(f"{char}う", f"{char}お") for char in o_dan]
_long_vowel_pairs.extend((f"{char}い", f"{char}え") for char in e_dan)
_long_vowel_rules = _create_substitution_rules(_long_vowel_pairs, "long_vowel", COST_EQUIVALENT)


# 2. 假名大小写变体规则
small_to_large_map = {
    "ぁ": "あ", "ぃ": "い", "ぅ": "う", "ぇ": "え", "ぉ": "お",
    "ゃ": "や", "ゅ": "ゆ", "ょ": "よ", "っ": "つ", "ゎ": "わ",
}
_kana_variation_rules = _create_substitution_rules(
    pairs=list(small_to_large_map.items()),
    base_name="kana_variation",
    cost_a_to_b=COST_COMMON_VARIANT,  # small -> large
    cost_b_to_a=COST_RARE_VARIANT,  # large -> small
)


# 3. 清浊音/半浊音等价规则
voicing_pairs = [
    ("か", "が"), ("き", "ぎ"), ("く", "ぐ"), ("け", "げ"), ("こ", "ご"),
    ("さ", "ざ"), ("し", "じ"), ("す", "ず"), ("せ", "ぜ"), ("そ", "ぞ"),
    ("た", "だ"), ("ち", "ぢ"), ("つ", "づ"), ("て", "で"), ("と", "ど"),
    ("は", "ば"), ("ひ", "び"), ("ふ", "ぶ"), ("へ", "べ"), ("ほ", "ぼ"),
    ("は", "ぱ"), ("ひ", "ぴ"), ("ふ", "ぷ"), ("へ", "ぺ"), ("ほ", "ぽ"),
    ("ば", "ぱ"), ("び", "ぴ"), ("ぶ", "ぷ"), ("べ", "ぺ"), ("ぼ", "ぽ"),
]
_voicing_rules = _create_substitution_rules(voicing_pairs, "voicing", COST_RARE_VARIANT)


# --- Final Rule Aggregation ---
ALL_RULES: list[SubstitutionRule | FuncRule] = [
    # --- 等价规则 (Cost = 0) ---
    # 助词
    SubstitutionRule(name="particle_ha_to_wa", cost=COST_EQUIVALENT, rule_type=RuleType.SUBSTITUTION, content=("は", "わ"), introduced_chars={"わ"}),
    SubstitutionRule(name="particle_he_to_e", cost=COST_EQUIVALENT, rule_type=RuleType.SUBSTITUTION, content=("へ", "え"), introduced_chars={"え"}),
    SubstitutionRule(name="particle_wo_to_o", cost=COST_EQUIVALENT, rule_type=RuleType.SUBSTITUTION, content=("を", "お"), introduced_chars={"お"}),
    # 同音异形
    *_create_substitution_rules([("づ", "ず"), ("ぢ", "じ")], "homophone", COST_EQUIVALENT),
    # 长音等价 (自动生成)
    *_long_vowel_rules,
    # 特殊读音
    *_create_substitution_rules([("でぃ", "ぢ"), ("でゅ", "づ")], "special_reading", COST_EQUIVALENT),
    # 长音符展开 (函数规则)
    FuncRule(name="long_vowel_expand", cost=COST_EQUIVALENT, rule_type=RuleType.FUNCTION, content=_handle_long_vowel, introduced_chars=set("あいうえお")),
    # --- 模糊匹配规则 (Cost > 0) ---
    # 备注: 规则的顺序和代价(cost)会影响匹配的优先顺序。
    # Cost = 1: 高频且代价小的变体
    SubstitutionRule(name="sokuon_omission", cost=COST_COMMON_VARIANT, rule_type=RuleType.SUBSTITUTION, content=("っ", ""), introduced_chars=set()),
    SubstitutionRule(name="sokuon_to_tsu", cost=COST_COMMON_VARIANT, rule_type=RuleType.SUBSTITUTION, content=("っ", "つ"), introduced_chars={"つ"}),
    SubstitutionRule(name="hatsuon_omission", cost=COST_COMMON_VARIANT, rule_type=RuleType.SUBSTITUTION, content=("ん", ""), introduced_chars=set()),
    *_kana_variation_rules,  # 假名大小写变体
    # Cost = 2: 代价较大或频率较低的变体
    SubstitutionRule(name="long_vowel_omission", cost=COST_RARE_VARIANT, rule_type=RuleType.SUBSTITUTION, content=("ー", ""), introduced_chars=set()),
    *_voicing_rules,  # 清浊音/半浊音 (か -> が)
]
