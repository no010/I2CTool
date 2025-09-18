"""
EEPROM operations using I2C adapters.
"""

import time
from typing import Optional

from .interfaces import I2CAdapter, I2CError
from .eeprom_config import EEPROMConfig


class EEPROMOperations:
    """High-level EEPROM operations."""
    
    def __init__(self, adapter: I2CAdapter, config: EEPROMConfig):
        self.adapter = adapter
        self.config = config
    
    def read_random(self, device_addr: int, mem_addr: int, length: int) -> bytes:
        """Random read from EEPROM.
        
        Args:
            device_addr: I2C device address (7-bit)
            mem_addr: Memory address to read from
            length: Number of bytes to read
            
        Returns:
            bytes: Read data
        """
        return self.adapter.read(device_addr, mem_addr, length, self.config.address_width)
    
    def read_sequential(self, device_addr: int, start_addr: int, length: int) -> bytes:
        """Sequential read from EEPROM.
        
        Args:
            device_addr: I2C device address (7-bit)
            start_addr: Starting memory address
            length: Number of bytes to read
            
        Returns:
            bytes: Read data
        """
        # For sequential read, we can read in chunks or all at once
        # depending on adapter capabilities
        return self.adapter.read(device_addr, start_addr, length, self.config.address_width)
    
    def write_byte(self, device_addr: int, mem_addr: int, data: int) -> None:
        """Write single byte to EEPROM.
        
        Args:
            device_addr: I2C device address (7-bit)
            mem_addr: Memory address to write to
            data: Byte value to write
        """
        self.adapter.write(device_addr, mem_addr, bytes([data]), self.config.address_width)
        self._wait_write_cycle()
    
    def write_page(self, device_addr: int, mem_addr: int, data: bytes) -> None:
        """Write page to EEPROM.
        
        Args:
            device_addr: I2C device address (7-bit)
            mem_addr: Memory address to write to (should be page-aligned)
            data: Data to write (max page_size bytes)
            
        Raises:
            ValueError: If data exceeds page size
        """
        if len(data) > self.config.page_size:
            raise ValueError(f"Data size {len(data)} exceeds page size {self.config.page_size}")
        
        # Check page boundary
        page_start = (mem_addr // self.config.page_size) * self.config.page_size
        if mem_addr + len(data) > page_start + self.config.page_size:
            raise ValueError("Write would cross page boundary")
        
        self.adapter.write(device_addr, mem_addr, data, self.config.address_width)
        self._wait_write_cycle()
    
    def write_buffer(self, device_addr: int, start_addr: int, data: bytes) -> None:
        """Write buffer to EEPROM with automatic page handling.
        
        Args:
            device_addr: I2C device address (7-bit)
            start_addr: Starting memory address
            data: Data to write
        """
        offset = 0
        current_addr = start_addr
        
        while offset < len(data):
            # Calculate how much we can write in current page
            page_start = (current_addr // self.config.page_size) * self.config.page_size
            page_remaining = self.config.page_size - (current_addr - page_start)
            
            # Write size is minimum of remaining data and remaining page space
            write_size = min(len(data) - offset, page_remaining)
            
            # Write the chunk
            chunk = data[offset:offset + write_size]
            self.adapter.write(device_addr, current_addr, chunk, self.config.address_width)
            self._wait_write_cycle()
            
            # Move to next chunk
            offset += write_size
            current_addr += write_size
    
    def read_full(self, device_addr: int) -> bytes:
        """Read entire EEPROM contents.
        
        Args:
            device_addr: I2C device address (7-bit)
            
        Returns:
            bytes: Full EEPROM contents
        """
        return self.read_sequential(device_addr, 0, self.config.size_bytes)
    
    def erase_chip(self, device_addr: int, fill_value: int = 0xFF) -> None:
        """Erase (fill) entire EEPROM chip.
        
        Args:
            device_addr: I2C device address (7-bit)
            fill_value: Value to fill with (default 0xFF)
        """
        fill_data = bytes([fill_value] * self.config.page_size)
        
        for addr in range(0, self.config.size_bytes, self.config.page_size):
            remaining = self.config.size_bytes - addr
            if remaining < self.config.page_size:
                fill_data = bytes([fill_value] * remaining)
            
            self.write_page(device_addr, addr, fill_data)
    
    def _wait_write_cycle(self) -> None:
        """Wait for EEPROM write cycle to complete."""
        if self.config.write_cycle_ms > 0:
            time.sleep(self.config.write_cycle_ms / 1000.0)
    
    def verify_write(self, device_addr: int, mem_addr: int, expected_data: bytes) -> bool:
        """Verify written data by reading back.
        
        Args:
            device_addr: I2C device address (7-bit)
            mem_addr: Memory address to verify
            expected_data: Expected data
            
        Returns:
            bool: True if verification successful
        """
        try:
            read_data = self.read_random(device_addr, mem_addr, len(expected_data))
            return read_data == expected_data
        except I2CError:
            return False