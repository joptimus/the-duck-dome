import pytest
from fastapi.testclient import TestClient
from duckdome.app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(data_dir=tmp_path)


@pytest.fixture
def client(app):
    return TestClient(app)
