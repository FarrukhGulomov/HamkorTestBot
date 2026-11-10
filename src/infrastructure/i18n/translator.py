import json
from pathlib import Path

from src.domain.entities import DEFAULT_LANGUAGE, Language

LOCALES_DIR = Path(__file__).parent / "locales"


class Translator:
    def __init__(self, locales_dir: Path = LOCALES_DIR) -> None:
        self._messages: dict[Language, dict[str, str]] = {}
        for language in Language:
            path = locales_dir / f"{language.value}.json"
            self._messages[language] = json.loads(path.read_text(encoding="utf-8"))

    def get(self, language: Language, key: str, **params: object) -> str:
        messages = self._messages[language]
        text = messages.get(key) or self._messages[DEFAULT_LANGUAGE][key]
        return text.format(**params) if params else text

    def all_translations(self, key: str) -> set[str]:
        """Bitta kalitning barcha tillardagi matnlari (tugma matnini aniqlash uchun)."""
        return {messages[key] for messages in self._messages.values() if key in messages}
