"""CH341 adapter implementation based on the WCH vendor DLL (CH341PAR/CH341DLL).

The adapter talks to a CH341 USB-I2C bridge through the official WCH dynamic
library using ctypes. The DLL is searched in the following order:

1. An explicit path passed to the constructor (``dll_path=``).
2. The ``I2CTOOL_CH341_DLL`` environment variable.
3. Common DLL file names next to the process executable / current directory.

When the DLL or the hardware is absent, :meth:`open` simply returns ``False``
so callers can fall back to another adapter.
"""

from __future__ import annotations

import ctypes
import os
import sys
from typing import List, Optional

from i2ctool_core.interfaces import I2CAdapter, I2CError

# ---------------------------------------------------------------------------
# WCH CH341 library constants (see CH341PAR/CH341DLL documentation)
# ---------------------------------------------------------------------------
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

# CH341SetStream I2C speed modes
_SPEED_MODES = {
    20: 0x00000000,   # low speed, ~20 kHz
    100: 0x00000001,  # standard speed, ~100 kHz
    400: 0x00000002,  # fast speed, ~400 kHz
    750: 0x00000003,  # high speed, ~750 kHz
}

# Transaction chunk limits to stay inside the CH341 internal buffer sizes.
_MAX_WRITE_CHUNK = 512
_MAX_READ_CHUNK = 1024

_DLL_CANDIDATES = ("CH341DLL.dll", "CH341DLL.DLL", "CH341PAR.dll", "ch341.dll")
_DLL_ENV_VAR = "I2CTOOL_CH341_DLL"


def _load_dll(path: Optional[str] = None) -> Optional[ctypes.WinDLL]:
    """Try to load the CH341 vendor DLL, returning None when unavailable."""
    if sys.platform != "win32":
        return None

    candidates: List[str] = []
    if path:
        candidates.append(path)
    env_path = os.environ.get(_DLL_ENV_VAR)
    if env_path:
        candidates.append(env_path)
    candidates.extend(_DLL_CANDIDATES)

    loader = ctypes.WinDLL  # WCH API uses __stdcall on Windows
    for name in candidates:
        try:
            return loader(name)
        except OSError:
            continue
    return None


