"""Чистый разбор ответа модели. Сеть не используется."""

from app.interpret import (
    FALLBACK_DRAFT_REPLY,
    interpret_model_output,
)
from app.schemas import Category, Confidence

RAW_SECRET = 'сырой-текст-модели-991'


def test_valid_billing_json():
    raw = (
        '{"category":"billing","draft_reply":" Проверим счёт. ",'
        '"confidence":"high","escalate":false}'
    )
    interpreted = interpret_model_output(raw)
    assert interpreted.error is None
    assert interpreted.response.category is Category.billing
    assert interpreted.response.draft_reply == 'Проверим счёт.'
    assert interpreted.response.confidence is Confidence.high
    assert interpreted.response.escalate is False


def test_broken_json_becomes_fallback():
    interpreted = interpret_model_output(RAW_SECRET)
    assert interpreted.error == 'invalid_json'
    assert interpreted.response.draft_reply == FALLBACK_DRAFT_REPLY
    assert interpreted.response.category is Category.other
    assert interpreted.response.confidence is Confidence.low
    assert interpreted.response.escalate is True
    assert RAW_SECRET not in interpreted.response.draft_reply


def test_unknown_category():
    raw = (
        '{"category":"spam","draft_reply":"Текст.","confidence":"high",'
        '"escalate":false}'
    )
    interpreted = interpret_model_output(raw)
    assert interpreted.error == 'invalid_category'
    assert 'Текст' not in interpreted.response.draft_reply


def test_unknown_confidence():
    raw = (
        '{"category":"support","draft_reply":"Текст.","confidence":"sure",'
        '"escalate":false}'
    )
    assert interpret_model_output(raw).error == 'invalid_confidence'


def test_empty_draft():
    raw = (
        '{"category":"support","draft_reply":"   ","confidence":"high",'
        '"escalate":false}'
    )
    assert interpret_model_output(raw).error == 'empty_draft'
