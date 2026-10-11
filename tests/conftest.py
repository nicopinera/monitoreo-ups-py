from pathlib import Path

import pytest

from infraestructura.database import RepositorioDB
from tests.dobles import NotificadorFalso


@pytest.fixture
def notificador() -> NotificadorFalso:
    return NotificadorFalso()


@pytest.fixture
def repo_db(tmp_path: Path) -> RepositorioDB:
    return RepositorioDB(str(tmp_path / "test_errores.db"))
