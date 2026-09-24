from pathlib import Path
import pytest
from cem.phase import require_runtime


def pytest_sessionstart(session):
    # Runs before test collection; --collect-only is also gated.
    require_runtime(Path(__file__).resolve().parents[1])


@pytest.fixture
def root():
    return Path(__file__).resolve().parents[1]
