import os

os.environ.setdefault("XT_DISABLE_SEARCH_ENGINE", "1")

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture(autouse=True)
def _disable_startup_data_load(monkeypatch):
    monkeypatch.setattr(main, "load_data", lambda: None)


@pytest.fixture
def client():
    with TestClient(main.app) as client:
        yield client
