"""Лимит по client_id: шестой запрос при лимите 5 получает 429."""

import sqlite3

from fastapi.testclient import TestClient

from app.config import load_settings
from app.main import create_app
from tests.fakes import FakeLlm

PAYLOAD = {
    'text': 'Не приходит счёт',
    'channel': 'email',
    'client_id': 'client-limit',
}
OTHER_PAYLOAD = {**PAYLOAD, 'client_id': 'client-other'}


def _application(tmp_path, limit: int):
    database_path = tmp_path / 'triage.db'
    settings = load_settings().model_copy(
        update={
            'database_path': str(database_path),
            'rate_limit_per_minute': limit,
        },
    )
    return create_app(settings, FakeLlm()), database_path


def test_sixth_request_is_rate_limited(tmp_path):
    application, database_path = _application(tmp_path, application_limit(tmp_path))
    limit = application.state.settings.rate_limit_per_minute
    with TestClient(application) as client:
        statuses = [
            client.post('/triage', json=PAYLOAD).status_code
            for _ in range(limit)
        ]
        blocked = client.post('/triage', json=PAYLOAD)
    assert statuses == [200] * limit
    assert blocked.status_code == 429
    body = blocked.json()
    assert body['code'] == 'rate_limited'
    assert body['message'] == 'Слишком много запросов'
    retry_after = body['details']['retry_after_seconds']
    assert isinstance(retry_after, int)
    assert retry_after >= 1
    with sqlite3.connect(database_path) as connection:
        error = connection.execute(
            'select error from tickets order by id desc limit 1',
        ).fetchone()
    assert error == ('rate_limited',)


def test_other_client_is_not_limited(tmp_path):
    application, _database_path = _application(tmp_path, application_limit(tmp_path))
    limit = application.state.settings.rate_limit_per_minute
    with TestClient(application) as client:
        for _ in range(limit):
            assert client.post('/triage', json=PAYLOAD).status_code == 200
        assert client.post('/triage', json=PAYLOAD).status_code == 429
        other = client.post('/triage', json=OTHER_PAYLOAD)
    assert other.status_code == 200


def application_limit(tmp_path) -> int:
    """Берёт лимит из настроек процесса, а не из числа в тесте маршрута."""

    del tmp_path
    return load_settings().rate_limit_per_minute
