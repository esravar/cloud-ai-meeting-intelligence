from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.repository import UserRepository


def test_commit_failure_rolls_back_session() -> None:
    session = Mock()
    session.commit.side_effect = SQLAlchemyError("database failure")
    repository = UserRepository(session)

    with pytest.raises(SQLAlchemyError):
        repository.create("esra@example.com", "hash")

    session.rollback.assert_called_once()
