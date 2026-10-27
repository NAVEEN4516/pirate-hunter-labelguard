import json
from pathlib import Path
import pytest
from labelguard import store
from labelguard.config import settings
from labelguard.corpus import get_corpus


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(settings(), "data_dir", tmp_path)
    monkeypatch.setattr(settings(), "cache_enabled", False)
    store.init_db()


@pytest.fixture
def payload():
    return json.loads(Path("examples/valid-protein.json").read_text())


@pytest.fixture
def corpus():
    return get_corpus()
