"""
Simplified -> Traditional Chinese conversion for the translator input.

The Taigi translator was trained on Traditional Chinese, and simplified input misleads
it (老板好 came out as "Lāu-pô--ah", i.e. 老婆; 老闆好 is "Lāu-pán hó"). The HAN column
mixes both scripts, so lines are converted before translation.

Coverage: every simplified character in the lesson HAN column (2026-10-25) plus common
night-market vocabulary. Characters with several traditional forms are only converted
inside the phrases listed in PHRASES (e.g. 面 -> 麵 in 牛肉面, but 里面 -> 裡面 keeps 面);
outside those phrases they are left as-is. Taiwan usage is preferred (卤 -> 滷, 台 kept).
"""

import re

# Converted before single characters; longest phrase wins.
PHRASES = {
    "老板": "老闆",
    "关系": "關係",
    "没关系": "沒關係",
    "面条": "麵條",
    "面线": "麵線",
    "担仔面": "擔仔麵",
    "牛肉面": "牛肉麵",
    "炒面": "炒麵",
    "汤面": "湯麵",
    "意面": "意麵",
    "干面": "乾麵",
    "饼干": "餅乾",
    "头发": "頭髮",
    "一只": "一隻",
    "两只": "兩隻",
    "皇后": "皇后",
}

# One-to-one conversions. Ambiguous characters (面 只 干 系 台 云 准 划 制 冲 斗 发→髮)
# are deliberately missing here or mapped to their usual form in this content.
CHARS = dict(zip(
    "东两个为么买于亲们价会传关几凤别动区卖卤历发后吗听圆块头对带当担据无时条来样欢汤没湾点烧"
    "猪种笋红细经给统绿肠虾试语说请课调谢贡过还这里钱错问闽顾饭饱饼骄鲜鸡黄酱"
    "爱门见现进远边让谁从气热钟号帮饮馆机车书学习写话读认识总业专场员题应该难觉开长张双鱼"
    "盐咸葱姜饺馄饨炖鸭鹅鲁蚝贝凉冻优赠尝闻声乐节庙礼灯码万亿实惯选择极级岁宝妈爷儿孙师摊铺档"
    "罢备够计运风阳阴雾杂锅荐迟",
    "東兩個為麼買於親們價會傳關幾鳳別動區賣滷歷發後嗎聽圓塊頭對帶當擔據無時條來樣歡湯沒灣點燒"
    "豬種筍紅細經給統綠腸蝦試語說請課調謝貢過還這裡錢錯問閩顧飯飽餅驕鮮雞黃醬"
    "愛門見現進遠邊讓誰從氣熱鐘號幫飲館機車書學習寫話讀認識總業專場員題應該難覺開長張雙魚"
    "鹽鹹蔥薑餃餛飩燉鴨鵝魯蠔貝涼凍優贈嘗聞聲樂節廟禮燈碼萬億實慣選擇極級歲寶媽爺兒孫師攤鋪檔"
    "罷備夠計運風陽陰霧雜鍋薦遲",
))

_PHRASE_RE = re.compile("|".join(sorted(map(re.escape, PHRASES), key=len, reverse=True)))


def to_traditional(text):
    if not text:
        return text
    text = _PHRASE_RE.sub(lambda m: PHRASES[m.group(0)], text)
    return "".join(CHARS.get(ch, ch) for ch in text)
