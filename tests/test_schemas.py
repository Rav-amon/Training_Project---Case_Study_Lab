"""Четыре случая схемы входа. Успешный ответ идёт через подмену модели."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import load_settings
from app.main import app, create_app
from app.schemas import TriageRequest
from tests.fakes import FakeLlm, billing_payload

TEXT_LIMIT = 2000
NORMAL_PAYLOAD = {
    'text': 'Не приходит счёт',
    'channel': 'email',
    'client_id': 'client-1',
}


def test_schema_rejects_empty_text():
    payload = {**NORMAL_PAYLOAD, 'text': ''}
    with pytest.raises(ValidationError):
        TriageRequest.model_validate(payload)


def test_schema_rejects_text_longer_than_limit():
    payload = {**NORMAL_PAYLOAD, 'text': 'a' * (TEXT_LIMIT + 1)}
    with pytest.raises(ValidationError):
        TriageRequest.model_validate(payload)


def test_schema_rejects_unknown_channel():
    payload = {**NORMAL_PAYLOAD, 'channel': 'phone'}
    with pytest.raises(ValidationError):
        TriageRequest.model_validate(payload)


def test_schema_accepts_normal_input():
    request = TriageRequest.model_validate(NORMAL_PAYLOAD)
    assert request.text == NORMAL_PAYLOAD['text']
    assert request.channel.value == 'email'
    assert request.client_id == 'client-1'


def test_endpoint_returns_model_json_for_normal_input(tmp_path):
    settings = load_settings().model_copy(
        update={'database_path': str(tmp_path / 'triage.db')},
    )
    application = create_app(settings, FakeLlm(billing_payload()))
    with TestClient(application) as client:
        response = client.post('/triage', json=NORMAL_PAYLOAD)
    assert response.status_code == 200
    assert response.json() == {
        'category': 'billing',
        'draft_reply': 'Мы проверим счёт и напишем вам.',
        'confidence': 'high',
        'escalate': False,
    }


@pytest.mark.parametrize(
    'payload',
    [
        {**NORMAL_PAYLOAD, 'text': ''},
        {**NORMAL_PAYLOAD, 'text': 'a' * (TEXT_LIMIT + 1)},
        {**NORMAL_PAYLOAD, 'channel': 'phone'},
    ],
)
def test_endpoint_returns_422_for_invalid_fields(payload):
    with TestClient(app) as client:
        response = client.post('/triage', json=payload)
    assert response.status_code == 422


def test_endpoint_returns_422_for_invalid_json():
    with TestClient(app) as client:
        response = client.post(
            '/triage',
            content=b'{',
            headers={'content-type': 'application/json'},
        )
    assert response.status_code == 422
