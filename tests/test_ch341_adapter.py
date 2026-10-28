"""Tests for the CH341 adapter logic without real hardware.

A stub DLL object records calls so frame construction and error paths can be
verified deterministically.
"""

import pytest

from adapters.ch341_adapter import CH341Adapter, _load_dll
from i2ctool_core.interfaces import I2CError


class StubDLL:
    """Minimal stand-in for the WCH CH341 vendor DLL."""

    def __init__(self, stream_result=True):
        self.stream_result = stream_result
        self.stream_calls = []
        self.stream_mode_calls = []

    def CH341StreamI2C(self, index, write_len, write_buf, read_len, read_buf):
        frame = bytes(write_buf[:write_len.value]) if write_buf else b""
        self.stream_calls.append(
            {"index": index.value, "frame": frame, "read_len": read_len.value}
        )
        if self.stream_result and read_buf is not None:
            for i in range(read_len.value):
                read_buf[i] = 0x5A
        return self.stream_result

    def CH341SetStream(self, index, mode):
        self.stream_mode_calls.append(mode.value)
        return True

    def CH341CloseDevice(self, index):
        return True


@pytest.fixture
def stubbed_adapter():
    """Connected adapter wired to a stub DLL."""
    adapter = CH341Adapter(device_index=0)
    adapter._connected = True
    adapter._dll = StubDLL()
    return adapter


class TestAddressHeader:
    def test_one_byte_address(self):
        header = CH341Adapter._build_address_header(0x50, 0x0A, 1)
        assert header == bytes([0xA0, 0x0A])

    def test_two_byte_address_is_big_endian(self):
        header = CH341Adapter._build_address_header(0x50, 0x1234, 2)
        assert header == bytes([0xA0, 0x12, 0x34])

    def test_invalid_device_address_raises(self):
        with pytest.raises(I2CError):
            CH341Adapter._build_address_header(0x80, 0, 1)

    def test_negative_memory_address_raises(self):
        with pytest.raises(I2CError):
            CH341Adapter._build_address_header(0x50, -1, 1)

    def test_memory_address_exceeding_address_space_raises(self):
        with pytest.raises(I2CError, match="address space"):
            CH341Adapter._build_address_header(0x50, 256, 1)


class TestDisconnectedBehaviour:
    def test_operations_raise_when_not_connected(self):
        adapter = CH341Adapter()
        with pytest.raises(I2CError):
            adapter.scan()
        with pytest.raises(I2CError):
            adapter.read(0x50, 0, 1)
        with pytest.raises(I2CError):
            adapter.write(0x50, 0, b"\x00")

    def test_set_speed_stores_value_when_closed(self):
        adapter = CH341Adapter()
        adapter.set_speed(400)
        assert "400 kHz" in adapter.get_info()

    def test_unsupported_speed_raises(self):
        adapter = CH341Adapter()
        with pytest.raises(I2CError):
            adapter.set_speed(123)

    def test_open_without_dll_returns_false(self):
        adapter = CH341Adapter(dll_path="definitely-missing-ch341.dll")
        assert adapter.open() is False
        assert adapter.is_connected() is False


class TestStubbedStreamIO:
    def test_read_frame_and_result(self, stubbed_adapter):
        data = stubbed_adapter.read(0x50, 0x0100, 4, addr_width=2)
        calls = stubbed_adapter._dll.stream_calls
        assert len(calls) == 1
        assert calls[0]["frame"] == bytes([0xA0, 0x01, 0x00])
        assert calls[0]["read_len"] == 4
        assert data == b"\x5A" * 4

    def test_large_read_is_chunked(self, stubbed_adapter):
        stubbed_adapter.read(0x50, 0, 1500, addr_width=2)
        calls = stubbed_adapter._dll.stream_calls
        assert [c["read_len"] for c in calls] == [1024, 476]
        # Second chunk must re-address at offset 1024.
        assert calls[1]["frame"] == bytes([0xA0, 0x04, 0x00])

    def test_write_frame(self, stubbed_adapter):
        stubbed_adapter.write(0x50, 0x10, b"\x11\x22", addr_width=1)
        calls = stubbed_adapter._dll.stream_calls
        assert len(calls) == 1
        assert calls[0]["frame"] == bytes([0xA0, 0x10, 0x11, 0x22])
        assert calls[0]["read_len"] == 0

    def test_large_write_is_chunked(self, stubbed_adapter):
        payload = bytes(range(256)) * 3  # 768 bytes -> 512 + 256
        stubbed_adapter.write(0x50, 0, payload, addr_width=2)
        calls = stubbed_adapter._dll.stream_calls
        assert len(calls) == 2
        assert len(calls[0]["frame"]) == 3 + 512
        assert len(calls[1]["frame"]) == 3 + 256

    def test_failed_stream_raises(self, stubbed_adapter):
        stubbed_adapter._dll.stream_result = False
        with pytest.raises(I2CError):
            stubbed_adapter.read(0x50, 0, 4)
        with pytest.raises(I2CError):
            stubbed_adapter.write(0x50, 0, b"\x00")

    def test_scan_detects_ack_only_addresses(self, stubbed_adapter):
        devices = stubbed_adapter.scan()
        # Stub always ACKs, so every valid 7-bit address is reported.
        assert devices == list(range(0x08, 0x78))

    def test_scan_with_nak_stub_finds_nothing(self, stubbed_adapter):
        stubbed_adapter._dll.stream_result = False
        assert stubbed_adapter.scan() == []

    def test_invalid_addr_width_raises(self, stubbed_adapter):
        with pytest.raises(I2CError):
            stubbed_adapter.read(0x50, 0, 1, addr_width=3)
        with pytest.raises(I2CError):
            stubbed_adapter.write(0x50, 0, b"\x00", addr_width=0)


class TestAvailability:
    def test_load_dll_missing_path_returns_none(self):
        assert _load_dll("definitely-missing-ch341.dll") is None

    def test_is_available_returns_bool(self):
        assert isinstance(CH341Adapter.is_available(), bool)

    def test_supports_page_write(self):
        assert CH341Adapter().supports_eeprom_page_write() is True
