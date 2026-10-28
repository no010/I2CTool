"""Main window for I2CTool PySide6 application."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QProgressBar,
    QRadioButton,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from adapters.simulation_adapter import SimulationAdapter
from i2ctool_core.eeprom_config import EEPROMManager
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
        self.adapter: Optional[SimulationAdapter] = None
        self.eeprom_manager = EEPROMManager()
        self.eeprom_ops: Optional[EEPROMOperations] = None
        self._buffered_eeprom_data: Optional[bytes] = None
        self._last_read_data: Optional[bytes] = None
        self._syncing_bus = False
        self._syncing_device = False
        self._current_device_addr = 0x50
        self._current_speed = 100
        self._recent_action = "-"
        
        self.setWindowTitle("I2CTool - I2C Debugging Tool")
        self.setGeometry(100, 100, 960, 660)
        
        self.setup_ui()
        self.setup_status_bar()
        self.connect_signals()
        
        # Initialize with simulation adapter
        self.init_adapter("simulation")
    
    def setup_ui(self):
        """Set up the user interface."""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)

        # Adapter strip (top)
        adapter_strip = QHBoxLayout()
        root_layout.addLayout(adapter_strip)

        adapter_strip.addWidget(QLabel("适配器:"))
        self.adapter_combo = QComboBox()
        self.adapter_combo.addItem("Simulation", "simulation")
        adapter_strip.addWidget(self.adapter_combo)

        adapter_strip.addSpacing(8)

        self.connect_btn = QPushButton("连接模拟器")
        adapter_strip.addWidget(self.connect_btn)

        adapter_strip.addStretch()

        # Tabs
        self.tab_widget = QTabWidget()
        root_layout.addWidget(self.tab_widget)

        self.general_tab = self.create_general_tab()
        self.eeprom_tab = self.create_eeprom_tab()

        self.tab_widget.addTab(self.general_tab, "通用读写")
        self.tab_widget.addTab(self.eeprom_tab, "EEPROM读写")
    
    def setup_status_bar(self):
        """Set up the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Status indicator
        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet("color: #e74c3c; font-size: 14px;")
        self.status_text = QLabel("状态: 未连接")

        # Divider helper
        def divider() -> QFrame:
            line = QFrame()
            line.setFrameShape(QFrame.VLine)
            line.setFrameShadow(QFrame.Sunken)
            line.setStyleSheet("color: #4a627a;")
            return line

        self.recent_action_label = QLabel("最近操作: -")
        self.connection_info_label = QLabel("总线: - | 地址: - | 速率: -")

        self.refresh_button = QToolButton()
        self.refresh_button.setText("⟳")
        self.refresh_button.setToolTip("刷新当前状态")

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(160)
        self.progress_bar.setVisible(False)

        self.status_bar.addWidget(self.status_indicator)
        self.status_bar.addWidget(self.status_text)
        self.status_bar.addWidget(divider())
        self.status_bar.addWidget(self.recent_action_label)
        self.status_bar.addWidget(divider())
        self.status_bar.addWidget(self.connection_info_label)
        self.status_bar.addPermanentWidget(self.progress_bar)
        self.status_bar.addPermanentWidget(self.refresh_button)

        self.status_bar.showMessage("准备就绪")
    
    def connect_signals(self):
        """Connect UI signals."""
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.adapter_combo.currentTextChanged.connect(self.on_adapter_changed)
        self.refresh_button.clicked.connect(self.refresh_status_summary)

        # General tab signals
        self.bus_combo.currentTextChanged.connect(self.on_bus_changed)
        self.speed_combo.currentTextChanged.connect(self.set_i2c_speed)
        self.scan_btn.clicked.connect(self.scan_i2c_bus)
        self.device_addr_spin.valueChanged.connect(self.on_general_device_changed)
        self.addr_width_group.buttonToggled.connect(self.on_addr_width_changed)
        self.read_button.clicked.connect(self.perform_read)
        self.write_button.clicked.connect(self.perform_write)

        # EEPROM tab signals
        self.eeprom_bus_combo.currentTextChanged.connect(self.on_bus_changed_from_eeprom)
        self.eeprom_device_spin.valueChanged.connect(self.on_eeprom_device_changed)
        self.eeprom_config_combo.currentTextChanged.connect(self.update_eeprom_config)
        self.eeprom_read_btn.clicked.connect(self.read_eeprom_to_view)
        self.eeprom_write_btn.clicked.connect(self.write_view_to_eeprom)
        self.eeprom_save_btn.clicked.connect(self.save_eeprom_buffer)
        self.eeprom_load_btn.clicked.connect(self.load_eeprom_buffer)
    
    def populate_eeprom_combo(self):
        """Populate EEPROM configuration combo box."""
        self.eeprom_config_combo.clear()
        for config in self.eeprom_manager.get_config_list():
            self.eeprom_config_combo.addItem(f"{config.name} ({config.size_bytes} bytes)", config.id)
    
    def init_adapter(self, adapter_type="simulation"):
        """Initialize the selected adapter."""
        if adapter_type == "simulation":
            from adapters.simulation_adapter import SimulationAdapter
            self.adapter = SimulationAdapter()
            self.status_bar.showMessage("已创建模拟适配器")
        elif adapter_type == "ch341":
            from adapters.ch341_adapter import CH341Adapter
            self.adapter = CH341Adapter()
            if CH341Adapter.is_available():
                self.status_bar.showMessage("CH341 adapter created (vendor DLL found)")
            else:
                self.status_bar.showMessage("CH341 adapter created (vendor DLL not found, install CH341DLL.dll)")
        elif adapter_type == "ch347":
            from adapters.ch347_adapter import CH347Adapter
            self.adapter = CH347Adapter()
            self.status_bar.showMessage("CH347 adapter created (not implemented)")
        else:
            self.adapter = None
            self.status_bar.showMessage("未知适配器类型")
    
    def on_adapter_changed(self):
        """Handle adapter selection change."""
        adapter_type = self.adapter_combo.currentData()
        if adapter_type:
            # Disconnect current adapter if connected
            if self.adapter and self.adapter.is_connected():
                self.adapter.close()
                self.update_ui_state(False)
                self.connect_btn.setText("连接模拟器")
            
            # Initialize new adapter
            self.init_adapter(adapter_type)
    
    def toggle_connection(self):
        """Toggle adapter connection."""
        if not self.adapter:
            self.init_adapter()
        
        if self.adapter.is_connected():
            self.adapter.close()
            self.connect_btn.setText("连接模拟器")
            self.status_bar.showMessage("已断开连接")
            self.set_status_indicator(connected=False)
            self.update_ui_state(False)
        else:
            if self.adapter.open():
                self.connect_btn.setText("断开连接")
                self.status_bar.showMessage("已连接模拟适配器")
                self.set_status_indicator(connected=True)
                self.populate_bus_options()
                self.update_ui_state(True)
            else:
                QMessageBox.warning(self, "Connection Error", "Failed to connect to adapter")
    
    def update_ui_state(self, connected):
        """Update UI elements based on connection state."""
        for widget in (
            self.bus_combo,
            self.speed_combo,
            self.scan_btn,
            self.device_addr_spin,
            self.register_spin,
            self.read_length_spin,
            self.read_button,
            self.write_button,
            self.write_data_input,
            self.addr16_radio,
            self.addr8_radio,
        ):
            widget.setEnabled(connected)

        for widget in (
            self.eeprom_bus_combo,
            self.eeprom_device_spin,
            self.eeprom_config_combo,
            self.eeprom_read_btn,
            self.eeprom_write_btn,
            self.eeprom_save_btn,
            self.eeprom_load_btn,
        ):
            widget.setEnabled(connected)

        if not connected:
            self.general_log.clear()
            self.eeprom_hex_view.clear()
            self._buffered_eeprom_data = None
            self._last_read_data = None
            self.connection_info_label.setText("总线: - | 地址: - | 速率: -")
            self.recent_action_label.setText("最近操作: -")

    # ------------------------------------------------------------------
    # General Tab
    # ------------------------------------------------------------------
    def create_general_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form_group = QGroupBox("I2C 基本配置")
        form_layout = QGridLayout(form_group)

        # Row 0: bus + speed
        form_layout.addWidget(QLabel("I2C 总线:"), 0, 0)
        self.bus_combo = QComboBox()
        form_layout.addWidget(self.bus_combo, 0, 1)

        form_layout.addWidget(QLabel("设备地址 (7-bit):"), 0, 2)
        self.device_addr_spin = QSpinBox()
        self.device_addr_spin.setPrefix("0x")
        self.device_addr_spin.setDisplayIntegerBase(16)
        self.device_addr_spin.setRange(0x00, 0x7F)
        self.device_addr_spin.setValue(self._current_device_addr)
        form_layout.addWidget(self.device_addr_spin, 0, 3)

        self.scan_btn = QPushButton("扫描设备")
        form_layout.addWidget(self.scan_btn, 0, 4)

        form_layout.addWidget(QLabel("总线速率:"), 1, 0)
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["50", "100", "400", "1000"])
        self.speed_combo.setCurrentText(str(self._current_speed))
        form_layout.addWidget(self.speed_combo, 1, 1)

        form_layout.addWidget(QLabel("寄存器地址:"), 1, 2)
        self.register_spin = QSpinBox()
        self.register_spin.setRange(0, 0xFFFF)
        self.register_spin.setPrefix("0x")
        self.register_spin.setDisplayIntegerBase(16)
        form_layout.addWidget(self.register_spin, 1, 3)

        addr_mode_layout = QHBoxLayout()
        self.addr_width_group = QButtonGroup(self)
        self.addr16_radio = QRadioButton("16-bit")
        self.addr8_radio = QRadioButton("8-bit")
        self.addr_width_group.addButton(self.addr16_radio, 2)
        self.addr_width_group.addButton(self.addr8_radio, 1)
        self.addr16_radio.setChecked(True)
        addr_mode_layout.addWidget(self.addr16_radio)
        addr_mode_layout.addWidget(self.addr8_radio)
        form_layout.addLayout(addr_mode_layout, 1, 4)

        layout.addWidget(form_group)

        # Read/Write group
        rw_group = QGroupBox("读写操作")
        rw_layout = QGridLayout(rw_group)

        rw_layout.addWidget(QLabel("写入数据 (Hex):"), 0, 0)
        self.write_data_input = QLineEdit("DE AD BE EF")
        rw_layout.addWidget(self.write_data_input, 0, 1, 1, 2)

        self.write_button = QPushButton("写 入")
        rw_layout.addWidget(self.write_button, 0, 3)

        rw_layout.addWidget(QLabel("读取长度 (Bytes):"), 1, 0)
        self.read_length_spin = QSpinBox()
        self.read_length_spin.setRange(1, 256)
        self.read_length_spin.setValue(16)
        rw_layout.addWidget(self.read_length_spin, 1, 1)

        self.read_button = QPushButton("读 取")
        rw_layout.addWidget(self.read_button, 1, 3)

        layout.addWidget(rw_group)

        # Log area
        log_group = QGroupBox("读取结果 / 日志")
        log_layout = QVBoxLayout(log_group)
        self.general_log = QPlainTextEdit()
        self.general_log.setFont(QFont("Cascadia Code", 11))
        self.general_log.setReadOnly(True)
        log_layout.addWidget(self.general_log)
        layout.addWidget(log_group)

        return tab

    def on_bus_changed(self):
        if self._syncing_bus:
            return

        if not self.adapter or not self.adapter.is_connected():
            return

        bus = self.bus_combo.currentText()
        try:
            self.adapter.set_bus(bus)
            self._syncing_bus = True
            if self.eeprom_bus_combo.currentText() != bus:
                self.eeprom_bus_combo.setCurrentText(bus)
        finally:
            self._syncing_bus = False

        self.refresh_status_summary()

    def on_bus_changed_from_eeprom(self):
        if self._syncing_bus:
            return

        bus = self.eeprom_bus_combo.currentText()
        if not bus:
            return
        try:
            self._syncing_bus = True
            if self.bus_combo.currentText() != bus:
                self.bus_combo.setCurrentText(bus)
        finally:
            self._syncing_bus = False

    def on_general_device_changed(self, value: int):
        if self._syncing_device:
            return

        self._current_device_addr = value
        try:
            self._syncing_device = True
            if self.eeprom_device_spin.value() != value:
                self.eeprom_device_spin.setValue(value)
        finally:
            self._syncing_device = False
        self.refresh_status_summary()

    def on_eeprom_device_changed(self, value: int):
        if self._syncing_device:
            return

        try:
            self._syncing_device = True
            if self.device_addr_spin.value() != value:
                self.device_addr_spin.setValue(value)
        finally:
            self._syncing_device = False
        self.refresh_status_summary()

    def on_addr_width_changed(self):
        if self.addr8_radio.isChecked():
            self.register_spin.setMaximum(0xFF)
        else:
            self.register_spin.setMaximum(0xFFFF)

    def perform_read(self):
        if not self.adapter or not self.adapter.is_connected():
            return

        device_addr = self.device_addr_spin.value()
        mem_addr = self.register_spin.value()
        length = self.read_length_spin.value()
        addr_width = 2 if self.addr16_radio.isChecked() else 1

        try:
            data = self.adapter.read(device_addr, mem_addr, length, addr_width)
            self._last_read_data = data
            hex_str = " ".join(f"{b:02X}" for b in data)
            log_entry = (
                f"> read(bus={self.bus_combo.currentText()}, addr=0x{device_addr:02X}, "
                f"reg=0x{mem_addr:04X}, len={length}, aw={addr_width})\n"
                f"DATA: {hex_str}"
            )
            self.append_log(log_entry)
            self.set_recent_action("读取成功")
        except I2CError as exc:
            QMessageBox.warning(self, "读取失败", str(exc))
            self.append_log(f"ERROR: {exc}")
            self.set_recent_action("读取失败")

    def perform_write(self):
        if not self.adapter or not self.adapter.is_connected():
            return

        device_addr = self.device_addr_spin.value()
        mem_addr = self.register_spin.value()
        addr_width = 2 if self.addr16_radio.isChecked() else 1

        try:
            data_bytes = self.parse_hex_bytes(self.write_data_input.text())
        except ValueError as exc:
            QMessageBox.warning(self, "写入失败", str(exc))
            return

        try:
            self.adapter.write(device_addr, mem_addr, data_bytes, addr_width)
            self.append_log(
                f"> write(bus={self.bus_combo.currentText()}, addr=0x{device_addr:02X}, "
                f"reg=0x{mem_addr:04X}, data=[{', '.join(f'{b:02X}' for b in data_bytes)}])\n"
                f"SUCCESS: Wrote {len(data_bytes)} bytes."
            )
            self.set_recent_action("写入成功")
        except I2CError as exc:
            QMessageBox.warning(self, "写入失败", str(exc))
            self.append_log(f"ERROR: {exc}")
            self.set_recent_action("写入失败")

    def append_log(self, text: str) -> None:
        self.general_log.appendPlainText(text)
        self.general_log.verticalScrollBar().setValue(self.general_log.verticalScrollBar().maximum())

    # ------------------------------------------------------------------
    # EEPROM Tab
    # ------------------------------------------------------------------
    def create_eeprom_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        config_group = QGroupBox("EEPROM 配置")
        cfg_layout = QGridLayout(config_group)

        cfg_layout.addWidget(QLabel("I2C 总线:"), 0, 0)
        self.eeprom_bus_combo = QComboBox()
        cfg_layout.addWidget(self.eeprom_bus_combo, 0, 1)

        cfg_layout.addWidget(QLabel("设备地址:"), 0, 2)
        self.eeprom_device_spin = QSpinBox()
        self.eeprom_device_spin.setPrefix("0x")
        self.eeprom_device_spin.setDisplayIntegerBase(16)
        self.eeprom_device_spin.setRange(0x00, 0x7F)
        self.eeprom_device_spin.setValue(self._current_device_addr)
        cfg_layout.addWidget(self.eeprom_device_spin, 0, 3)

        cfg_layout.addWidget(QLabel("EEPROM 型号:"), 1, 0)
        self.eeprom_config_combo = QComboBox()
        cfg_layout.addWidget(self.eeprom_config_combo, 1, 1, 1, 3)

        layout.addWidget(config_group)

        action_group = QGroupBox("操作")
        act_layout = QGridLayout(action_group)

        self.eeprom_read_btn = QPushButton("读取到视图")
        act_layout.addWidget(self.eeprom_read_btn, 0, 0)

        self.eeprom_write_btn = QPushButton("写入到EEPROM")
        act_layout.addWidget(self.eeprom_write_btn, 0, 1)

        self.eeprom_save_btn = QPushButton("保存到文件...")
        act_layout.addWidget(self.eeprom_save_btn, 0, 2)

        self.eeprom_load_btn = QPushButton("从文件写入...")
        act_layout.addWidget(self.eeprom_load_btn, 0, 3)

        self.eeprom_progress = QProgressBar()
        self.eeprom_progress.setVisible(False)
        act_layout.addWidget(QLabel("进度:"), 1, 0)
        act_layout.addWidget(self.eeprom_progress, 1, 1, 1, 3)

        layout.addWidget(action_group)

        hex_group = QGroupBox("数据视图")
        hex_layout = QVBoxLayout(hex_group)
        self.eeprom_hex_view = QPlainTextEdit()
        self.eeprom_hex_view.setFont(QFont("Cascadia Code", 10))
        self.eeprom_hex_view.setReadOnly(True)
        hex_layout.addWidget(self.eeprom_hex_view)

        layout.addWidget(hex_group)

        return tab
    
    def scan_i2c_bus(self):
        """Scan I2C bus for devices."""
        if not self.adapter or not self.adapter.is_connected():
            return

        self.scan_btn.setEnabled(False)
        self.status_bar.showMessage("正在扫描 I2C 总线...")

        self.scan_thread = I2CScanThread(self.adapter)
        self.scan_thread.scan_complete.connect(self.on_scan_complete)
        self.scan_thread.scan_error.connect(self.on_scan_error)
        self.scan_thread.start()
    
    def on_scan_complete(self, devices):
        """Handle scan completion."""
        self.scan_btn.setEnabled(True)
        self.status_bar.showMessage(f"扫描完成 - 找到 {len(devices)} 个设备")
        if devices:
            device_list = ", ".join(f"0x{addr:02X}" for addr in devices)
            self.append_log(f"SCAN: {device_list}")
        else:
            self.append_log("SCAN: 未发现设备")

        if devices and self.device_addr_spin.value() not in devices:
            self.device_addr_spin.setValue(devices[0])
    
    def on_scan_error(self, error):
        """Handle scan error."""
        QMessageBox.warning(self, "Scan Error", f"Failed to scan I2C bus: {error}")
        self.scan_btn.setEnabled(True)
        self.status_bar.showMessage("扫描失败")
        self.append_log(f"SCAN ERROR: {error}")
    
    def set_i2c_speed(self, speed_text):
        """Set I2C communication speed."""
        if not self.adapter or not self.adapter.is_connected():
            return
        try:
            speed = int(speed_text)
            self.adapter.set_speed(speed)
            self._current_speed = speed
            self.status_bar.showMessage(f"I2C 速率已设为 {speed} kHz")
            self.refresh_status_summary()
        except Exception as e:
            QMessageBox.warning(self, "Speed Error", f"Failed to set speed: {e}")
    
    def update_eeprom_config(self):
        """Update EEPROM configuration."""
        config_id = self.eeprom_config_combo.currentData()
        if config_id:
            config = self.eeprom_manager.get_config(config_id)
            if config and self.adapter:
                self.eeprom_ops = EEPROMOperations(self.adapter, config)
                self.status_bar.showMessage(f"当前 EEPROM 配置: {config.name}")

    def read_eeprom_to_view(self):
        if not self.eeprom_ops or not self.adapter or not self.adapter.is_connected():
            return

        device_addr = self.eeprom_device_spin.value()

        try:
            self.toggle_eeprom_controls(False)
            self.eeprom_progress.setVisible(True)
            self.eeprom_progress.setRange(0, 0)
            data = self.eeprom_ops.read_full(device_addr)
            self._buffered_eeprom_data = data
            self.eeprom_hex_view.setPlainText(self.format_hex_dump(data))
            self.status_bar.showMessage(f"读取完成，共 {len(data)} 字节")
            self.set_recent_action("EEPROM读取完成")
        except I2CError as exc:
            QMessageBox.warning(self, "读取失败", str(exc))
            self.status_bar.showMessage("EEPROM 读取失败")
        finally:
            self.toggle_eeprom_controls(True)
            self.eeprom_progress.setVisible(False)

    def write_view_to_eeprom(self):
        if not self.eeprom_ops or not self.adapter or not self.adapter.is_connected():
            return

        if not self._buffered_eeprom_data:
            QMessageBox.information(self, "提示", "请先读取或加载数据")
            return

        device_addr = self.eeprom_device_spin.value()
        config = self.eeprom_manager.get_config(self.eeprom_config_combo.currentData())
        if not config:
            QMessageBox.warning(self, "配置错误", "无法获取 EEPROM 配置")
            return

        data = self._buffered_eeprom_data
        if len(data) != config.size_bytes:
            reply = QMessageBox.question(
                self,
                "数据长度不匹配",
                "数据长度与所选 EEPROM 大小不同，仍要写入吗？",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        try:
            self.toggle_eeprom_controls(False)
            self.eeprom_progress.setVisible(True)
            self.eeprom_progress.setRange(0, 100)

            chunk_size = config.page_size or 64
            total = len(data)
            written = 0
            while written < total:
                chunk = data[written : written + chunk_size]
                self.adapter.write(device_addr, written, chunk, config.address_width)
                written += len(chunk)
                self.eeprom_progress.setValue(int((written / total) * 100))
            self.status_bar.showMessage("EEPROM 写入完成")
            self.set_recent_action("EEPROM写入完成")
        except I2CError as exc:
            QMessageBox.warning(self, "写入失败", str(exc))
            self.status_bar.showMessage("EEPROM 写入失败")
        finally:
            self.toggle_eeprom_controls(True)
            self.eeprom_progress.setVisible(False)

    def save_eeprom_buffer(self):
        if not self._buffered_eeprom_data:
            QMessageBox.information(self, "提示", "没有可保存的数据")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "保存 EEPROM 数据", "eeprom.bin")
        if not file_path:
            return

        try:
            Path(file_path).write_bytes(self._buffered_eeprom_data)
            self.status_bar.showMessage(f"已保存到 {file_path}")
            self.set_recent_action("EEPROM数据已保存")
        except OSError as exc:
            QMessageBox.warning(self, "保存失败", str(exc))

    def load_eeprom_buffer(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 EEPROM 数据文件", "", "Binary Files (*.bin);;All Files (*)")
        if not file_path:
            return

        try:
            data = Path(file_path).read_bytes()
        except OSError as exc:
            QMessageBox.warning(self, "读取文件失败", str(exc))
            return

        self._buffered_eeprom_data = data
        self.eeprom_hex_view.setPlainText(self.format_hex_dump(data))
        self.status_bar.showMessage(f"已从 {file_path} 加载 {len(data)} 字节")
        self.set_recent_action("文件加载完成")

    def toggle_eeprom_controls(self, enabled: bool) -> None:
        for widget in (
            self.eeprom_read_btn,
            self.eeprom_write_btn,
            self.eeprom_save_btn,
            self.eeprom_load_btn,
        ):
            widget.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def populate_bus_options(self):
        if not self.adapter:
            return

        if hasattr(self.adapter, "list_buses"):
            buses = self.adapter.list_buses()
        else:
            buses = ["/dev/i2c-1"]

        self._syncing_bus = True
        try:
            self.bus_combo.clear()
            self.bus_combo.addItems(buses)

            self.eeprom_bus_combo.clear()
            self.eeprom_bus_combo.addItems(buses)

            if buses:
                self.bus_combo.setCurrentIndex(0)
                self.eeprom_bus_combo.setCurrentIndex(0)
                self.adapter.set_bus(buses[0])
        finally:
            self._syncing_bus = False

        self.refresh_status_summary()

    def refresh_status_summary(self):
        bus = self.bus_combo.currentText() or "-"
        addr = f"0x{self.device_addr_spin.value():02X}" if self.adapter and self.adapter.is_connected() else "-"
        speed = f"{self._current_speed} kHz" if self.adapter and self.adapter.is_connected() else "-"
        self.connection_info_label.setText(f"总线: {bus} | 地址: {addr} | 速率: {speed}")

    def set_status_indicator(self, connected: bool):
        if connected:
            self.status_indicator.setStyleSheet("color: #2ecc71; font-size: 14px;")
            self.status_text.setText("状态: 空闲")
        else:
            self.status_indicator.setStyleSheet("color: #e74c3c; font-size: 14px;")
            self.status_text.setText("状态: 未连接")

    def set_recent_action(self, text: str):
        self._recent_action = text
        self.recent_action_label.setText(f"最近操作: {text}")

    @staticmethod
    def parse_hex_bytes(text: str) -> bytes:
        text = text.replace(",", " ")
        parts = [p.strip() for p in text.split() if p.strip()]
        if not parts:
            raise ValueError("请输入要写入的十六进制数据")
        try:
            return bytes(int(part, 16) for part in parts)
        except ValueError as exc:
            raise ValueError("无效的十六进制数据") from exc

    @staticmethod
    def format_hex_dump(data: bytes, width: int = 16) -> str:
        lines: List[str] = []
        for offset in range(0, len(data), width):
            chunk = data[offset : offset + width]
            hex_part = " ".join(f"{byte:02X}" for byte in chunk)
            ascii_part = "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in chunk)
            lines.append(f"{offset:08X}  {hex_part:<{width * 3}}  |{ascii_part}|")
        return "\n".join(lines)