"""Чтение настроек из окружения. Секреты в коде не хранятся."""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

ENV_OPENAI_API_KEY = 'OPENAI_API_KEY'
ENV_OPENAI_MODEL = 'OPENAI_MODEL'
ENV_RATE_LIMIT_PER_MINUTE = 'RATE_LIMIT_PER_MINUTE'
ENV_DATABASE_PATH = 'DATABASE_PATH'

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OPENAI_MODEL = 'gpt-4o-mini'
DEFAULT_RATE_LIMIT_PER_MINUTE = 5
DEFAULT_DATABASE_PATH = 'data/triage.db'


def resolve_database_path(raw: str) -> str:
    """Относительный путь всегда от корня репозитория, не от текущей папки."""

    path = Path(raw)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path.resolve())


class Settings(BaseModel):
    """Снимок настроек процесса."""

    openai_api_key: str = ''
    openai_model: str = DEFAULT_OPENAI_MODEL
    rate_limit_per_minute: int = DEFAULT_RATE_LIMIT_PER_MINUTE
    database_path: str = DEFAULT_DATABASE_PATH


def load_settings() -> Settings:
    """Читает .env и переменные окружения. Модель и база здесь не открываются."""

    load_dotenv()
    raw_limit = os.getenv(
        ENV_RATE_LIMIT_PER_MINUTE,
        str(DEFAULT_RATE_LIMIT_PER_MINUTE),
    )
    return Settings(
        openai_api_key=os.getenv(ENV_OPENAI_API_KEY, ''),
        openai_model=os.getenv(ENV_OPENAI_MODEL, DEFAULT_OPENAI_MODEL),
        rate_limit_per_minute=int(raw_limit),
        database_path=resolve_database_path(
            os.getenv(ENV_DATABASE_PATH, DEFAULT_DATABASE_PATH),
        ),
    )
