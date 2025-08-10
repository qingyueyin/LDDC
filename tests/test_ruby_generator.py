# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
import pytest

from LDDC.common.logger import logger
from LDDC.common.models import FSLyricsLine, FSLyricsWord
from LDDC.core.ruby import generate_ruby

from .ruby_test_cases import test_cases as more_test_cases

# 定义所有测试用例的数据
# 算法的目标是在现有信息下提供最好的结果，部分情况无法处理，如：空格分隔的汉字，如果罗马音中没有更多的信息，则会合并为一个注音
# 格式: (test_name, orig_text, roma_text, expected_result)
# expected_result 是一个列表，每个元素是一个元组，包含起始索引、结束索引、假名注音，预期结果应该为算法能实现的最佳结果
test_cases = [
    (
        "基础汉字和假名",
        "私が見る世界",
        "watashi ga miru sekai",
        [(0, 1, "わたし"), (2, 3, "み"), (4, 6, "せかい")],
    ),
    (
        "分句处理",
        "思い出が 何もかもが 消え去り",
        "o mo i de ga   na ni mo ka mo ga   ki e sa ri",
        [(0, 1, "おも"), (2, 3, "で"), (5, 6, "なに"), (11, 12, "き"), (13, 14, "さ")],
    ),
    (
        "混合英文 1 (边界问题)",
        "Don't-生-War Lie-兵士-War-World",
        "Don't- sei -War Lie- hei shi -War-World",
        [(6, 7, "せい"), (16, 18, "へいし")],
    ),
    (
        "混合英文 2",
        "愛してる Game世界のDay",
        "a i shi te ru   Game se ka i no Day",
        [(0, 1, "あい"), (9, 11, "せかい")],
    ),
    (
        "片假名与汉字混合",
        "新たなレベルへ",
        "arata na reberu e",
        [(0, 1, "あら")],
    ),
    (
        "行末汉字",
        "明日を夢見て",
        "ashita wo yumemite",
        [(0, 2, "あした"), (3, 4, "ゆめ"), (4, 5, "み")],
    ),
    (
        "复杂音节 (促音等)",
        "ずっと一緒だって信じてた",
        "zutto issho datte shinjiteta",
        [(3, 5, "いっしょ"), (8, 9, "しん")],
    ),
    (
        "叠字符号",
        "堂々さらした罪の群れと",
        "do u do u sa ra shi ta tsu mi no mu re to",
        [(0, 2, "どうどう"), (6, 7, "つみ"), (8, 9, "む")],
    ),
    (
        "指针同步",
        "こぼれた温もりさえ拾い続け",
        "ko bo re ta nu ku mo ri sa e hi ro i tsu du ke",
        [(4, 5, "ぬく"), (9, 10, "ひろ"), (11, 12, "つづ")],
    ),
    (
        "罗马音转换",
        "無邪気に綴る 毎日は幸せで",
        "mu ja ki ni tsu du ru   ma i ni chi ha shi a wa se de",
        [(0, 3, "むじゃき"), (4, 5, "つづ"), (7, 9, "まいにち"), (10, 11, "しあわ")],
    ),
    (
        "特殊符号",
        "そっとココロ放って",
        "so 't to ko ko ro ha na 't te",
        [(6, 7, "はな")],
    ),
    (
        "非标准罗马音1",
        "僅かにちらつく灯り消し",
        "wazu ka ni qi la cu ku aka li ke xi",
        [(0, 1, "わず"), (7, 8, "あか"), (9, 10, "け")],
    ),
    (
        "非标准罗马音2",
        "ゆっくりと進んで行く",
        "yu  ku li to susu n de yu ku",
        [(5, 6, "すす"), (8, 9, "ゆ")],
    ),
    (
        "模糊匹配1",
        "二人手をぎゅっとぎゅっと重ねて",
        "uta li te wo gi yu  to gi yu  to kasa ne te ",
        [(0, 2, "ふたり"), (2, 3, "て"), (12, 13, "かさ")],
    ),
    (
        "非标准罗马音4",
        "君はただ立ちつくす",
        "kimi wa ta da ta qi cu ku su ",
        [(0, 1, "きみ"), (4, 5, "た")],
    ),
    (
        "模糊匹配2",
        "星はきっときっと瞬く",
        "hoxi wa ki  to ki  to matata ku ",
        [(0, 1, "ほし"), (8, 9, "またた")],
    ),
    (
        "づ/ず 不匹配问题",
        "心近づく",
        "ko ko ro chi ka zu ku",
        [(0, 1, "こころ"), (1, 2, "ちか")],
    ),
    (
        "C失败回退",
        "痺れる感覚 愛 高鳴るぬくもり",
        "shi bi re ru ka n ka ku    ta ka na ru nu ku mo ri ",
        [(0, 1, "しび"), (3, 10, "かんかくたかな")],
    ),
    (
        "片假名长音省略",
        "アイム最強ガール ah ah",
        "a i mu sa i kyo u ga ru  ah ah",
        [(3, 5, "さいきょう")],
    ),
    (
        "n后面的撇号作为分隔符",
        "信一",
        "shin'ichi",
        [(0, 2, "しんいち")],
    ),
    (
        "组合模糊匹配 (拗音+促音)",
        "正義っちゃ正義",
        "seigi cha seigi",
        [(0, 2, "せいぎ"), (5, 7, "せいぎ")],
    ),
    (
        "ぴょんぴょん拗音 1",
        "こころぴょんぴょん待ち?",
        "ko ko ro pyo n pyo n ma chi ? ",
        [(9, 10, "ま")],
    ),
    (
        "ぴょんぴょん拗音 2",
        "いたずら笑顔でぴょんぴょん",
        "i ta zu ra e ga o de pyo n pyo n ",
        [(4, 6, "えがお")],
    ),
    (
        "ぴょんぴょん拗音 3",
        "いつもぴょんぴょん可能",
        "i tsu mo pyo n pyo n ka no u ",
        [(9, 11, "かのう")],
    ),
    (
        "汉字与片假名长音",
        "東京タワー",
        "toukyou tawa-",
        [(0, 2, "とうきょう")],
    ),
    (
        "引号与汉字",
        "「最高」と言った",
        "saikou to itta",
        [(1, 3, "さいこう"), (5, 6, "い")],
    ),
    (
        "纯假名行",
        "こんにちは",
        "konnichiwa",
        [],
    ),
    (
        "纯英文行",
        "Hello World",
        "Hello World",
        [],
    ),
    (
        "罗马音m/n转换",
        "先輩の新聞",
        "sempai no shimbun",
        [(0, 2, "せんぱい"), (3, 5, "しんぶん")],
    ),
    (
        "全角空格处理",
        "ハミダシてた　恋と",
        "ha mi da shi te ta  ko i to",
        [(7, 8, "こい")],
    ),
    (
        "数字处理",
        "一緒に過ごす１つ１つが愛しくて",
        "i ssho ni su go su hi to tsu hi to tsu ga i to shi ku te",
        [(0, 2, "いっしょ"), (3, 4, "す"), (6, 7, "ひと"), (8, 9, "ひと"), (11, 12, "いと")],
    ),
    (
        "数字与汉字处理",
        "２人は変わらずにいれるかな",
        "fu ta ri wa ka wa ra zu ni i re ru ka na",
        [(0, 2, "ふたり"), (3, 4, "か")],
    ),
    (
        "贪婪匹配",
        "輝く星の下 私は今息をする",
        "ka ga ya ku ho shi no shi ta   wa ta shi ha i ma i ki wo su ru ",
        [(0, 1, "かがや"), (2, 3, "ほし"), (4, 5, "した"), (6, 7, "わたし"), (8, 9, "いま"), (9, 10, "いき")],
    ),
    (
        "空注音",
        "夏の面影を振り返るよ",
        "na tsu no o mo ka ge wo fu ri ka e ru yo ",
        [(0, 1, "なつ"), (2, 4, "おもかげ"), (5, 6, "ふ"), (7, 8, "かえ")],
    ),
    (
        "助词ha匹配",
        "橋は曲線形状をして",
        "ha shi ha kyo ku se n ke i jo u wo shi te ",
        [(0, 1, "はし"), (2, 6, "きょくせんけいじょう")],
    ),
    (
        "多重ha匹配",
        "幾億も灰は降って",
        "i ku o ku mo ha i ha fu 't te ",
        [(0, 2, "いくおく"), (3, 4, "はい"), (5, 6, "ふ")],
    ),
    (
        "促音与平假名つ不匹配",
        "ぎゅっと抱きしめたら",
        "gyu tsu to da ki shi me ta ra",
        [(4, 5, "だ")],
    ),
    (
        "百分号和引号",
        "1000%「スキ」で満たしていきたいから",
        "se n %「 su ki 」 de mi ta shi te i ki ta i ka ra",
        [(0, 5, "せん"), (10, 11, "み")],
    ),
    (
        "括号内英文",
        "(simple as that) 忘れない",
        "wa su re na i",
        [(17, 18, 'わす')],
    ),
    (
        "复杂匹配 1",
        "だって似た者同士の僕ら",
        "da tte ni ta mo no do u shi no bo ku ra",
        [(3, 4, "に"), (5, 8, "ものどうし"), (9, 10, "ぼく")],
    ),
    (
        "复杂匹配 2",
        "恋一滴 想い纺いでく",
        "ko i i chi te ki o mo i tsu mu i de ku",
        [(0, 1, "こ"), (1, 2, 'いち'),(2, 5, 'てきおも'), (6, 7, "つむ")],
        # 或许应该是[(0, 1, 'こい'), (1, 2, 'いち'), (2, 5, 'てきおも'), (6, 7, 'つむ')]
    ),
    (
        "复杂匹配 3",
        "早すぎる合図 二人笑い出してるいつまでも",
        "ha ya su gi ru a i zu fu ta ri wa ra i da shi te ru i tsu ma de mo",
        [(0, 1, 'はや'), (4, 6, 'あいず'), (7, 9, 'ふたり'), (9, 10, 'わら'), (11, 12, 'だ')],
    ),
    (
        "复杂匹配 4",
        "芽生えた炎 胸の奥に灯して",
        "me ba e ta honoo mune no oku ni tomo shi te",
        [(0, 2, 'めば'), (4, 5, 'ほのお'), (6, 7, 'むね'), (8, 9, 'おく'), (10, 11, 'とも')],
    ),
    (
        "复杂匹配 5",
        "可能性の限界まで",
        "ka no u se i no ge n ka i ma de",
        [(0, 2, 'かのう'), (2, 3, 'せい'), (4, 6, 'げんかい')],
    ),
    (
        "复杂匹配 6",
        "そんな台詞繰り返すことに溺れて",
        "so n na se ri fu ku ri ka e su ko to ni o bo re te",
        [(3, 6, "せりふく"), (7, 8, "かえ"), (12, 13, "おぼ")],
    ),
    (
        "复杂匹配 7",
        " 遮二無二足掻き喰らい再三嗤い",
        "sha ni mu ni a ga ki ku ra i sa i sa n wa ra i",
        [(1, 7, "しゃにむにあが"), (8, 9, "く"), (11, 14, "さいさんわら")],
    ),
    (
        "复杂匹配 8",
        "似顔絵が消されるように",
        "ni ga o e ga ke sa re ru yo u ni",
        [(0, 3, "にがおえ"), (4, 5, "け")],
    ),
    (
        "行末英文不应被注音 1",
        " 風見鶏のポーズ (ピヨピヨ! Just Do It!)",
        "ka za mi do ri no poo zu",
        [(1, 4, "かざみどり")],
    ),
    (
        "行末英文不应被注音 2",
        " 頭を揺らすポーズ (ピヨピヨ! Just Do It!)",
        "a ta ma wo yu ra su poo zu",
        [(1, 2, "あたま"), (3, 4, "ゆ")],
    ),
    (
        "带括号的预设注音",
        "現れる陽 紅(くれ)る世界",
        "a ra wa re ru hi ku re na i ru se ka i",
        [(0, 1, 'あらわ'), (3, 4, 'ひ'), (5, 6, 'くれ'), (11, 13, 'せかい')],
        # 或许应该是 [(0, 1, 'あら'), (3, 4, 'ひ'), (5, 6, 'くれ'), (11, 13, 'せかい')]
    ),
        (
        "片假名长音符1",
        "ハートのリズム高鳴って",
        "ha a to no ri zu mu ta ka na 't te ",
        [(7, 9, "たかな")],
    ),
    (
        "片假名长音符2",
        "ハートのリズムを掴んで",
        "ha a to no ri zu mu wo tsu ka n de ",
        [(8, 9, "つか")],
    ),
        (
        "外来语 fi 和促音 't",
        "フィナーレまで舞って歌ってる",
        "fi na a re ma de ma 't te u ta 't te ru",
        [(7, 8, "ま"), (10, 11, "うた")],
    ),
    (
        "助词 'を' 导致汉字读音被截断",
        "炎を掲げて",
        "ho no o wo ka ka ge te",
        [(0, 1, "ほのお"), (2, 3, "かか")],
    ),
    (
        "评分系统",
        "歌え彼方を 歌え永劫",
        "u ta e ka na ta wo   u ta e e i go u ",
        [(0, 1, 'うた'), (2, 4, 'かなた'), (6, 7, 'うた'), (8, 10, 'えいごう')],
    ),
    (
        "字典送假名处理",
        "闇に溶けて 巡る世界",
        "ya mi ni to ke te   me gu ru se ka i ",
        [(0, 1, 'やみ'), (2, 3, 'と'), (6, 7, 'めぐ'), (8, 10, 'せかい')],
    ),
    (
        "词典匹配-含假名",
        "有り難う",
        "a ri ga to u",
        [(0, 1, "あ"), (2, 3, "がと")],
    ),
    (
        "模糊匹配 - 长音等价",
        "ゆこう 思い出を重ねて",
        "yukoo omoidewo kasanete",
        [(4, 5, 'おも'), (6, 7, 'で'), (8, 9, 'かさ')],
    ),
    (
        "模糊匹配 - 长音等价2",
        "ゆこう　シナリオは続くよ",
        "yukoo shinariowa tsudukuyo",
        [(9, 10, 'つづ')],
    ),
    (
        "NFKC 归一化 - 省略号",
        "う…ちょっと緊張してきたかも",
        "u...chotto kinchou shitekitakamo",
        [(6, 8, "きんちょう")],
    ),
    (
        "训读1",
        "理があるなら",
        "kotowali ga a lu na la",
        [(0, 1, 'ことわり')],
    ),
    (
        "训读2",
        "映る僕たちは幻",
        "wucu lu boku ta qi wa maboloxi",
        [(0, 1, 'うつ'), (2, 3, 'ぼく'), (6, 7, 'まぼろし')],
    ),
    # ------------错误处理------------------
    (
        "时间戳罗马音",
        "天壌を翔る者たち - Love Planet Five",
        "[0,22850]",
        [],
    ),
    (
        "罗马音与原文严重不匹配",
        "ドキドキと急ぐ",
        "ka la fu lu ni xi qi a e ",
        [],
    ),
    (
        "中间部分失败但后续同步成功",
        "朝食を抜いて、夜は来る",
        "choushoku o, yoru wa kuru",
        [(0, 2, "ちょうしょく"), (7, 8, "よる"), (9, 10, "く")],
    ),
]


