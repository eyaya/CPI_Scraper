"""Shared schema base: the validation exception used by every indicator schema."""


class ValidationError(Exception):
    """Raised when a parsed frame fails its indicator schema checks."""
    pass
