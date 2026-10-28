"""Tests for EEPROM configuration loading."""

import json
from pathlib import Path

from i2ctool_core.eeprom_config import EEPROMConfig, EEPROMManager

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestShippedConfigs:
    def test_repo_configs_load(self):
        manager = EEPROMManager(str(PROJECT_ROOT / "configs" / "eeprom"))
        configs = manager.get_all_configs()
        assert {"24c02", "24c08", "24c256"} <= set(configs)

    def test_24c256_profile_is_consistent(self):
        manager = EEPROMManager(str(PROJECT_ROOT / "configs" / "eeprom"))
        cfg = manager.get_config("24c256")
        assert cfg is not None
        assert cfg.size_bytes == 32768
        assert cfg.address_width == 2
        assert cfg.page_size == 64

    def test_config_list_matches_registry(self):
        manager = EEPROMManager(str(PROJECT_ROOT / "configs" / "eeprom"))
        assert {c.id for c in manager.get_config_list()} == set(manager.get_all_configs())


class TestEmptyDirectory:
    def test_missing_dir_creates_defaults(self, tmp_path):
        target = tmp_path / "fresh" / "configs"
        manager = EEPROMManager(str(target))
        assert {"24c02", "24c08", "24c256"} <= set(manager.get_all_configs())
        assert (target / "24c02.json").exists()

    def test_defaults_are_valid_json(self, tmp_path):
        target = tmp_path / "configs"
        EEPROMManager(str(target))
        for f in target.glob("*.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            EEPROMConfig(**data)  # must not raise


class TestInvalidConfigs:
    def test_unknown_fields_and_missing_fields_are_skipped(self, tmp_path):
        (tmp_path / "broken.json").write_text('{"id": "broken"}', encoding="utf-8")
        (tmp_path / "garbage.json").write_text("not json", encoding="utf-8")
        manager = EEPROMManager(str(tmp_path))
        assert manager.get_config("broken") is None
        assert manager.get_config_list() == []

    def test_get_config_unknown_id_returns_none(self, tmp_path):
        manager = EEPROMManager(str(tmp_path))
        assert manager.get_config("nope") is None
