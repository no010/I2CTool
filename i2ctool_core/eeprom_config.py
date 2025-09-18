"""
EEPROM configuration management.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class EEPROMConfig:
    """EEPROM chip configuration."""
    id: str
    name: str
    size_bytes: int
    address_width: int  # 1 or 2 bytes
    page_size: int
    write_cycle_ms: int
    notes: str = ""


class EEPROMManager:
    """Manages EEPROM configurations loaded from JSON files."""
    
    def __init__(self, config_dir: str = "configs/eeprom"):
        self.config_dir = Path(config_dir)
        self._configs: Dict[str, EEPROMConfig] = {}
        self.load_configs()
    
    def load_configs(self) -> None:
        """Load all EEPROM configurations from JSON files."""
        self._configs.clear()
        
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)
            # Create a default config
            self._create_default_configs()
        
        for config_file in self.config_dir.glob("*.json"):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    config = EEPROMConfig(**data)
                    self._configs[config.id] = config
            except Exception as e:
                print(f"Error loading config {config_file}: {e}")
    
    def _create_default_configs(self) -> None:
        """Create default EEPROM configurations."""
        default_configs = [
            {
                "id": "24c02",
                "name": "24C02 (2Kbit)",
                "size_bytes": 256,
                "address_width": 1,
                "page_size": 8,
                "write_cycle_ms": 5,
                "notes": "Standard 2Kbit I2C EEPROM"
            },
            {
                "id": "24c08",
                "name": "24C08 (8Kbit)",
                "size_bytes": 1024,
                "address_width": 1,
                "page_size": 16,
                "write_cycle_ms": 5,
                "notes": "Standard 8Kbit I2C EEPROM"
            },
            {
                "id": "24c256",
                "name": "24C256 (256Kbit)",
                "size_bytes": 32768,
                "address_width": 2,
                "page_size": 64,
                "write_cycle_ms": 5,
                "notes": "Standard 256Kbit I2C EEPROM"
            }
        ]
        
        for config_data in default_configs:
            config_file = self.config_dir / f"{config_data['id']}.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2)
    
    def get_config(self, eeprom_id: str) -> Optional[EEPROMConfig]:
        """Get EEPROM configuration by ID."""
        return self._configs.get(eeprom_id)
    
    def get_all_configs(self) -> Dict[str, EEPROMConfig]:
        """Get all loaded EEPROM configurations."""
        return self._configs.copy()
    
    def get_config_list(self) -> List[EEPROMConfig]:
        """Get list of all configurations."""
        return list(self._configs.values())