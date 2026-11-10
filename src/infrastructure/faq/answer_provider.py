import json
from pathlib import Path

from src.application.ports import AnswerProvider
from src.domain.entities import Language

FAQ_PATH = Path(__file__).parent / "faq.json"


class FaqAnswerProvider(AnswerProvider):
    """Savolda mavzuga oid kalit so'z topilsa, shu mavzu bo'yicha tayyor javob beradi.
    Kalit so'zlar barcha tillarda tekshiriladi (foydalanuvchi boshqa tilda yozishi mumkin),
    javob esa foydalanuvchi tanlagan tilda qaytariladi."""

    def __init__(self, path: Path = FAQ_PATH) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        self._topics: dict[str, dict] = data["topics"]
        self._default: dict[str, str] = data["default"]

    async def answer(self, question: str, language: Language) -> str:
        text = question.casefold()
        for topic in self._topics.values():
            keywords = (kw for words in topic["keywords"].values() for kw in words)
            if any(keyword in text for keyword in keywords):
                return topic["answers"][language.value]
        return self._default[language.value]