class CH341Adapter(I2CAdapter):
    """CH341 USB-I2C adapter backed by the WCH vendor DLL."""

    def __init__(self, device_index: int = 0, dll_path: Optional[str] = None):
        self._device_index = device_index
        self._dll_path = dll_path
        self._dll: Optional[ctypes.WinDLL] = None
        self._connected = False
        self._speed_khz = 100

    # ------------------------------------------------------------------
    # Availability helpers
    # ------------------------------------------------------------------
    @classmethod
    def is_available(cls, dll_path: Optional[str] = None) -> bool:
        """Return True when the vendor DLL can be loaded on this machine."""
        return _load_dll(dll_path) is not None

    # ------------------------------------------------------------------
    # Adapter lifecycle
    # ------------------------------------------------------------------
    def open(self) -> bool:
        """Open connection to the CH341 device."""
        if self._connected:
            return True

        dll = _load_dll(self._dll_path)
        if dll is None:
            return False

        try:
            handle = dll.CH341OpenDevice(ctypes.c_ulong(self._device_index))
        except (OSError, AttributeError):
            return False

        if handle == _INVALID_HANDLE_VALUE or handle is None:
            return False

        self._dll = dll
        self._connected = True
        # Apply the currently configured stream speed.
        try:
            self.set_speed(self._speed_khz)
        except I2CError:
            # Speed setup failing should not prevent basic usage.
            pass
        return True

    def close(self) -> None:
        """Close connection to the CH341 device."""
        if self._connected and self._dll is not None:
            try:
                self._dll.CH341CloseDevice(ctypes.c_ulong(self._device_index))
            except (OSError, AttributeError):
                pass
        self._dll = None
        self._connected = False

    def is_connected(self) -> bool:
        """Check if the CH341 device is connected."""
        return self._connected

    # ------------------------------------------------------------------
    # I2CAdapter implementation
    # ------------------------------------------------------------------
    def scan(self) -> List[int]:
        """Scan the I2C bus by probing every valid 7-bit address."""
        self._ensure_ready()
        found: List[int] = []
        for addr in range(0x08, 0x78):
            if self._probe_address(addr):
                found.append(addr)
        return found

    def read(self, device_addr: int, mem_addr: int, length: int,
             addr_width: int = 1) -> bytes:
        """Read from an EEPROM-style device via CH341StreamI2C."""
        self._ensure_ready()
        self._validate_addr_width(addr_width)
        if length < 0:
            raise I2CError("Negative read length is invalid")

        result = bytearray()
        remaining = length
        current = mem_addr
        while remaining > 0:
            chunk = min(remaining, _MAX_READ_CHUNK)
            header = self._build_address_header(device_addr, current, addr_width)
            read_buf = (ctypes.c_ubyte * chunk)()
            ok = self._dll.CH341StreamI2C(
                ctypes.c_ulong(self._device_index),
                ctypes.c_ulong(len(header)),
                header,
                ctypes.c_ulong(chunk),
                read_buf,
            )
            if not ok:
                raise I2CError(
                    f"CH341 read failed at device 0x{device_addr:02X} "
                    f"address 0x{current:X}"
                )
            result.extend(bytes(read_buf))
            current += chunk
            remaining -= chunk
        return bytes(result)

    def write(self, device_addr: int, mem_addr: int, data: bytes,
              addr_width: int = 1) -> None:
        """Write to an EEPROM-style device via CH341StreamI2C."""
        self._ensure_ready()
        self._validate_addr_width(addr_width)

        offset = 0
        current = mem_addr
        while offset < len(data):
            chunk = data[offset:offset + _MAX_WRITE_CHUNK]
            header = self._build_address_header(device_addr, current, addr_width)
            frame = bytes(header) + bytes(chunk)
            buf = (ctypes.c_ubyte * len(frame)).from_buffer_copy(frame)
            ok = self._dll.CH341StreamI2C(
                ctypes.c_ulong(self._device_index),
                ctypes.c_ulong(len(frame)),
                buf,
                ctypes.c_ulong(0),
                None,
            )
            if not ok:
                raise I2CError(
                    f"CH341 write failed at device 0x{device_addr:02X} "
                    f"address 0x{current:X}"
                )
            offset += len(chunk)
            current += len(chunk)

    def set_speed(self, khz: int) -> None:
        """Set the CH341 I2C stream speed."""
        if khz not in _SPEED_MODES:
            supported = ", ".join(str(k) for k in sorted(_SPEED_MODES))
            raise I2CError(f"Unsupported speed for CH341: {khz} kHz (supported: {supported})")
        self._speed_khz = khz
        if self._connected and self._dll is not None:
            ok = self._dll.CH341SetStream(
                ctypes.c_ulong(self._device_index),
                ctypes.c_ulong(_SPEED_MODES[khz]),
            )
            if not ok:
                raise I2CError(f"CH341SetStream failed for {khz} kHz")

    def supports_eeprom_page_write(self) -> bool:
        """CH341 supports page write."""
        return True

    def get_info(self) -> str:
        """Get adapter information."""
        state = "open" if self._connected else "closed"
        return f"CH341 Adapter #{self._device_index} ({state}, {self._speed_khz} kHz)"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_ready(self) -> None:
        if not self._connected or self._dll is None:
            raise I2CError("CH341 adapter not connected")

    @staticmethod
    def _validate_addr_width(addr_width: int) -> None:
        if addr_width not in (1, 2):
            raise I2CError(f"Unsupported address width: {addr_width}")

    @staticmethod
    def _build_address_header(device_addr: int, mem_addr: int,
                              addr_width: int) -> bytes:
        """Build the write header: 7-bit address (write mode) + memory address."""
        if not 0 <= device_addr <= 0x7F:
            raise I2CError(f"Invalid 7-bit device address: 0x{device_addr:02X}")
        if mem_addr < 0:
            raise I2CError("Negative memory address is invalid")
        if mem_addr >= (1 << (8 * addr_width)):
            raise I2CError(
                f"Memory address 0x{mem_addr:X} exceeds {addr_width}-byte address space"
            )
        header = bytearray([device_addr << 1])
        header.extend(mem_addr.to_bytes(addr_width, "big"))
        return bytes(header)

    def _probe_address(self, addr: int) -> bool:
        """Probe one 7-bit address: write the address byte, then read 1 byte."""
        header = (ctypes.c_ubyte * 1)(addr << 1)
        read_buf = (ctypes.c_ubyte * 1)()
        try:
            ok = self._dll.CH341StreamI2C(
                ctypes.c_ulong(self._device_index),
                ctypes.c_ulong(1),
                header,
                ctypes.c_ulong(1),
                read_buf,
            )
        except OSError:
            return False
        return bool(ok)


__all__ = ["CH341Adapter"]
