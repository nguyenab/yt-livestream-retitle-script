from app.state import load_state, save_state


def test_load_missing_returns_empty(tmp_path):
    assert load_state(str(tmp_path / "nope.json")) == {}


def test_save_then_load_roundtrips(tmp_path):
    p = str(tmp_path / "state.json")
    save_state({"last_run": "2026-05-10T18:00:00Z", "changed": 3}, p)
    assert load_state(p) == {"last_run": "2026-05-10T18:00:00Z", "changed": 3}


def test_load_corrupt_returns_empty(tmp_path):
    p = tmp_path / "state.json"
    p.write_text("{not valid json")
    assert load_state(str(p)) == {}
