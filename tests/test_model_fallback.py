"""Поломка модели остаётся ответом 200 и пишется в tickets.error."""

import sqlite3

from fastapi.testclient import TestClient

from app.config import load_settings
from app.interpret import FALLBACK_DRAFT_REPLY
from app.llm import LlmError, OpenAIChatClient
from app.main import create_app
from tests.fakes import FakeLlm

PAYLOAD = {
    'text': 'привет',
    'channel': 'chat',
    'client_id': 'client-fallback',
}


def _app(tmp_path, llm):
    settings = load_settings().model_copy(
        update={'database_path': str(tmp_path / 'triage.db')},
    )
    return create_app(settings, llm), settings.database_path


def test_broken_model_json_is_escalation(tmp_path):
    secret = 'сырой-ответ-модели'
    application, database_path = _app(tmp_path, FakeLlm(secret))
    with TestClient(application) as client:
        response = client.post('/triage', json=PAYLOAD)
    assert response.status_code == 200
    body = response.json()
    assert body['category'] == 'other'
    assert body['confidence'] == 'low'
    assert body['escalate'] is True
    assert body['draft_reply'] == FALLBACK_DRAFT_REPLY
    assert secret not in response.text
    with sqlite3.connect(database_path) as connection:
        error = connection.execute('select error from tickets').fetchone()
    assert error == ('invalid_json',)


def test_low_confidence_passes_through(tmp_path):
    raw = (
        '{"category":"other","draft_reply":"Уточните, пожалуйста, вопрос.",'
        '"confidence":"low","escalate":true}'
    )
    application, _database_path = _app(tmp_path, FakeLlm(raw))
    with TestClient(application) as client:
        response = client.post('/triage', json=PAYLOAD)
    assert response.status_code == 200
    assert response.json()['confidence'] == 'low'
    assert response.json()['escalate'] is True


class BrokenLlm:
    """Исключение SDK, уже свёрнутое в краткий код."""

    def complete(self, text: str, channel: str) -> str:
        del text, channel
        raise LlmError('timeout')


def test_sdk_failure_returns_200_template(tmp_path):
    application, database_path = _app(tmp_path, BrokenLlm())
    with TestClient(application) as client:
        response = client.post('/triage', json=PAYLOAD)
    assert response.status_code == 200
    assert response.json()['draft_reply'] == FALLBACK_DRAFT_REPLY
    with sqlite3.connect(database_path) as connection:
        error = connection.execute('select error from tickets').fetchone()
    assert error == ('timeout',)


def test_wrong_api_key_stores_error(tmp_path):
    from openai import OpenAIError

    def factory(**kwargs):
        del kwargs
        raise OpenAIError('unauthorized')

    llm = OpenAIChatClient('invalid-key', 'gpt-4o-mini', client_factory=factory)
    application, database_path = _app(tmp_path, llm)
    with TestClient(application) as client:
        response = client.post('/triage', json=PAYLOAD)
    assert response.status_code == 200
    body = response.json()
    assert body['draft_reply'] == FALLBACK_DRAFT_REPLY
    assert body['category'] == 'other'
    assert body['escalate'] is True
    assert 'invalid-key' not in response.text
    assert 'unauthorized' not in response.text
    with sqlite3.connect(database_path) as connection:
        error = connection.execute('select error from tickets').fetchone()
    assert error == ('sdk_error',)
