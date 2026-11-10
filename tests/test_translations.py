import re

from src.domain.entities import Language
from src.infrastructure.i18n.translator import JsonTranslator


def test_every_language_has_the_same_keys():
    translator = JsonTranslator()
    reference = set(translator._messages[Language.UZ])

    for language in Language:
        assert set(translator._messages[language]) == reference, language


def test_every_language_keeps_the_same_placeholders_and_html_tags():
    translator = JsonTranslator()
    for key in translator._messages[Language.UZ]:
        tags = {
            language: sorted(re.findall(r"</?b>", translator.get(language, key)))
            for language in Language
        }
        assert len({tuple(v) for v in tags.values()}) == 1, key


def test_settings_button_is_recognised_in_all_languages():
    translator = JsonTranslator()
    assert len(translator.all_translations("settings_button")) == len(Language)
