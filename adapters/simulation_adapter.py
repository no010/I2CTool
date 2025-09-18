"""
Simulation adapter for testing without hardware.
"""

import time
from typing import Dict, List

from i2ctool_core.interfaces import I2CAdapter, I2CError


class SimulationAdapter(I2CAdapter):
    """Simulation adapter for testing UI without real hardware."""
    
    def __init__(self):
        self._connected = False
        self._speed_khz = 100
        # Simulate some EEPROM devices
        self._simulated_devices = {
            0x50: bytearray(32768),  # 24C256 at address 0x50
            0x51: bytearray(1024),   # 24C08 at address 0x51
        }
        
        # Initialize with some test data
        for addr, memory in self._simulated_devices.items():
            # Fill with a pattern for testing
            for i in range(len(memory)):
                memory[i] = (i + addr) & 0xFF
    
    def open(self) -> bool:
        """Open simulated connection."""
        self._connected = True
        return True
    
    def close(self) -> None:
        """Close simulated connection."""
        self._connected = False
    
    def is_connected(self) -> bool:
        """Check if simulated device is connected."""
        return self._connected
    
    def scan(self) -> List[int]:
        """Scan for simulated I2C devices."""
        if not self._connected:
            raise I2CError("Adapter not connected")
        
        return list(self._simulated_devices.keys())
    
    def read(self, device_addr: int, mem_addr: int, length: int, 
             addr_width: int = 1) -> bytes:
        """Read from simulated device memory."""
        if not self._connected:
            raise I2CError("Adapter not connected")
        
        if device_addr not in self._simulated_devices:
            raise I2CError(f"Device 0x{device_addr:02X} not found")
        
        memory = self._simulated_devices[device_addr]
        
        if mem_addr >= len(memory):
            raise I2CError(f"Memory address 0x{mem_addr:04X} out of range")
        
        if mem_addr + length > len(memory):
            length = len(memory) - mem_addr
        
        # Simulate read delay
        time.sleep(0.001)  # 1ms
        
        return bytes(memory[mem_addr:mem_addr + length])
    
    def write(self, device_addr: int, mem_addr: int, data: bytes,
              addr_width: int = 1) -> None:
        """Write to simulated device memory."""
        if not self._connected:
            raise I2CError("Adapter not connected")
        
        if device_addr not in self._simulated_devices:
            raise I2CError(f"Device 0x{device_addr:02X} not found")
        
        memory = self._simulated_devices[device_addr]
        
        if mem_addr >= len(memory):
            raise I2CError(f"Memory address 0x{mem_addr:04X} out of range")
        
        if mem_addr + len(data) > len(memory):
            raise I2CError("Write would exceed device memory")
        
        # Simulate write delay
        time.sleep(0.005)  # 5ms write cycle
        
        memory[mem_addr:mem_addr + len(data)] = data
    
    def set_speed(self, khz: int) -> None:
        """Set simulated I2C speed."""
        if khz not in [100, 400, 1000]:
            raise I2CError(f"Unsupported speed: {khz} kHz")
        self._speed_khz = khz
    
    def supports_eeprom_page_write(self) -> bool:
        """Simulation supports page write."""
        return True
    
    def get_info(self) -> str:
        """Get adapter information."""
        return f"Simulation Adapter ({self._speed_khz} kHz)"