"""Контракт POST /triage."""

from enum import Enum

from pydantic import BaseModel, Field, StrictStr

# Границы полей входа из контракта.
TEXT_MIN_LENGTH = 1
TEXT_MAX_LENGTH = 2000
CLIENT_ID_MIN_LENGTH = 1
CLIENT_ID_MAX_LENGTH = 64


class Channel(str, Enum):
    """Канал обращения."""

    email = 'email'
    form = 'form'
    chat = 'chat'


class Category(str, Enum):
    """Категория сортировки."""

    billing = 'billing'
    support = 'support'
    complaint = 'complaint'
    other = 'other'


class Confidence(str, Enum):
    """Уверенность классификации."""

    high = 'high'
    medium = 'medium'
    low = 'low'


class TriageRequest(BaseModel):
    """Вход POST /triage."""

    text: StrictStr = Field(min_length=TEXT_MIN_LENGTH, max_length=TEXT_MAX_LENGTH)
    channel: Channel
    client_id: StrictStr = Field(
        min_length=CLIENT_ID_MIN_LENGTH,
        max_length=CLIENT_ID_MAX_LENGTH,
    )


class TriageResponse(BaseModel):
    """Выход POST /triage."""

    category: Category
    draft_reply: str
    confidence: Confidence
    escalate: bool
