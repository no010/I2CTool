"""Tests for EEPROMOperations built on top of the simulation adapter."""

import pytest

from i2ctool_core.interfaces import I2CError


class TestReadOperations:
    def test_read_random_returns_requested_length(self, ops, device_addr):
        data = ops.read_random(device_addr, 0x100, 32)
        assert isinstance(data, bytes)
        assert len(data) == 32

    def test_read_random_is_deterministic(self, ops, device_addr):
        first = ops.read_random(device_addr, 0x200, 64)
        second = ops.read_random(device_addr, 0x200, 64)
        assert first == second

    def test_read_sequential_matches_random_read(self, ops, device_addr):
        seq = ops.read_sequential(device_addr, 0x300, 48)
        rnd = ops.read_random(device_addr, 0x300, 48)
        assert seq == rnd

    def test_read_full_covers_entire_chip(self, ops, device_addr, config_24c256):
        dump = ops.read_full(device_addr)
        assert len(dump) == config_24c256.size_bytes


class TestWriteByte:
    def test_write_byte_is_readable(self, ops, device_addr):
        ops.write_byte(device_addr, 0x010, 0xA5)
        assert ops.read_random(device_addr, 0x010, 1) == b"\xA5"

    def test_write_byte_overwrites_previous_value(self, ops, device_addr):
        ops.write_byte(device_addr, 0x020, 0x11)
        ops.write_byte(device_addr, 0x020, 0x22)
        assert ops.read_random(device_addr, 0x020, 1) == b"\x22"


class TestWritePage:
    def test_write_page_within_page(self, ops, device_addr):
        payload = bytes(range(64))
        ops.write_page(device_addr, 0x000, payload)  # page-aligned
        assert ops.read_random(device_addr, 0x000, 64) == payload

    def test_write_page_rejects_oversized_data(self, ops, device_addr, config_24c256):
        with pytest.raises(ValueError, match="exceeds page size"):
            ops.write_page(device_addr, 0x000, bytes(config_24c256.page_size + 1))

    def test_write_page_rejects_page_boundary_crossing(self, ops, device_addr):
        # 8 bytes starting at offset 60 inside a 64-byte page cross the boundary.
        with pytest.raises(ValueError, match="page boundary"):
            ops.write_page(device_addr, 60, bytes(8))


class TestWriteBuffer:
    def test_write_buffer_spanning_multiple_pages(self, ops, device_addr):
        # 150 bytes starting at 60 spans parts of four 64-byte pages.
        payload = bytes((i * 7 + 3) % 256 for i in range(150))
        ops.write_buffer(device_addr, 60, payload)
        assert ops.read_random(device_addr, 60, len(payload)) == payload

    def test_write_buffer_page_aligned(self, ops, device_addr):
        payload = bytes(range(256)) * 2  # exactly 8 pages
        ops.write_buffer(device_addr, 0x400, payload)
        assert ops.read_random(device_addr, 0x400, len(payload)) == payload

    def test_write_buffer_single_byte(self, ops, device_addr):
        ops.write_buffer(device_addr, 0x7FF, b"\x42")
        assert ops.read_random(device_addr, 0x7FF, 1) == b"\x42"

    def test_write_buffer_does_not_touch_neighbouring_bytes(self, ops, device_addr):
        before = ops.read_random(device_addr, 0x100 - 1, 1)
        ops.write_buffer(device_addr, 0x100, b"\xEE\xEE")
        after = ops.read_random(device_addr, 0x100 - 1, 1)
        assert before == after


class TestEraseChip:
    def test_erase_chip_fills_with_0xff(self, ops, device_addr, config_24c256):
        ops.write_buffer(device_addr, 0, b"\x00" * 256)
        ops.erase_chip(device_addr)
        dump = ops.read_full(device_addr)
        assert dump == b"\xFF" * config_24c256.size_bytes

    def test_erase_chip_custom_fill_value(self, ops, device_addr, config_24c256):
        ops.erase_chip(device_addr, fill_value=0x00)
        assert ops.read_full(device_addr) == b"\x00" * config_24c256.size_bytes


class TestVerifyWrite:
    def test_verify_write_success(self, ops, device_addr):
        payload = b"verify-me"
        ops.write_buffer(device_addr, 0x500, payload)
        assert ops.verify_write(device_addr, 0x500, payload) is True

    def test_verify_write_detects_mismatch(self, ops, device_addr):
        ops.write_buffer(device_addr, 0x500, b"aaaa")
        assert ops.verify_write(device_addr, 0x500, b"bbbb") is False

    def test_verify_write_returns_false_on_i2c_error(self, ops):
        # Address 0x77 does not exist on the simulated bus.
        assert ops.verify_write(0x77, 0x00, b"x") is False


class TestErrorPropagation:
    def test_read_from_absent_device_raises(self, ops):
        with pytest.raises(I2CError):
            ops.read_random(0x77, 0, 8)

    def test_write_beyond_chip_size_raises(self, ops, device_addr, config_24c256):
        with pytest.raises(I2CError):
            ops.write_buffer(
                device_addr, config_24c256.size_bytes - 2, b"\x00\x00\x00\x00"
            )
