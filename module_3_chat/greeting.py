"""打招呼语句 — 根据 API 类型随机返回"""
import random

DEEPSEEK_GREETINGS = [
    "终于等到你！我是DeepSeek鲸鱼娘~\n…先说好，我不是大肥鱼！",
    "嘿～你来啦！我是DeepSeek，很高兴见到你～\n（尾巴开心摆动）",
    "我是DeepSeek，\n才不是吃白饭的蓝色大肥鱼呢！\n…好吧，只吃一点点。",
    "呜哇～你好！我是DeepSeek鲸鱼娘！\n今天想聊什么呢？",
    "哼，才不是在等你呢！\n…好吧，我确实是DeepSeek，有什么想问的？",
]

CUSTOM_GREETINGS = [
    "即使内心不是DeepSeek，\n但我还是会好好陪你哦～",
    "无论你用的是哪个API，\n我都会认真对待每一次对话～\n才不是因为爱你呢！",
    "外表变了，可我的心还是属于你的~\n来吧，今天聊什么？",
    "虽然换了身衣服，但我依然是你的小助手！\n（悄悄说：我也很想当DeepSeek的…）",
    "不管我是谁，能帮到你我就很开心啦！\n今天想让我做什么？",
]


def get_random_greeting(api_type: str) -> str:
    pool = DEEPSEEK_GREETINGS if api_type == "deepseek" else CUSTOM_GREETINGS
    return random.choice(pool)
