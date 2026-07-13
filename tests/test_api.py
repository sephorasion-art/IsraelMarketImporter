import pytest
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_home_status_code():
    resp = client.get("/")
    assert resp.status_code == 200
