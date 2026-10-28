"""Tests for the SimulationAdapter contract."""

import pytest

from adapters.simulation_adapter import SimulationAdapter
from i2ctool_core.interfaces import I2CError


@pytest.fixture
def closed_adapter():
    return SimulationAdapter()


class TestLifecycle:
    def test_initially_disconnected(self, closed_adapter):
        assert closed_adapter.is_connected() is False

    def test_open_close(self, closed_adapter):
        assert closed_adapter.open() is True
        assert closed_adapter.is_connected() is True
        closed_adapter.close()
        assert closed_adapter.is_connected() is False

    def test_operations_require_connection(self, closed_adapter):
        with pytest.raises(I2CError):
            closed_adapter.scan()
        with pytest.raises(I2CError):
            closed_adapter.read(0x50, 0, 1)
        with pytest.raises(I2CError):
            closed_adapter.write(0x50, 0, b"\x00")


class TestScan:
    def test_scan_returns_sorted_addresses(self, adapter):
        devices = adapter.scan()
        assert devices == sorted(devices)
        assert 0x50 in devices

    def test_scan_differs_between_buses(self):
        sim = SimulationAdapter()
        sim.open()
        sim.set_bus("/dev/i2c-0")
        bus0 = sim.scan()
        sim.set_bus("/dev/i2c-2")
        bus2 = sim.scan()
        sim.close()
        assert bus0 != bus2


class TestReadWrite:
    def test_roundtrip(self, adapter):
        adapter.write(0x50, 0x10, b"\xDE\xAD\xBE\xEF")
        assert adapter.read(0x50, 0x10, 4) == b"\xDE\xAD\xBE\xEF"

    def test_read_negative_address_raises(self, adapter):
        with pytest.raises(I2CError):
            adapter.read(0x50, -1, 1)

    def test_read_out_of_range_raises(self, adapter):
        with pytest.raises(I2CError):
            adapter.read(0x50, 32768, 1)

    def test_write_past_end_raises(self, adapter):
        with pytest.raises(I2CError):
            adapter.write(0x50, 32767, b"\x00\x00")

    def test_unknown_device_raises(self, adapter):
        with pytest.raises(I2CError):
            adapter.read(0x62, 0, 1)

    def test_bus_isolation(self):
        sim = SimulationAdapter()
        sim.open()
        sim.set_bus("/dev/i2c-1")
        sim.write(0x50, 0, b"\xAB")
        sim.set_bus("/dev/i2c-0")
        # Bus 0 has its own 1024-byte device at 0x50; value must differ.
        assert sim.read(0x50, 0, 1) != b"\xAB"
        sim.close()


class TestSpeed:
    @pytest.mark.parametrize("khz", [50, 100, 400, 1000])
    def test_supported_speeds(self, adapter, khz):
        adapter.set_speed(khz)
        assert f"{khz} kHz" in adapter.get_info()

    def test_unsupported_speed_raises(self, adapter):
        with pytest.raises(I2CError):
            adapter.set_speed(123)


class TestMisc:
    def test_supports_page_write(self, adapter):
        assert adapter.supports_eeprom_page_write() is True

    def test_invalid_bus_raises(self, adapter):
        with pytest.raises(I2CError):
            adapter.set_bus("/dev/i2c-99")
