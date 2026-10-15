"""Подмена модели: тесты не ходят в сеть."""

import json


def billing_payload() -> str:
    """Валидный JSON про оплату."""

    return json.dumps(
        {
            'category': 'billing',
            'draft_reply': 'Мы проверим счёт и напишем вам.',
            'confidence': 'high',
            'escalate': False,
        },
        ensure_ascii=False,
    )


class FakeLlm:
    """Возвращает заранее заданный JSON и считает вызовы."""

    def __init__(self, raw: str | None = None) -> None:
        self.raw = billing_payload() if raw is None else raw
        self.calls = 0
        self.last_text = ''
        self.last_channel = ''

    def complete(self, text: str, channel: str) -> str:
        self.calls += 1
        self.last_text = text
        self.last_channel = channel
        return self.raw
