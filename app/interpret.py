"""Разбор JSON модели. Функция чистая: сеть и HTTP здесь не используются."""

import json

from app.schemas import Category, Confidence, TriageResponse

FALLBACK_DRAFT_REPLY = (
    'Ваше обращение передано оператору. '
    'Специалист посмотрит его и ответит.'
)

REASON_INVALID_JSON = 'invalid_json'
REASON_INVALID_CATEGORY = 'invalid_category'
REASON_INVALID_CONFIDENCE = 'invalid_confidence'
REASON_EMPTY_DRAFT = 'empty_draft'
REASON_INVALID_ESCALATE = 'invalid_escalate'

CATEGORIES = {item.value for item in Category}
CONFIDENCE_LEVELS = {item.value for item in Confidence}


class InterpretedReply:
    """Ответ для клиента и краткая причина, если модель не попала в контракт."""

    def __init__(self, response: TriageResponse, error: str | None) -> None:
        self.response = response
        self.error = error


def fallback_reply(reason: str) -> InterpretedReply:
    """Безопасная эскалация. Сырой текст модели в ответ не входит."""

    return InterpretedReply(
        response=TriageResponse(
            category=Category.other,
            draft_reply=FALLBACK_DRAFT_REPLY,
            confidence=Confidence.low,
            escalate=True,
        ),
        error=reason,
    )


def interpret_model_output(raw: str) -> InterpretedReply:
    """Проверяет JSON модели. При любой поломке возвращает шаблон и причину."""

    try:
        loaded: object = json.loads(raw)
    except json.JSONDecodeError:
        return fallback_reply(REASON_INVALID_JSON)
    if not isinstance(loaded, dict):
        return fallback_reply(REASON_INVALID_JSON)
    category = loaded.get('category')
    if not isinstance(category, str) or category not in CATEGORIES:
        return fallback_reply(REASON_INVALID_CATEGORY)
    confidence = loaded.get('confidence')
    if not isinstance(confidence, str) or confidence not in CONFIDENCE_LEVELS:
        return fallback_reply(REASON_INVALID_CONFIDENCE)
    draft_reply = loaded.get('draft_reply')
    if not isinstance(draft_reply, str) or not draft_reply.strip():
        return fallback_reply(REASON_EMPTY_DRAFT)
    escalate = loaded.get('escalate')
    if not isinstance(escalate, bool):
        return fallback_reply(REASON_INVALID_ESCALATE)
    return InterpretedReply(
        response=TriageResponse(
            category=Category(category),
            draft_reply=draft_reply.strip(),
            confidence=Confidence(confidence),
            escalate=escalate,
        ),
        error=None,
    )
