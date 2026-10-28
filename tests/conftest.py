import pytest

from database import db


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    return db


@pytest.fixture
def client(temp_db):
    # app.py runs init_db()/seed_db() on import, so import it only after
    # temp_db has redirected DB_PATH away from the real database.
    import app as app_module

    app_module.app.config["TESTING"] = True

    # The first import seeds the demo user into this temp DB; later tests
    # get an empty one. Start every test from the same empty state.
    conn = temp_db.get_db()
    try:
        conn.execute("DELETE FROM expenses")
        conn.execute("DELETE FROM users")
        conn.commit()
    finally:
        conn.close()
    return app_module.app.test_client()
