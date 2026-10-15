-- История запросов /triage и результатов модели.
-- Файл для DBeaver: Database → SQL Editor → выполнить скрипт.
-- Файл базы: data/triage.db (каталог data/ остаётся точкой контроля).

CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    client_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    text TEXT NOT NULL,
    category TEXT,
    confidence TEXT,
    escalate INTEGER,
    draft_reply TEXT,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets (created_at);
CREATE INDEX IF NOT EXISTS idx_tickets_client_id ON tickets (client_id);
