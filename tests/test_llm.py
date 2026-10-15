"""Параметры вызова модели без реального запроса в сеть."""

import pytest

from app.llm import (
    LLM_TIMEOUT_SECONDS,
    TEMPERATURE,
    LlmError,
    OpenAIChatClient,
    build_user_message,
)


def test_user_message_contains_text_and_channel():
    message = build_user_message('Где счёт?', 'email')
    assert 'Где счёт?' in message
    assert 'email' in message


def test_empty_key_does_not_open_sdk():
    def factory(**kwargs):
        del kwargs
        raise AssertionError('SDK не должен создаваться без ключа')

    client = OpenAIChatClient('  ', 'gpt-4o-mini', client_factory=factory)
    with pytest.raises(LlmError) as caught:
        client.complete('привет', 'chat')
    assert caught.value.reason == 'empty_api_key'


def test_call_uses_temperature_json_format_and_timeout():
    captured: dict[str, object] = {}

    class Completions:
        def create(self, **kwargs):
            captured['create'] = kwargs
            message = type('Message', (), {'content': '{"ok":true}'})()
            choice = type('Choice', (), {'message': message})()
            return type('Response', (), {'choices': [choice]})()

    class Chat:
        completions = Completions()

    class Sdk:
        chat = Chat()

    def factory(**kwargs):
        captured['factory'] = kwargs
        return Sdk()

    client = OpenAIChatClient('test-key', 'gpt-4o-mini', client_factory=factory)
    raw = client.complete('Где счёт?', 'form')
    factory_kwargs = captured['factory']
    create_kwargs = captured['create']
    assert isinstance(factory_kwargs, dict)
    assert isinstance(create_kwargs, dict)
    assert factory_kwargs['timeout'].read == LLM_TIMEOUT_SECONDS
    assert factory_kwargs['max_retries'] == 0
    assert create_kwargs['temperature'] == TEMPERATURE
    assert create_kwargs['timeout'].read == LLM_TIMEOUT_SECONDS
    assert create_kwargs['response_format'] == {'type': 'json_object'}
    assert create_kwargs['model'] == 'gpt-4o-mini'
    user_message = create_kwargs['messages'][1]['content']
    assert 'Где счёт?' in user_message
    assert 'form' in user_message
    assert raw == '{"ok":true}'


def test_sdk_error_is_short_reason():
    class Completions:
        def create(self, **kwargs):
            del kwargs
            from openai import OpenAIError
            raise OpenAIError('секретный ответ модели')

    class Chat:
        completions = Completions()

    class Sdk:
        chat = Chat()

    client = OpenAIChatClient(
        'test-key',
        'gpt-4o-mini',
        client_factory=lambda **kwargs: Sdk(),
    )
    with pytest.raises(LlmError) as caught:
        client.complete('привет', 'chat')
    assert caught.value.reason == 'sdk_error'
    assert 'секретный' not in caught.value.reason
