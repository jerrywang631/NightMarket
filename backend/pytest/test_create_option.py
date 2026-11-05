"""
POST /api/admin/options/<node_id> must refuse options for a node that does not
exist (Unity's runtime generation used the made-up node "quiz-generated") and
option_ids that already exist (it re-inserted real options as duplicates).
Runs against the test DB (mode 1) with ML models skipped.
"""

import pytest

from main import App


@pytest.fixture(scope="module")
def app():
    app = App(mode=1, skip_models=True)
    app.run()  # builds the Flask app and routes; does not start the server
    return app


@pytest.fixture
def client(app):
    return app.app.test_client()


def post(client, node_id, option_id):
    return client.post(f"/api/admin/options/{node_id}",
                       json={"option_id": option_id, "option_text": "test", "feedback_type": "quiz"})


def test_unknown_node_rejected(client, app):
    r = post(client, "quiz-generated", "quiz_opt_test0001")
    assert r.status_code == 404
    assert app.dialogue_manager.get_option("quiz_opt_test0001") is None


def test_duplicate_option_rejected(client, app):
    existing = app.dialogue_manager.db.get_data("SELECT node_id, option_id FROM options LIMIT 1")[0]
    count = lambda: app.dialogue_manager.db.get_data(
        "SELECT count(*) FROM options WHERE option_id = ?", (existing[1],))[0][0]
    before = count()
    assert post(client, existing[0], existing[1]).status_code == 409
    assert count() == before


def test_new_option_on_existing_node_created(client, app):
    node_id = app.dialogue_manager.db.get_data("SELECT node_id FROM dialogue_nodes LIMIT 1")[0][0]
    try:
        assert post(client, node_id, "o_pytest_new_001").status_code == 201
        assert app.dialogue_manager.get_option("o_pytest_new_001")["node_id"] == node_id
    finally:
        app.dialogue_manager.delete_option("o_pytest_new_001")
