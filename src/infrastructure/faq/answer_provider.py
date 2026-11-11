import json
import re
from pathlib import Path

from src.application.ports import AnswerProvider
from src.domain.entities import Language

FAQ_PATH = Path(__file__).parent / "faq.json"

# Xitoy yozuvida so'zlar bo'shliq bilan ajratilmaydi, shuning uchun u yerda bo'lak bo'yicha qidiramiz
CJK = re.compile(r"[\u3400-\u9fff]")


class FaqAnswerProvider(AnswerProvider):
    """Savolda mavzuga oid kalit so'z topilsa, shu mavzu bo'yicha tayyor javob beradi.

    Kalit so'z so'zning BOSHIDA bo'lishi kerak ("kartamni" -> "karta" mos, "discard" -> "card"
    mos emas). Kalit so'zlar barcha tillarda tekshiriladi (foydalanuvchi boshqa tilda yozishi
    mumkin), javob esa foydalanuvchi tanlagan tilda qaytariladi. Bir necha mavzu uchrasa,
    savolda birinchi uchragan mavzu tanlanadi."""

    def __init__(self, path: Path = FAQ_PATH) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        self._topics = [
            (_compile(topic["keywords"]), topic["answers"]) for topic in data["topics"].values()
        ]
        self._default: dict[str, str] = data["default"]

    async def answer(self, question: str, language: Language) -> str:
        text = question.casefold()
        best_position, best_answers = len(text) + 1, None
        for pattern, answers in self._topics:
            match = pattern.search(text)
            if match and match.start() < best_position:
                best_position, best_answers = match.start(), answers
        return (best_answers or self._default)[language.value]


def _compile(keywords_by_language: dict[str, list[str]]) -> re.Pattern[str]:
    parts = []
    for keywords in keywords_by_language.values():
        for keyword in keywords:
            keyword = keyword.casefold()
            prefix = "" if CJK.search(keyword) else r"(?<!\w)"
            parts.append(prefix + re.escape(keyword))
    return re.compile("|".join(parts))
