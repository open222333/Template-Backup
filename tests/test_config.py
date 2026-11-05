import os

import src


def test_base_dir_points_to_project_root():
    assert os.path.isdir(os.path.join(src.BASE_DIR, 'conf'))


def test_env_overrides_config(monkeypatch):
    monkeypatch.setenv('SOME_KEY', 'from-env')
    assert src.get_setting('ANY', 'SOME_KEY', 'fallback') == 'from-env'


def test_fallback_when_missing(monkeypatch):
    monkeypatch.delenv('MISSING_KEY', raising=False)
    assert src.get_setting('ANY', 'MISSING_KEY', 'fallback') == 'fallback'


def test_typed_getters(monkeypatch):
    monkeypatch.setenv('INT_KEY', '3')
    monkeypatch.setenv('BOOL_KEY', 'true')
    assert src.get_int('ANY', 'INT_KEY', 0) == 3
    assert src.get_bool('ANY', 'BOOL_KEY') is True
