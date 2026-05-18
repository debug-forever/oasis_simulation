"""Chinese sentiment lexicon and topic keywords."""

POSITIVE_WORDS = {
    "好", "棒", "赞", "强", "优秀", "厉害", "牛", "给力", "支持", "喜欢", "爱",
    "期待", "惊艳", "震撼", "突破", "领先", "创新", "进步", "成功", "胜利",
    "骄傲", "自豪", "信心", "希望", "温暖", "感动", "开心", "高兴", "快乐",
    "满意", "靠谱", "实力", "顶", "yyds", "绝了", "完美", "优质", "亮眼",
    "崛起", "振奋", "提升", "красив", "精彩", "出色", "卓越", "用心", "良心",
    "硬核", "惊喜", "舒服", "流畅", "稳", "香", "值得", "推荐", "认可", "点赞",
    "加油", "争气", "扬眉吐气", "国货之光", "实至名归", "可圈可点", "前景广阔",
}

NEGATIVE_WORDS = {
    "差", "烂", "坑", "垃圾", "失望", "拉胯", "翻车", "崩", "卡", "贵", "智商税",
    "割韭菜", "难用", "退步", "失败", "落后", "抄袭", "虚假", "欺骗", "忽悠",
    "夸张", "吹", "水", "黑", "喷", "骂", "怒", "气", "愤怒", "讨厌", "厌恶",
    "恶心", "无语", "离谱", "辣鸡", "敷衍", "缩水", "卡顿", "发热", "掉电",
    "bug", "故障", "维权", "投诉", "退货", "崩溃", "焦虑", "担忧", "恐慌",
    "质疑", "抵制", "封杀", "打压", "制裁", "危机", "下滑", "暴跌", "亏损",
    "丑", "糟糕", "可惜", "遗憾", "心寒", "寒心", "翻不了身", "不行", "不值",
    "套路", "营销号", "带节奏", "双标", "甩锅",
}

NEGATION_WORDS = {"不", "没", "无", "非", "未", "别", "莫", "勿", "拒绝", "并非", "毫无"}

DEGREE_WORDS = {
    "非常": 1.6, "特别": 1.6, "极其": 1.8, "极": 1.8, "超": 1.5, "超级": 1.7,
    "十分": 1.5, "相当": 1.4, "太": 1.5, "巨": 1.6, "贼": 1.5, "很": 1.3,
    "挺": 1.2, "比较": 0.8, "有点": 0.7, "稍微": 0.6, "略": 0.6,
}

NEGATION_WINDOW = 4  # 否定词影响其后多少字符内的情感词


def score_sentiment(text):
    if not text:
        return 0.0, "中性"
    t = str(text).lower()
    raw = 0.0
    hits = 0

    def _local_factor(pos):
        """计算情感词所在位置前缀的程度/否定修饰系数。"""
        prefix = t[max(0, pos - NEGATION_WINDOW):pos]
        factor = 1.0
        for d, w in DEGREE_WORDS.items():
            if d in prefix:
                factor *= w
                break
        for n in NEGATION_WORDS:
            if n in prefix:
                factor *= -0.8
                break
        return factor

    for w in POSITIVE_WORDS:
        idx = t.find(w)
        while idx != -1:
            raw += 1.0 * _local_factor(idx)
            hits += 1
            idx = t.find(w, idx + len(w))
    for w in NEGATIVE_WORDS:
        idx = t.find(w)
        while idx != -1:
            raw += -1.0 * _local_factor(idx)
            hits += 1
            idx = t.find(w, idx + len(w))

    if hits == 0:
        return 0.0, "中性"
    import math
    score = math.tanh(raw / max(1.5, hits ** 0.5))
    if score > 0.08:
        label = "正面"
    elif score < -0.08:
        label = "负面"
    else:
        label = "中性"
    return round(score, 4), label


TOPIC_KEYWORDS = {
    "华为": ["华为", "harmony", "鸿蒙", "mate", "麒麟", "余承东", "pura"],
    "苹果": ["苹果", "iphone", "ios", "apple", "库克"],
    "芯片": ["芯片", "半导体", "光刻", "制程", "纳米", "5g", "算力"],
    "新能源车": ["新能源", "电动车", "比亚迪", "理想", "蔚来", "小鹏", "特斯拉", "续航"],
    "AI": ["ai", "人工智能", "大模型", "chatgpt", "agent", "智能体"],
    "国产替代": ["国产", "国货", "自主研发", "卡脖子", "自主可控"],
    "财经": ["股价", "市值", "财报", "营收", "利润", "投资", "经济", "出货量"],
    "数码消费": ["手机", "相机", "数码", "智能家居", "耳机", "平板"],
}


def extract_topics(text):
    """
    从文本抽取话题。优先使用 #话题# 标签，否则用关键词兜底。

    Returns:
        (primary_topic, hashtags_list)
    """
    if not text:
        return "其他", []
    import re
    tags = re.findall(r"#([^#\s]{1,30})#", str(text))
    tags = [s.strip() for s in tags if s.strip()]
    if tags:
        return tags[0], tags
    # 关键词兜底
    low = str(text).lower()
    for topic, kws in TOPIC_KEYWORDS.items():
        for kw in kws:
            if kw in low:
                return topic, []
    return "其他", []
