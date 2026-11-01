"""HTTP contract smoke tests for Voucher Adventure routes."""

from flask import Flask
import pytest

from voucher_adventure.repository import create_voucher_repository
from voucher_adventure.routes import register_voucher_routes
from voucher_adventure.service import VoucherAdventureService


@pytest.fixture
def voucher_http(tmp_path):
    repository = create_voucher_repository(
        sqlite_path=str(tmp_path / "voucher_http.db")
    )
    service = VoucherAdventureService(repository)
    app = Flask("voucher-http-test")
    app.config["TESTING"] = True
    register_voucher_routes(app, service)
    return app.test_client(), service


def test_create_and_restore_http_contract(voucher_http):
    client, _ = voucher_http
    response = client.post(
        "/api/v1/voucher-adventure/sessions",
        headers={"Idempotency-Key": "http-create-1"},
        json={
            "player_id": "http-player",
            "difficulty": "easy",
            "content_version": "v1",
        },
    )
    assert response.status_code == 201
    wrapper = response.get_json()
    assert wrapper["status"] == "success"
    session = wrapper["data"]
    assert len(session["vendors"]) == 5

    restored = client.get(f"/api/v1/voucher-adventure/sessions/{session['session_id']}")
    assert restored.status_code == 200
    assert restored.get_json()["data"]["session_status"] == "ACTIVE"


def test_http_requires_idempotency_key(voucher_http):
    client, _ = voucher_http
    response = client.post(
        "/api/v1/voucher-adventure/sessions",
        json={
            "player_id": "http-player",
            "difficulty": "easy",
            "content_version": "v1",
        },
    )
    assert response.status_code == 400
    assert response.get_json()["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_reveal_http_does_not_leak_answer(voucher_http):
    client, service = voucher_http
    created = client.post(
        "/api/v1/voucher-adventure/sessions",
        headers={"Idempotency-Key": "http-create-reveal"},
        json={
            "player_id": "http-reveal-player",
            "difficulty": "easy",
            "content_version": "v1",
        },
    ).get_json()["data"]
    vendor = created["vendors"][0]
    offer = service.repository.fetch_one(
        "SELECT * FROM voucher_session_offers WHERE offer_instance_id = ?",
        (vendor["offer_instance_id"],),
    )
    response = client.post(
        (
            f"/api/v1/voucher-adventure/sessions/{created['session_id']}"
            f"/offers/{vendor['offer_instance_id']}/reveal"
        ),
        headers={"Idempotency-Key": "http-reveal-1"},
        json={
            "dialogue_node_id": offer["dialogue_offer_node_id"],
            "option_id": offer["confirm_option_id"],
        },
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert "bundle_price_cents" not in data
    assert all("answer" not in question for question in data["questions"])
