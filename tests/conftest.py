"""Shared pytest fixtures for the i2ctool test suite."""

from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from adapters.simulation_adapter import SimulationAdapter  # noqa: E402
from i2ctool_core.eeprom_config import EEPROMConfig  # noqa: E402
from i2ctool_core.eeprom_operations import EEPROMOperations  # noqa: E402

# Bus /dev/i2c-1 hosts a 32768-byte device at 0x50, matching the 24C256 profile.
TEST_BUS = "/dev/i2c-1"
TEST_DEVICE_ADDR = 0x50


@pytest.fixture
def adapter():
    """Opened simulation adapter on a bus with a 24C256-sized device."""
    sim = SimulationAdapter()
    assert sim.open()
    sim.set_bus(TEST_BUS)
    yield sim
    sim.close()


@pytest.fixture
def config_24c256():
    """24C256 profile with zero write-cycle delay to keep tests fast."""
    return EEPROMConfig(
        id="24c256",
        name="24C256 (256Kbit)",
        size_bytes=32768,
        address_width=2,
        page_size=64,
        write_cycle_ms=0,
    )


@pytest.fixture
def ops(adapter, config_24c256):
    """EEPROM operations bound to the simulated 24C256 device."""
    return EEPROMOperations(adapter, config_24c256)


@pytest.fixture
def device_addr():
    return TEST_DEVICE_ADDR
