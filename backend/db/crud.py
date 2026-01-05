"""CRUD helpers placeholder."""
from .models import User


def get_user(user_id: int) -> User:
    return User(id=user_id, name="Stub")
