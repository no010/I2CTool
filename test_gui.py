#!/usr/bin/env python3
"""
Test script to verify I2CTool functionality.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_core_functionality():
    """Test core functionality without GUI. Returns True only if all checks pass."""
    from i2ctool_core.eeprom_config import EEPROMManager
    from adapters.simulation_adapter import SimulationAdapter
    from i2ctool_core.eeprom_operations import EEPROMOperations
    
    failed = False
    print("=== Testing I2CTool Core Functionality ===")
    
    # Test EEPROM configuration manager
    print("\n1. Testing EEPROM Configuration Manager...")
    manager = EEPROMManager()
    configs = manager.get_config_list()
    print(f"   Loaded {len(configs)} EEPROM configurations:")
    for config in configs:
        print(f"   - {config.id}: {config.name} ({config.size_bytes} bytes, "
              f"page size: {config.page_size})")
    
    # Test simulation adapter
    print("\n2. Testing Simulation Adapter...")
    adapter = SimulationAdapter()
    adapter.open()
    print(f"   Connected: {adapter.is_connected()}")
    print(f"   Adapter info: {adapter.get_info()}")
    
    # Test I2C scanning
    print("\n3. Testing I2C Bus Scanning...")
    devices = adapter.scan()
    print(f"   Found {len(devices)} devices: {[hex(d) for d in devices]}")
    
    # Test EEPROM operations
    print("\n4. Testing EEPROM Operations...")
    config = manager.get_config('24c256')
    if config:
        ops = EEPROMOperations(adapter, config)
        
        # Test read
        device_addr = 0x50
        print(f"   Reading from device 0x{device_addr:02X}...")
        data = ops.read_random(device_addr, 0, 32)
        print(f"   First 32 bytes: {data.hex()}")
        
        # Test write and verify
        print(f"   Testing write operation...")
        test_data = b"I2CTool Test Data 123"
        ops.write_buffer(device_addr, 100, test_data)
        
        # Verify write
        read_back = ops.read_random(device_addr, 100, len(test_data))
        if read_back == test_data:
            print(f"   Write/read verification: PASSED")
        else:
            print(f"   Write/read verification: FAILED")
            print(f"   Expected: {test_data}")
            print(f"   Got:      {read_back}")
            adapter.close()
            raise AssertionError(
                f"Write/read verification failed: expected {test_data!r}, got {read_back!r}"
            )
    else:
        print("   ERROR: EEPROM config '24c256' not found")
        failed = True
    
    adapter.close()
    print("\n=== Core functionality test completed ===")
    return not failed


def test_gui_imports():
    """Test GUI imports without actually running the GUI. Returns True only if all checks pass."""
    print("\n=== Testing GUI Imports ===")
    
    try:
        from ui_pyside6.main_window import MainWindow
        from PySide6.QtWidgets import QApplication
        print("   GUI imports: PASSED")
        
        # Test creating application (but don't show)
        app = QApplication([])
        print("   QApplication creation: PASSED")
        
        # Test creating main window (but don't show)
        window = MainWindow()
        print("   MainWindow creation: PASSED")
        
        print("   GUI framework initialization: PASSED")
        return True
        
    except Exception as e:
        print(f"   GUI test failed: {e}")
        return False


if __name__ == "__main__":
    exit_code = 0
    for test in (test_core_functionality, test_gui_imports):
        try:
            passed = test()
        except Exception as e:
            print(f"\n{test.__name__} raised an exception: {e}")
            passed = False
        if not passed:
            exit_code = 1

    if exit_code == 0:
        print("\n=== All tests completed ===")
    else:
        print("\n=== Tests FAILED ===")
    sys.exit(exit_code)