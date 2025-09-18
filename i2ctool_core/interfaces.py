"""
Hardware adapter interfaces for I2C communication.
"""

from abc import ABC, abstractmethod
from typing import List, Optional


class I2CAdapter(ABC):
    """Abstract base class for I2C hardware adapters."""
    
    @abstractmethod
    def open(self) -> bool:
        """Open connection to hardware device.
        
        Returns:
            bool: True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close connection to hardware device."""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if device is connected and ready.
        
        Returns:
            bool: True if connected, False otherwise
        """
        pass
    
    @abstractmethod
    def scan(self) -> List[int]:
        """Scan I2C bus for devices.
        
        Returns:
            List[int]: List of detected I2C device addresses (7-bit)
        """
        pass
    
    @abstractmethod
    def read(self, device_addr: int, mem_addr: int, length: int, 
             addr_width: int = 1) -> bytes:
        """Read data from I2C device.
        
        Args:
            device_addr: I2C device address (7-bit)
            mem_addr: Memory address to read from
            length: Number of bytes to read
            addr_width: Address width in bytes (1 or 2)
            
        Returns:
            bytes: Read data
            
        Raises:
            I2CError: If communication fails
        """
        pass
    
    @abstractmethod
    def write(self, device_addr: int, mem_addr: int, data: bytes,
              addr_width: int = 1) -> None:
        """Write data to I2C device.
        
        Args:
            device_addr: I2C device address (7-bit)
            mem_addr: Memory address to write to
            data: Data to write
            addr_width: Address width in bytes (1 or 2)
            
        Raises:
            I2CError: If communication fails
        """
        pass
    
    @abstractmethod
    def set_speed(self, khz: int) -> None:
        """Set I2C communication speed.
        
        Args:
            khz: Speed in kHz (e.g., 100, 400)
        """
        pass
    
    @abstractmethod
    def supports_eeprom_page_write(self) -> bool:
        """Check if adapter supports EEPROM page write optimization.
        
        Returns:
            bool: True if page write is supported
        """
        pass


class I2CError(Exception):
    """Exception raised for I2C communication errors."""
    pass