"""Журнал POST /triage не содержит текст обращения и ключ."""

import json
import logging

from fastapi.testclient import TestClient

from app.config import load_settings
from app.main import create_app
from tests.fakes import FakeLlm

SECRET_TEXT = 'уникальный-текст-обращения-4401'
SECRET_KEY = 'sk-test-secret-key-4401'
PAYLOAD = {
    'text': SECRET_TEXT,
    'channel': 'email',
    'client_id': 'client-log',
}


def _events(caplog) -> list[dict[str, object]]:
    events = []
    for record in caplog.records:
        if not record.message.startswith('{'):
            continue
        events.append(json.loads(record.message))
    return events


def test_success_log_has_decision_without_text(tmp_path, caplog):
    settings = load_settings().model_copy(
        update={
            'database_path': str(tmp_path / 'triage.db'),
            'openai_api_key': SECRET_KEY,
        },
    )
    application = create_app(settings, FakeLlm())
    with caplog.at_level(logging.INFO, logger='triage'):
        with TestClient(application) as client:
            response = client.post('/triage', json=PAYLOAD)
    assert response.status_code == 200
    event = _events(caplog)[-1]
    assert event == {
        'client_id': 'client-log',
        'channel': 'email',
        'category': 'billing',
        'confidence': 'high',
        'escalate': False,
        'был_ли_error': False,
    }
    assert SECRET_TEXT not in caplog.text
    assert SECRET_KEY not in caplog.text


def test_fallback_log_marks_error(tmp_path, caplog):
    settings = load_settings().model_copy(
        update={'database_path': str(tmp_path / 'triage.db')},
    )
    application = create_app(settings, FakeLlm('не json ' + SECRET_TEXT))
    with caplog.at_level(logging.INFO, logger='triage'):
        with TestClient(application) as client:
            response = client.post('/triage', json=PAYLOAD)
    assert response.status_code == 200
    event = _events(caplog)[-1]
    assert event['category'] == 'other'
    assert event['confidence'] == 'low'
    assert event['escalate'] is True
    assert event['был_ли_error'] is True
    assert SECRET_TEXT not in caplog.text
