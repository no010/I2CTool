"""
Main window for I2CTool PySide6 application.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGroupBox, QComboBox, QPushButton, QLabel, 
    QSpinBox, QTextEdit, QTableWidget, QTableWidgetItem,
    QSplitter, QMessageBox, QProgressBar, QStatusBar
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from i2ctool_core.eeprom_config import EEPROMManager
from adapters.simulation_adapter import SimulationAdapter
from i2ctool_core.eeprom_operations import EEPROMOperations
from i2ctool_core.interfaces import I2CError


class I2CScanThread(QThread):
    """Thread for I2C bus scanning."""
    scan_complete = Signal(list)
    scan_error = Signal(str)
    
    def __init__(self, adapter):
        super().__init__()
        self.adapter = adapter
    
    def run(self):
        try:
            devices = self.adapter.scan()
            self.scan_complete.emit(devices)
        except Exception as e:
            self.scan_error.emit(str(e))


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.adapter = None
        self.eeprom_manager = EEPROMManager()
        self.eeprom_ops = None
        
        self.setWindowTitle("I2CTool - I2C Debugging Tool")
        self.setGeometry(100, 100, 1000, 700)
        
        self.setup_ui()
        self.setup_status_bar()
        self.connect_signals()
        
        # Initialize with simulation adapter
        self.init_adapter("simulation")
    
    def setup_ui(self):
        """Set up the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Create main splitter
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        # Left panel - Controls
        left_panel = self.create_control_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - Data display
        right_panel = self.create_data_panel()
        splitter.addWidget(right_panel)
        
        # Set splitter proportions
        splitter.setSizes([300, 700])
    
    def create_control_panel(self):
        """Create the control panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Adapter selection
        adapter_group = QGroupBox("Hardware Adapter")
        adapter_layout = QVBoxLayout(adapter_group)
        
        self.adapter_combo = QComboBox()
        self.adapter_combo.addItem("Simulation", "simulation")
        self.adapter_combo.addItem("CH341 (Not implemented)", "ch341")
        self.adapter_combo.addItem("CH347 (Not implemented)", "ch347")
        self.adapter_combo.currentTextChanged.connect(self.on_adapter_changed)
        adapter_layout.addWidget(self.adapter_combo)
        
        self.connect_btn = QPushButton("Connect")
        adapter_layout.addWidget(self.connect_btn)
        
        layout.addWidget(adapter_group)
        
        # I2C settings
        i2c_group = QGroupBox("I2C Settings")
        i2c_layout = QVBoxLayout(i2c_group)
        
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Speed (kHz):"))
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["100", "400", "1000"])
        speed_layout.addWidget(self.speed_combo)
        i2c_layout.addLayout(speed_layout)
        
        self.scan_btn = QPushButton("Scan I2C Bus")
        i2c_layout.addWidget(self.scan_btn)
        
        layout.addWidget(i2c_group)
        
        # EEPROM selection
        eeprom_group = QGroupBox("EEPROM Configuration")
        eeprom_layout = QVBoxLayout(eeprom_group)
        
        self.eeprom_combo = QComboBox()
        self.populate_eeprom_combo()
        eeprom_layout.addWidget(self.eeprom_combo)
        
        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel("Device Address:"))
        self.device_addr_spin = QSpinBox()
        self.device_addr_spin.setPrefix("0x")
        self.device_addr_spin.setDisplayIntegerBase(16)
        self.device_addr_spin.setRange(0, 127)
        self.device_addr_spin.setValue(0x50)
        device_layout.addWidget(self.device_addr_spin)
        eeprom_layout.addLayout(device_layout)
        
        layout.addWidget(eeprom_group)
        
        # Operations
        ops_group = QGroupBox("Operations")
        ops_layout = QVBoxLayout(ops_group)
        
        self.read_full_btn = QPushButton("Read Full EEPROM")
        ops_layout.addWidget(self.read_full_btn)
        
        self.erase_btn = QPushButton("Erase EEPROM")
        ops_layout.addWidget(self.erase_btn)
        
        layout.addWidget(ops_group)
        
        layout.addStretch()
        return panel
    
    def create_data_panel(self):
        """Create the data display panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Device list
        devices_group = QGroupBox("Detected I2C Devices")
        devices_layout = QVBoxLayout(devices_group)
        
        self.devices_table = QTableWidget(0, 2)
        self.devices_table.setHorizontalHeaderLabels(["Address", "Status"])
        devices_layout.addWidget(self.devices_table)
        
        layout.addWidget(devices_group)
        
        # Data display
        data_group = QGroupBox("EEPROM Data")
        data_layout = QVBoxLayout(data_group)
        
        self.data_display = QTextEdit()
        self.data_display.setFont(QFont("Courier", 10))
        self.data_display.setPlainText("No data loaded. Click 'Read Full EEPROM' to start.")
        data_layout.addWidget(self.data_display)
        
        layout.addWidget(data_group)
        
        return panel
    
    def setup_status_bar(self):
        """Set up the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        self.status_bar.showMessage("Ready")
    
    def connect_signals(self):
        """Connect UI signals."""
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.scan_btn.clicked.connect(self.scan_i2c_bus)
        self.speed_combo.currentTextChanged.connect(self.set_i2c_speed)
        self.read_full_btn.clicked.connect(self.read_full_eeprom)
        self.erase_btn.clicked.connect(self.erase_eeprom)
        self.eeprom_combo.currentTextChanged.connect(self.update_eeprom_config)
    
    def populate_eeprom_combo(self):
        """Populate EEPROM configuration combo box."""
        self.eeprom_combo.clear()
        for config in self.eeprom_manager.get_config_list():
            self.eeprom_combo.addItem(f"{config.name} ({config.size_bytes} bytes)", config.id)
    
    def init_adapter(self, adapter_type="simulation"):
        """Initialize the selected adapter."""
        if adapter_type == "simulation":
            from adapters.simulation_adapter import SimulationAdapter
            self.adapter = SimulationAdapter()
            self.status_bar.showMessage("Simulation adapter created")
        elif adapter_type == "ch341":
            from adapters.ch341_adapter import CH341Adapter
            self.adapter = CH341Adapter()
            self.status_bar.showMessage("CH341 adapter created (not implemented)")
        elif adapter_type == "ch347":
            from adapters.ch347_adapter import CH347Adapter
            self.adapter = CH347Adapter()
            self.status_bar.showMessage("CH347 adapter created (not implemented)")
        else:
            self.adapter = None
            self.status_bar.showMessage("Unknown adapter type")
    
    def on_adapter_changed(self):
        """Handle adapter selection change."""
        adapter_type = self.adapter_combo.currentData()
        if adapter_type:
            # Disconnect current adapter if connected
            if self.adapter and self.adapter.is_connected():
                self.adapter.close()
                self.update_ui_state(False)
                self.connect_btn.setText("Connect")
            
            # Initialize new adapter
            self.init_adapter(adapter_type)
    
    def toggle_connection(self):
        """Toggle adapter connection."""
        if not self.adapter:
            self.init_adapter()
        
        if self.adapter.is_connected():
            self.adapter.close()
            self.connect_btn.setText("Connect")
            self.status_bar.showMessage("Disconnected")
            self.update_ui_state(False)
        else:
            if self.adapter.open():
                self.connect_btn.setText("Disconnect")
                self.status_bar.showMessage("Connected to simulation adapter")
                self.update_ui_state(True)
            else:
                QMessageBox.warning(self, "Connection Error", "Failed to connect to adapter")
    
    def update_ui_state(self, connected):
        """Update UI elements based on connection state."""
        self.scan_btn.setEnabled(connected)
        self.speed_combo.setEnabled(connected)
        self.read_full_btn.setEnabled(connected)
        self.erase_btn.setEnabled(connected)
    
    def scan_i2c_bus(self):
        """Scan I2C bus for devices."""
        if not self.adapter or not self.adapter.is_connected():
            return
        
        self.scan_btn.setEnabled(False)
        self.status_bar.showMessage("Scanning I2C bus...")
        
        self.scan_thread = I2CScanThread(self.adapter)
        self.scan_thread.scan_complete.connect(self.on_scan_complete)
        self.scan_thread.scan_error.connect(self.on_scan_error)
        self.scan_thread.start()
    
    def on_scan_complete(self, devices):
        """Handle scan completion."""
        self.devices_table.setRowCount(len(devices))
        
        for i, addr in enumerate(devices):
            addr_item = QTableWidgetItem(f"0x{addr:02X}")
            status_item = QTableWidgetItem("Present")
            
            self.devices_table.setItem(i, 0, addr_item)
            self.devices_table.setItem(i, 1, status_item)
        
        self.devices_table.resizeColumnsToContents()
        self.scan_btn.setEnabled(True)
        self.status_bar.showMessage(f"Scan complete - found {len(devices)} device(s)")
    
    def on_scan_error(self, error):
        """Handle scan error."""
        QMessageBox.warning(self, "Scan Error", f"Failed to scan I2C bus: {error}")
        self.scan_btn.setEnabled(True)
        self.status_bar.showMessage("Scan failed")
    
    def set_i2c_speed(self, speed_text):
        """Set I2C communication speed."""
        if not self.adapter or not self.adapter.is_connected():
            return
        
        try:
            speed = int(speed_text)
            self.adapter.set_speed(speed)
            self.status_bar.showMessage(f"I2C speed set to {speed} kHz")
        except Exception as e:
            QMessageBox.warning(self, "Speed Error", f"Failed to set speed: {e}")
    
    def update_eeprom_config(self):
        """Update EEPROM configuration."""
        config_id = self.eeprom_combo.currentData()
        if config_id:
            config = self.eeprom_manager.get_config(config_id)
            if config and self.adapter:
                self.eeprom_ops = EEPROMOperations(self.adapter, config)
                self.status_bar.showMessage(f"EEPROM config: {config.name}")
    
    def read_full_eeprom(self):
        """Read full EEPROM contents."""
        if not self.eeprom_ops or not self.adapter.is_connected():
            return
        
        device_addr = self.device_addr_spin.value()
        
        try:
            self.read_full_btn.setEnabled(False)
            self.status_bar.showMessage("Reading EEPROM...")
            
            data = self.eeprom_ops.read_full(device_addr)
            self.display_hex_data(data)
            
            self.status_bar.showMessage(f"Read {len(data)} bytes from EEPROM")
        except I2CError as e:
            QMessageBox.warning(self, "Read Error", f"Failed to read EEPROM: {e}")
            self.status_bar.showMessage("Read failed")
        finally:
            self.read_full_btn.setEnabled(True)
    
    def erase_eeprom(self):
        """Erase EEPROM (fill with 0xFF)."""
        if not self.eeprom_ops or not self.adapter.is_connected():
            return
        
        reply = QMessageBox.question(
            self, "Confirm Erase", 
            "Are you sure you want to erase the EEPROM?\n"
            "This will overwrite all data with 0xFF.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            device_addr = self.device_addr_spin.value()
            
            try:
                self.erase_btn.setEnabled(False)
                self.status_bar.showMessage("Erasing EEPROM...")
                
                self.eeprom_ops.erase_chip(device_addr)
                
                self.status_bar.showMessage("EEPROM erased successfully")
            except I2CError as e:
                QMessageBox.warning(self, "Erase Error", f"Failed to erase EEPROM: {e}")
                self.status_bar.showMessage("Erase failed")
            finally:
                self.erase_btn.setEnabled(True)
    
    def display_hex_data(self, data):
        """Display data in hex format."""
        lines = []
        for i in range(0, len(data), 16):
            # Address
            addr_str = f"{i:04X}: "
            
            # Hex bytes
            hex_bytes = []
            ascii_chars = []
            
            for j in range(16):
                if i + j < len(data):
                    byte = data[i + j]
                    hex_bytes.append(f"{byte:02X}")
                    ascii_chars.append(chr(byte) if 32 <= byte <= 126 else '.')
                else:
                    hex_bytes.append("  ")
                    ascii_chars.append(" ")
            
            # Format: ADDR: XX XX XX XX XX XX XX XX XX XX XX XX XX XX XX XX  |ASCII........|
            hex_str = " ".join(hex_bytes[:8]) + "  " + " ".join(hex_bytes[8:])
            ascii_str = "".join(ascii_chars)
            
            lines.append(f"{addr_str}{hex_str}  |{ascii_str}|")
        
        self.data_display.setPlainText("\n".join(lines))