"""HTTP-сервис: лимит, вызов модели и запись в SQLite."""

import logging
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import Settings, load_settings
from app.db import init_database, save_ticket, utc_now_iso
from app.interpret import interpret_model_output, fallback_reply
from app.llm import LlmClient, LlmError, OpenAIChatClient
from app.log import log_triage_event
from app.rate_limit import (
    RATE_LIMIT_STATUS,
    RATE_LIMITED_CODE,
    RATE_LIMITED_MESSAGE,
    ClientRateLimiter,
)
from app.schemas import TriageRequest, TriageResponse

logger = logging.getLogger('triage')

STORAGE_ERROR_STATUS = 500
STORAGE_ERROR_CODE = 'storage_error'
STORAGE_ERROR_MESSAGE = 'Не удалось сохранить обращение'


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Готовит файл базы до приёма запросов."""

    init_database(application.state.settings.database_path)
    yield


def create_app(
    settings: Settings | None = None,
    llm: LlmClient | None = None,
) -> FastAPI:
    """Собирает приложение. Модель можно подменить в проверках."""

    resolved = settings or load_settings()
    _configure_logging()
    application = FastAPI(title='Triage', lifespan=lifespan)
    application.state.settings = resolved
    application.state.rate_limiter = ClientRateLimiter(resolved.rate_limit_per_minute)
    application.state.llm = llm or OpenAIChatClient(
        api_key=resolved.openai_api_key,
        model=resolved.openai_model,
    )

    @application.get('/health')
    def health() -> dict[str, str]:
        """Сообщает, что процесс запущен."""

        return {'status': 'ok'}

    @application.post('/triage', response_model=TriageResponse)
    def triage(body: TriageRequest, request: Request) -> TriageResponse | JSONResponse:
        """Ведёт обращение по фиксированному порядку шагов."""

        # 1. Валидация уже выполнена схемой TriageRequest до входа в функцию.
        database_path = request.app.state.settings.database_path
        # 2. Лимит по client_id. При отказе модель не вызывается.
        retry_after = request.app.state.rate_limiter.hit(body.client_id)
        if retry_after is not None:
            failure = _save(database_path, body, None, RATE_LIMITED_CODE)
            _record_event(body, None, None, None, True)
            if failure is not None:
                return _storage_error_response(failure)
            return JSONResponse(
                status_code=RATE_LIMIT_STATUS,
                content={
                    'code': RATE_LIMITED_CODE,
                    'message': RATE_LIMITED_MESSAGE,
                    'details': {'retry_after_seconds': retry_after},
                },
            )
        # 3. Вызов модели.
        raw, call_error = _call_model(
            request.app.state.llm,
            body.text,
            body.channel.value,
        )
        # 4. Нормализация и аварийный шаблон.
        if call_error is not None:
            interpreted = fallback_reply(call_error)
        else:
            interpreted = interpret_model_output(raw)
        # 5. Запись в tickets. Текст обращения остаётся только в базе.
        failure = _save(
            database_path,
            body,
            interpreted.response,
            interpreted.error,
        )
        had_error = interpreted.error is not None or failure is not None
        # 6. Ответ клиенту.
        _record_event(
            body,
            interpreted.response.category.value,
            interpreted.response.confidence.value,
            interpreted.response.escalate,
            had_error,
        )
        if failure is not None:
            return _storage_error_response(failure)
        return interpreted.response

    return application


def _call_model(llm: LlmClient, text: str, channel: str) -> tuple[str, str | None]:
    """Возвращает сырой JSON либо краткую причину сбоя. Текст в журнал не пишет."""

    try:
        return llm.complete(text, channel), None
    except LlmError as exc:
        return '', exc.reason


def _record_event(
    body: TriageRequest,
    category: str | None,
    confidence: str | None,
    escalate: bool | None,
    had_error: bool,
) -> None:
    """Журнал решения: идентификатор и канал есть, текст обращения нет."""

    log_triage_event(
        client_id=body.client_id,
        channel=body.channel.value,
        category=category,
        confidence=confidence,
        escalate=escalate,
        had_error=had_error,
    )


def _save(
    database_path: str,
    body: TriageRequest,
    result: TriageResponse | None,
    error: str | None,
) -> sqlite3.Error | None:
    """Пишет строку. При сбое пишет в журнал и возвращает исключение."""

    try:
        save_ticket(database_path, body, result, utc_now_iso(), error)
    except sqlite3.Error as exc:
        # Процесс остаётся живым: текст обращения в журнал не попадает.
        logger.exception('ошибка записи обращения')
        return exc
    return None


def _storage_error_response(exc: sqlite3.Error) -> JSONResponse:
    """Ответ 500 с типом сбоя, без текста обращения."""

    return JSONResponse(
        status_code=STORAGE_ERROR_STATUS,
        content={
            'code': STORAGE_ERROR_CODE,
            'message': STORAGE_ERROR_MESSAGE,
            'details': {'error_type': type(exc).__name__},
        },
    )


def _configure_logging() -> None:
    """Пишет JSON-события в тот же терминал, где запущен uvicorn."""

    logger.setLevel(logging.INFO)
    has_stream = any(
        isinstance(handler, logging.StreamHandler)
        for handler in logger.handlers
    )
    if not has_stream:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler)


app = create_app()
