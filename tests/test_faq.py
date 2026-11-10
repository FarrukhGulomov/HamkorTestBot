import json
import re

import pytest

from src.domain.entities import Language
from src.infrastructure.faq.answer_provider import FAQ_PATH, FaqAnswerProvider


@pytest.fixture
def provider() -> FaqAnswerProvider:
    return FaqAnswerProvider()


@pytest.fixture
def faq() -> dict:
    return json.loads(FAQ_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("question", "topic"),
    [
        ("Omonat ochmoqchiman, foizi qancha?", "deposit"),
        ("Хочу открыть вклад", "deposit"),
        ("What is the deposit rate?", "deposit"),
        ("Kredit olmoqchiman", "credit"),
        ("我想申请贷款", "credit"),
        ("Karta qanday olinadi?", "card"),
        ("Как оформить карту", "card"),
    ],
)
async def test_question_is_matched_to_the_topic(provider, faq, question, topic):
    answer = await provider.answer(question, Language.EN)

    assert answer == faq["topics"][topic]["answers"]["en"]


async def test_answer_uses_selected_language_even_if_question_is_in_another(provider, faq):
    answer = await provider.answer("Omonat ochmoqchiman", Language.RU)

    assert answer == faq["topics"]["deposit"]["answers"]["ru"]


async def test_unknown_question_gets_default_answer(provider, faq):
    answer = await provider.answer("Ob-havo qanday?", Language.UZ)

    assert answer == faq["default"]["uz"]


async def test_matching_ignores_case(provider, faq):
    answer = await provider.answer("OMONAT", Language.UZ)

    assert answer == faq["topics"]["deposit"]["answers"]["uz"]


def test_every_topic_is_answered_in_every_language(faq):
    languages = {language.value for language in Language}

    assert set(faq["default"]) == languages
    for name, topic in faq["topics"].items():
        assert set(topic["answers"]) == languages, name
        assert set(topic["keywords"]) == languages, name


def test_html_tags_are_balanced_and_consistent_across_languages(faq):
    answers_by_topic = {name: topic["answers"] for name, topic in faq["topics"].items()}
    answers_by_topic["default"] = faq["default"]

    for name, answers in answers_by_topic.items():
        for language, text in answers.items():
            assert text.count("<b>") == text.count("</b>"), (name, language)
            assert len(re.findall(r"<b>", text)) == len(re.findall(r"<b>", answers["uz"])), (name, language)
