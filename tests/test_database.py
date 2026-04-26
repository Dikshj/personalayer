import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import tempfile
from pathlib import Path
from unittest.mock import patch
import sqlite3

@pytest.fixture(autouse=True)
def use_test_db(monkeypatch):
    import database
    test_dir = Path(tempfile.mkdtemp())
    test_db_path = test_dir / 'test.db'
    monkeypatch.setattr(database, 'DATA_DIR', test_dir)
    monkeypatch.setattr(database, 'DB_PATH', test_db_path)
    monkeypatch.setattr(database, '_connections', [])
    database.create_tables()
    yield
    # Close any remaining connections before cleanup
    database.close_all_connections()
    if test_db_path.exists():
        try:
            test_db_path.unlink()
        except PermissionError:
            pass
    try:
        import shutil
        shutil.rmtree(test_dir, ignore_errors=True)
    except:
        pass

def test_create_tables_is_idempotent():
    from database import create_tables
    create_tables()
    create_tables()

def test_insert_and_retrieve_event():
    from database import insert_event, get_events_last_n_days
    import time
    now_ms = int(time.time() * 1000)
    insert_event(
        url="https://github.com/anthropics/anthropic-sdk-python",
        title="Anthropic SDK Python",
        domain="github.com",
        time_spent_seconds=120,
        search_query=None,
        timestamp=now_ms
    )
    events = get_events_last_n_days(7)
    assert len(events) == 1
    assert events[0]['domain'] == 'github.com'
    assert events[0]['time_spent_seconds'] == 120

def test_search_query_stored():
    from database import insert_event, get_events_last_n_days
    import time
    insert_event(
        url="https://google.com/search?q=mcp+server+python",
        title="mcp server python - Google Search",
        domain="google.com",
        time_spent_seconds=10,
        search_query="mcp server python",
        timestamp=int(time.time() * 1000)
    )
    events = get_events_last_n_days(1)
    assert events[0]['search_query'] == 'mcp server python'

def test_old_events_excluded():
    from database import insert_event, get_events_last_n_days
    old_ts = int((__import__('datetime').datetime.now() - __import__('datetime').timedelta(days=10)).timestamp() * 1000)
    insert_event("https://old.com", "Old", "old.com", 10, None, old_ts)
    events = get_events_last_n_days(7)
    assert len(events) == 0

def test_save_and_get_persona():
    from database import save_persona, get_latest_persona
    persona = {"identity": {"role": "developer"}, "meta": {"event_count": 42}}
    save_persona(persona)
    result = get_latest_persona()
    assert result['identity']['role'] == 'developer'
