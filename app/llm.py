"""Вызов OpenAI Chat Completions. Разбор JSON живёт отдельно."""

import socket
from collections.abc import Callable
from typing import Protocol

import httpx
from openai import APITimeoutError, OpenAI, OpenAIError

SYSTEM_PROMPT = (
    'Ты — ассистент службы поддержки. Твоя задача: классифицировать обращение '
    'и написать черновик ответа.\n'
    'Правила:\n'
    '- опирайся только на текст обращения, не выдумывай факты, сроки, суммы и обещания;\n'
    '- если данных мало для уверенной категории или ответа — confidence=low и escalate=true;\n'
    '- category: billing | support | complaint | other;\n'
    '- confidence: high | medium | low;\n'
    '- draft_reply: 1–6 предложений на языке обращения;\n'
    '- верни только JSON с ключами category, draft_reply, confidence, escalate.'
)

TEMPERATURE = 0.2
LLM_TIMEOUT_SECONDS = 20
SDK_MAX_RETRIES = 0
HTTP_TIMEOUT = httpx.Timeout(LLM_TIMEOUT_SECONDS)

REASON_EMPTY_API_KEY = 'empty_api_key'
REASON_TIMEOUT = 'timeout'
REASON_SDK_ERROR = 'sdk_error'
REASON_EMPTY_RESPONSE = 'empty_response'


class LlmError(Exception):
    """Сбой вызова модели. В reason только краткий код, без текста ответа."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class LlmClient(Protocol):
    """Контракт вызова: текст и канал на входе, сырой JSON на выходе."""

    def complete(self, text: str, channel: str) -> str:
        """Возвращает сырой JSON модели."""

        ...


def build_user_message(text: str, channel: str) -> str:
    """Собирает пользовательское сообщение только из текста и канала."""

    return f'text: {text}\nchannel: {channel}'


def _default_client_factory(api_key: str, timeout: httpx.Timeout, max_retries: int) -> OpenAI:
    """Создаёт SDK-клиент. Ключ приходит из окружения, не из кода."""

    return OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)


class OpenAIChatClient:
    """Один запрос Chat Completions с JSON-ответом и таймаутом 20 секунд."""

    def __init__(
        self,
        api_key: str,
        model: str,
        client_factory: Callable[..., object] | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._client_factory = client_factory or _default_client_factory

    def complete(self, text: str, channel: str) -> str:
        """Возвращает текст ответа модели либо бросает LlmError с краткой причиной."""

        if not self._api_key.strip():
            raise LlmError(REASON_EMPTY_API_KEY)
        # Ограничивает и DNS, и сам HTTP-запрос двадцатью секундами.
        previous_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(LLM_TIMEOUT_SECONDS)
        try:
            client = self._client_factory(
                api_key=self._api_key,
                timeout=HTTP_TIMEOUT,
                max_retries=SDK_MAX_RETRIES,
            )
            response = client.chat.completions.create(
                model=self._model,
                temperature=TEMPERATURE,
                timeout=HTTP_TIMEOUT,
                response_format={'type': 'json_object'},
                messages=[
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': build_user_message(text, channel)},
                ],
            )
        except APITimeoutError as exc:
            raise LlmError(REASON_TIMEOUT) from exc
        except OpenAIError as exc:
            raise LlmError(REASON_SDK_ERROR) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise LlmError(REASON_TIMEOUT) from exc
        finally:
            socket.setdefaulttimeout(previous_timeout)
        return _read_content(response)


def _read_content(response: object) -> str:
    """Достаёт текст ответа. Пустое тело считается поломкой, не успехом."""

    choices = getattr(response, 'choices', None)
    if not choices:
        raise LlmError(REASON_EMPTY_RESPONSE)
    message = getattr(choices[0], 'message', None)
    content = getattr(message, 'content', None)
    if not isinstance(content, str) or not content.strip():
        raise LlmError(REASON_EMPTY_RESPONSE)
    return content
