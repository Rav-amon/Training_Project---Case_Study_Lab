"""Структурный журнал решения. Текст обращения и ключ сюда не попадают."""

import json
import logging

logger = logging.getLogger('triage')

EVENT_HAD_ERROR = 'был_ли_error'


def build_triage_event(
    client_id: str,
    channel: str,
    category: str | None,
    confidence: str | None,
    escalate: bool | None,
    had_error: bool,
) -> dict[str, str | bool | None]:
    """Собирает поля события. Входной текст в словарь не входит."""

    return {
        'client_id': client_id,
        'channel': channel,
        'category': category,
        'confidence': confidence,
        'escalate': escalate,
        EVENT_HAD_ERROR: had_error,
    }


def log_triage_event(
    client_id: str,
    channel: str,
    category: str | None,
    confidence: str | None,
    escalate: bool | None,
    had_error: bool,
) -> None:
    """Пишет одно JSON-событие без текста обращения и без секретов."""

    payload = build_triage_event(
        client_id,
        channel,
        category,
        confidence,
        escalate,
        had_error,
    )
    logger.info(json.dumps(payload, ensure_ascii=False))
