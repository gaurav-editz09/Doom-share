import sys

from core.paths import get_bundle_dir, get_config_path, get_user_data_dir


def test_development_uses_project_directory_for_resources_and_user_data():
    project_dir = get_bundle_dir()
    assert project_dir.name == "Doom-Main"
    assert get_user_data_dir() == project_dir
    assert get_config_path() == project_dir / "config" / "api_keys.json"


def test_frozen_windows_build_uses_local_app_data_for_user_files(tmp_path, monkeypatch):
    bundle_dir = tmp_path / "bundle"
    local_app_data = tmp_path / "local"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle_dir), raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))

    assert get_bundle_dir() == bundle_dir
    assert get_user_data_dir() == local_app_data / "Doom"
    assert get_config_path() == local_app_data / "Doom" / "config" / "api_keys.json"


def test_frozen_build_without_local_app_data_uses_home(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    assert get_user_data_dir() == tmp_path / ".local" / "share" / "Doom"
