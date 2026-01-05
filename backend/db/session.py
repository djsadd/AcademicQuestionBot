"""Database session factory placeholder."""
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def get_session() -> Iterator[str]:
    """Yield a fake session identifier."""
    yield "session"
