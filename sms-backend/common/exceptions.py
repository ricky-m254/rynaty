"""
Domain exceptions.
All domain errors inherit from DomainError so callers can catch the right level.
"""


class DomainError(Exception):
    """Base for all domain-layer errors."""


class DomainValidationError(DomainError):
    """Raised when an entity or value-object fails its own validation rules."""


class PersonNotFoundError(DomainError):
    """Raised when a lookup finds no matching PersonRegistry entry."""


class DuplicateEventError(DomainError):
    """Raised when a scan event is a duplicate within the dedup window."""


class ExternalServiceError(DomainError):
    """Raised by infrastructure adapters when an external API fails."""
