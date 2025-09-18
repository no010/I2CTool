# I2CTool

I2C 调试工具 —— 支持 PySide6 原生 GUI 与 Tauri 前端两种实现路径。  
目标是通过合理抽象把硬件相关细节封装成统一接口，初期以 CH341 和 CH347 芯片为主，支持通用 I2C 调试与 EEPROM 芯片读写；EEPROM 型号可通过简单配置扩展。

概览
- 前端：可选 PySide6（原生桌面）或 Tauri（Web + 小体积后端）实现 UI。
- 后端：Python 核心库（跨前端共享），封装硬件适配层（Adapter）。
- 硬件适配器：实现统一的 I2C/EEPROM 接口，当前提供 ch341 与 ch347 适配器实现。
- 可扩展性：通过 JSON/YAML 配置文件注册 EEPROM 型号，无需改动核心代码即可新增型号。

核心目标
- 通用 I2C 调试（扫描、读写、速率配置等）。
- 通用 EEPROM 读写（支持随机读、顺序读、分页写等）。
- 通过适配器接口屏蔽底层芯片差异，便于新增芯片支持。
- 易于扩展的 EEPROM 芯片描述格式，便于用户添加新型号。

架构（简述）
- i2ctool-core/    -> Python 包，包含设备抽象、EEPROM 操作、配置加载
- adapters/        -> 各硬件适配器（ch341、ch347 等）
- ui-pyside6/      -> PySide6 前端（本地调试工具）
- ui-tauri/        -> Tauri 前端（Web UI + 后端桥接）
- configs/         -> EEPROM 型号描述文件（JSON/YAML）

硬件适配器（接口示例）
适配器应实现如下方法（示例接口，具体以代码为准）：
- open() / close()
- scan() -> list[i2c_address]
- read(device_addr, mem_addr, length) -> bytes
- write(device_addr, mem_addr, data) -> None
- set_speed(khz)
- supports_eeprom_page_write() -> bool

通过以上统一接口，上层 EEPROM 逻辑无需关心底层芯片差异（例如 CH341 与 CH347 的 API 差异由对应适配器实现）。

EEPROM 芯片描述（示例 JSON）
说明：放在 configs/eeprom/ 目录下。字段示例尽量简洁，覆盖常见 EEPROM 行为（地址宽度、页大小、总容量等）。
示例：
{
  "id": "24c256",
  "name": "Atmel 24C256",
  "size_bytes": 32768,
  "address_width": 2,        // 1 或 2 字节内部地址
  "page_size": 64,          // 页写入最大字节数
  "write_cycle_ms": 5,      // 写周期时间（可用于轮询等待）
  "notes": "Standard I2C EEPROM"
}

如何新增型号（高层步骤）
1. 在 configs/eeprom/ 下添加一个 JSON/YAML 文件，填写必要字段（如上示例）。  
2. 在 UI 中刷新型号列表或重启工具，工具会加载新增的型号。  
3. 如特殊芯片有非标准操作（例如特殊寻址或多片并联），可在适配器层添加小适配逻辑或扩展配置字段。

使用说明（快速上手）
- 运行 PySide6 开发界面（示例）
  1. 安装依赖：pip install -r requirements-dev.txt（包含 PySide6）
  2. 启动：python -m ui_pyside6.main
  3. 或运行演示：python run_demo.py（命令行演示）
- 测试功能：python test_gui.py（验证所有组件）
- 运行 Tauri 开发界面（示例）
  1. 安装前端依赖（在 ui-tauri 目录）并启动 Tauri dev（按 Tauri 官方流程）
  2. 后端（Python）以守护进程或插件方式暴露适配器 API

开发与打包
- 在 Windows 上测试 CH341/CH347 驱动需先安装对应厂商驱动。  
- 打包 PySide6：使用 PyInstaller 打包 Python 程序。  
- 打包 Tauri：按 Tauri 官方文档，前端构建后由 Tauri 打包本地可执行文件（后端需提供本地桥接层）。

调试建议
- 在调试 EEPROM 写入时使用小数据量、开启写周期等待或轮询 ACK。  
- 提供“仿真模式”适配器以便没有硬件时进行 UI 功能测试。

贡献指南
- 欢迎通过 PR 提交适配器、EEPROM 配置或 UI 改进。  
- 新增适配器请实现核心接口并加入测试用例。

许可证
- 请在仓库根目录添加 LICENSE（例如 MIT），并在此处注明项目许可证。

联系
- 在仓库中使用 Issues 提交需求或硬件兼容性问题。
