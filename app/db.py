"""SQLite-история обращений. Схема лежит в data/schema.sql для DBeaver."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.schemas import TriageRequest, TriageResponse

SCHEMA_PATH = Path(__file__).resolve().parents[1] / 'data' / 'schema.sql'
BUSY_TIMEOUT_MS = 5000

INSERT_TICKET_SQL = """
INSERT INTO tickets (
    created_at,
    client_id,
    channel,
    text,
    category,
    confidence,
    escalate,
    draft_reply,
    error
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

EXPECTED_COLUMNS = (
    'id',
    'created_at',
    'client_id',
    'channel',
    'text',
    'category',
    'confidence',
    'escalate',
    'draft_reply',
    'error',
)


def load_schema_sql() -> str:
    """Читает DDL из каталога data/. Без файла схему применить нельзя."""

    try:
        return SCHEMA_PATH.read_text(encoding='utf-8')
    except OSError as exc:
        raise FileNotFoundError(
            f'Не найден файл схемы {SCHEMA_PATH}',
        ) from exc


def utc_now_iso() -> str:
    """Текущий момент в UTC в формате ISO-8601."""

    return datetime.now(timezone.utc).isoformat()


def _connect(database_path: str) -> sqlite3.Connection:
    """Открывает файл базы. DELETE-журнал: все строки лежат в .db, DBeaver их видит."""

    connection = sqlite3.connect(database_path)
    connection.execute(f'PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}')
    # WAL прячет свежие строки в .db-wal; DBeaver часто показывает пустую таблицу.
    try:
        connection.execute('PRAGMA journal_mode = DELETE')
    except sqlite3.OperationalError:
        # Файл занят DBeaver или сервером: запись всё равно идёт в существующую базу.
        pass
    return connection


def init_database(database_path: str) -> None:
    """Создаёт каталог, файл SQLite и таблицу tickets по data/schema.sql."""

    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    schema_sql = load_schema_sql()
    connection = _connect(str(path))
    try:
        connection.executescript(schema_sql)
        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        raise
    finally:
        connection.close()


def save_ticket(
    database_path: str,
    request: TriageRequest,
    result: TriageResponse | None,
    created_at: str,
    error: str | None = None,
) -> None:
    """Пишет одну строку истории. Ошибку sqlite обрабатывает вызывающий код."""

    category: str | None = None
    confidence: str | None = None
    escalate: int | None = None
    draft_reply: str | None = None
    if result is not None:
        category = result.category.value
        confidence = result.confidence.value
        escalate = int(result.escalate)
        draft_reply = result.draft_reply
    connection = _connect(database_path)
    try:
        connection.execute(
            INSERT_TICKET_SQL,
            (
                created_at,
                request.client_id,
                request.channel.value,
                request.text,
                category,
                confidence,
                escalate,
                draft_reply,
                error,
            ),
        )
        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == '__main__':
    from app.config import load_settings

    settings = load_settings()
    init_database(settings.database_path)
    print(f'База готова: {settings.database_path}')
