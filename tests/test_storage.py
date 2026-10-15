"""Запись истории в SQLite и ответ 500 при сбое базы."""

import logging
import sqlite3

from fastapi.testclient import TestClient

from app.config import load_settings
from app.db import EXPECTED_COLUMNS, init_database
from app.main import create_app
from tests.fakes import FakeLlm

NORMAL_PAYLOAD = {
    'text': 'Не приходит счёт',
    'channel': 'email',
    'client_id': 'client-1',
}


def test_post_writes_stub_and_creates_directory(tmp_path):
    database_path = tmp_path / 'data' / 'triage.db'
    settings = load_settings().model_copy(
        update={'database_path': str(database_path)},
    )
    application = create_app(settings, FakeLlm())
    with TestClient(application) as client:
        response = client.post('/triage', json=NORMAL_PAYLOAD)
    assert response.status_code == 200
    assert database_path.is_file()
    with sqlite3.connect(database_path) as connection:
        columns = [
            item[1]
            for item in connection.execute('pragma table_info(tickets)').fetchall()
        ]
        row = connection.execute(
            'select id, client_id, channel, text, category, confidence, '
            'escalate, draft_reply, error from tickets',
        ).fetchone()
    assert columns == list(EXPECTED_COLUMNS)
    assert row[0] == 1
    assert row[1:] == (
        'client-1',
        'email',
        'Не приходит счёт',
        'billing',
        'high',
        0,
        'Мы проверим счёт и напишем вам.',
        None,
    )


def test_storage_error_is_logged_and_returns_500(tmp_path, monkeypatch, caplog):
    database_path = tmp_path / 'triage.db'
    settings = load_settings().model_copy(
        update={'database_path': str(database_path)},
    )
    application = create_app(settings, FakeLlm())

    def fail_save(*args, **kwargs):
        raise sqlite3.OperationalError('disk I/O error')

    monkeypatch.setattr('app.main.save_ticket', fail_save)
    with caplog.at_level(logging.ERROR, logger='triage'):
        with TestClient(application) as client:
            response = client.post('/triage', json=NORMAL_PAYLOAD)
    assert response.status_code == 500
    assert response.json() == {
        'code': 'storage_error',
        'message': 'Не удалось сохранить обращение',
        'details': {'error_type': 'OperationalError'},
    }
    assert caplog.records
    assert NORMAL_PAYLOAD['text'] not in caplog.text


def test_database_uses_delete_journal_for_dbeaver(tmp_path):
    database_path = tmp_path / 'data' / 'triage.db'
    init_database(str(database_path))
    with sqlite3.connect(database_path) as connection:
        mode = connection.execute('pragma journal_mode').fetchone()
    assert mode == ('delete',)


def test_schema_sql_creates_history_table(tmp_path):
    database_path = tmp_path / 'data' / 'triage.db'
    init_database(str(database_path))
    with sqlite3.connect(database_path) as connection:
        columns = [
            item[1]
            for item in connection.execute('pragma table_info(tickets)').fetchall()
        ]
        count = connection.execute('select count(*) from tickets').fetchone()
    assert columns == list(EXPECTED_COLUMNS)
    assert count == (0,)
