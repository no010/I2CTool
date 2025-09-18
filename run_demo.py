#!/usr/bin/env python3
"""
Demo script to showcase I2CTool functionality.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from i2ctool_core.eeprom_config import EEPROMManager
from adapters.simulation_adapter import SimulationAdapter
from i2ctool_core.eeprom_operations import EEPROMOperations


def main():
    """Run I2CTool demo."""
    print("=== I2CTool Demo ===")
    print("This demo shows the core functionality of I2CTool using simulation adapter.")
    
    # Initialize components
    print("\n1. Initializing components...")
    manager = EEPROMManager()
    adapter = SimulationAdapter()
    
    print(f"   - Loaded {len(manager.get_config_list())} EEPROM configurations")
    print(f"   - Created simulation adapter")
    
    # Connect to adapter
    print("\n2. Connecting to adapter...")
    if adapter.open():
        print(f"   - Connected successfully")
        print(f"   - Adapter: {adapter.get_info()}")
    else:
        print("   - Failed to connect")
        return
    
    # Scan I2C bus
    print("\n3. Scanning I2C bus...")
    devices = adapter.scan()
    print(f"   - Found {len(devices)} devices:")
    for device in devices:
        print(f"     * 0x{device:02X}")
    
    if not devices:
        print("   - No devices found, ending demo")
        return
    
    # Select first device and 24C256 config
    device_addr = devices[0]
    config = manager.get_config('24c256')
    
    if not config:
        print("   - 24C256 config not found")
        return
    
    print(f"\n4. Using device 0x{device_addr:02X} with {config.name}")
    ops = EEPROMOperations(adapter, config)
    
    # Read some data
    print("\n5. Reading EEPROM data...")
    print("   - Reading first 64 bytes:")
    data = ops.read_random(device_addr, 0, 64)
    
    # Display in hex format
    for i in range(0, len(data), 16):
        hex_bytes = " ".join(f"{data[i+j]:02X}" if i+j < len(data) else "  " 
                           for j in range(16))
        ascii_chars = "".join(chr(data[i+j]) if i+j < len(data) and 32 <= data[i+j] <= 126 else "."
                            for j in range(16) if i+j < len(data))
        print(f"     {i:04X}: {hex_bytes:<47} |{ascii_chars}|")
    
    # Write test data
    print("\n6. Writing test data...")
    test_message = b"Hello I2CTool! This is a test message for EEPROM."
    write_addr = 0x100  # Write at address 256
    
    print(f"   - Writing {len(test_message)} bytes at address 0x{write_addr:04X}")
    ops.write_buffer(device_addr, write_addr, test_message)
    
    # Read back and verify
    print("\n7. Verifying write...")
    read_back = ops.read_random(device_addr, write_addr, len(test_message))
    
    if read_back == test_message:
        print("   - Write verification: ✓ PASSED")
        print(f"   - Message: {read_back.decode('ascii', errors='replace')}")
    else:
        print("   - Write verification: ✗ FAILED")
    
    # Show EEPROM info
    print(f"\n8. EEPROM Information:")
    print(f"   - Type: {config.name}")
    print(f"   - Size: {config.size_bytes} bytes ({config.size_bytes // 1024}KB)")
    print(f"   - Page size: {config.page_size} bytes")
    print(f"   - Address width: {config.address_width} bytes")
    print(f"   - Write cycle time: {config.write_cycle_ms} ms")
    
    # Close connection
    adapter.close()
    print(f"\n9. Demo completed successfully!")
    print("\nTo run the GUI version:")
    print("   python -m ui_pyside6.main")


if __name__ == "__main__":
    main()