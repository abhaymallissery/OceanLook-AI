"""NEW (v6): every test gets its own empty history database, so tests never touch data/floatchat.db."""
import pytest


@pytest.fixture(autouse=True)
def _isolated_history(tmp_path, monkeypatch):
    monkeypatch.setenv("HISTORY_DB", str(tmp_path / "history.db"))