def visualize_result(original_text: str, ruby_result: list[tuple[int, int, str]]) -> str:
    """将注音结果可视化，方便查看。"""
    visual_result = list(original_text)
    # 从后往前替换，避免索引偏移
    for start, end, ruby in sorted(ruby_result, key=lambda x: x[0], reverse=True):
        visual_result[start:end] = list(f"【{original_text[start:end]}】[{ruby}]")
    return "".join(visual_result)


@pytest.mark.parametrize(("name", "orig_text", "roma_text", "expected"), test_cases + more_test_cases)
def test_generate_ruby(name: str, orig_text: str, roma_text: str, expected: list[tuple[int, int, str]]) -> None:
    """使用pytest参数化来运行所有测试用例"""
    # 修正 FSLyricsLine 的实例化方式
    orig_line = FSLyricsLine(0, 0, [FSLyricsWord(0, 0, orig_text)])
    roma_line = FSLyricsLine(0, 0, [FSLyricsWord(0, 0, roma_text)])

    result = generate_ruby(orig_line, roma_line)

    # pytest可以直接比较列表和元组，断言更简洁
    logger.info("原文: %s", orig_text)
    logger.info("罗马音: %s", roma_text)
    logger.info("结果: %s", result)
    logger.info("预期: %s", expected)
    logger.info("可视化: %s", visualize_result(orig_text, result))
    logger.info("可视化(预期): %s", visualize_result(orig_text, expected))
    assert sorted(result) == sorted(expected), f"测试 '{name}' 失败"
