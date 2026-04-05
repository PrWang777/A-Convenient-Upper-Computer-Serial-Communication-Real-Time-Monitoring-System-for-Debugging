# -*- coding: utf-8 -*-
"""
STM32 上位机监视程序 - 主窗口
"""

import os
import sys
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QComboBox, QTextEdit, QLineEdit,
    QGroupBox, QGridLayout, QScrollArea, QFrame, QSlider,
    QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QProgressBar, QStatusBar, QToolBar,
    QAction, QSplitter
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QColor

from core.serial_comm import SerialManager
from core.code_generator import CodeGenerator
from core.project_injector import ProjectInjector


class SerialConnectWorker(QThread):
    """串口连接工作线程"""
    connected = pyqtSignal(bool, str)  # connected, message
    
    def __init__(self, serial_manager, port, baudrate):
        super().__init__()
        self.serial_manager = serial_manager
        self.port = port
        self.baudrate = baudrate
    
    def run(self):
        try:
            success = self.serial_manager.connect(self.port, self.baudrate)
            if success:
                self.connected.emit(True, f"已连接到 {self.port}")
            else:
                self.connected.emit(False, "连接失败")
        except Exception as e:
            self.connected.emit(False, f"连接错误: {str(e)}")


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        
        # 初始化组件
        self.serial_manager = SerialManager()
        self.code_generator = None
        self.connect_worker = None
        
        # 引脚状态存储
        self.pin_status = {}
        
        # UI 初始化
        self.init_ui()
        
        # 信号连接
        self.setup_signals()
        
        # 定时刷新
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_pin_status)
        
    def init_ui(self):
        """初始化 UI"""
        self.setWindowTitle("STM32 上位机监视程序 v1.0")
        self.setGeometry(100, 100, 1200, 800)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 创建工具栏
        self.create_toolbar()
        
        # 创建标签页
        self.tabs = QTabWidget()
        
        # 1. 串口连接页
        self.tab_connection = self.create_connection_tab()
        self.tabs.addTab(self.tab_connection, "串口连接")
        
        # 2. 引脚状态页
        self.tab_pins = self.create_pins_tab()
        self.tabs.addTab(self.tab_pins, "引脚状态")
        
        # 3. PWM 控制页
        self.tab_pwm = self.create_pwm_tab()
        self.tabs.addTab(self.tab_pwm, "PWM 控制")
        
        # 4. 代码生成页
        self.tab_code = self.create_code_tab()
        self.tabs.addTab(self.tab_code, "代码生成")
        
        # 5. 串口日志页
        self.tab_log = self.create_log_tab()
        self.tabs.addTab(self.tab_log, "通信日志")
        
        # 6. 使用教程页
        self.tab_tutorial = self.create_tutorial_tab()
        self.tabs.addTab(self.tab_tutorial, "使用教程")
        
        main_layout.addWidget(self.tabs)
        
        # 状态栏
        self.statusBar().showMessage("就绪")
        
        # 自动刷新串口列表
        self.refresh_ports()
        
    def create_toolbar(self):
        """创建工具栏"""
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        # 打开工程
        action_open = QAction("打开工程", self)
        action_open.triggered.connect(self.open_project)
        toolbar.addAction(action_open)
        
        # 导入工程并注入代码
        action_inject = QAction("导入工程 + 添加通信代码", self)
        action_inject.triggered.connect(self.inject_project_code)
        toolbar.addAction(action_inject)
        
        toolbar.addSeparator()
        
        # 刷新串口
        action_refresh = QAction("刷新串口", self)
        action_refresh.triggered.connect(self.refresh_ports)
        toolbar.addAction(action_refresh)
        
    def create_connection_tab(self) -> QWidget:
        """创建串口连接页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 连接控制组
        group = QGroupBox("串口连接")
        group_layout = QHBoxLayout()
        
        # 串口选择
        layout.addWidget(QLabel("串口:"))
        self.combo_port = QComboBox()
        self.combo_port.setMinimumWidth(150)
        group_layout.addWidget(self.combo_port)
        
        # 波特率
        group_layout.addWidget(QLabel("波特率:"))
        self.combo_baud = QComboBox()
        self.combo_baud.addItems(['9600', '19200', '38400', '57600', '115200', '230400'])
        self.combo_baud.setCurrentText('115200')
        group_layout.addWidget(self.combo_baud)
        
        # 连接按钮
        self.btn_connect = QPushButton("连接")
        self.btn_connect.clicked.connect(self.toggle_connection)
        group_layout.addWidget(self.btn_connect)
        
        # 测试连接按钮
        self.btn_test = QPushButton("测试通信")
        self.btn_test.clicked.connect(self.test_connection)
        self.btn_test.setEnabled(False)
        group_layout.addWidget(self.btn_test)
        
        # 刷新按钮
        btn_refresh = QPushButton("刷新")
        btn_refresh.clicked.connect(self.refresh_ports)
        group_layout.addWidget(btn_refresh)
        
        group_layout.addStretch()
        group.setLayout(group_layout)
        layout.addWidget(group)
        
        # 连接状态
        self.label_status = QLabel("未连接")
        self.label_status.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.label_status)
        
        # 快捷指令
        group_cmd = QGroupBox("快捷指令")
        group_cmd_layout = QVBoxLayout()
        
        # 指令输入
        h_layout = QHBoxLayout()
        h_layout.addWidget(QLabel("指令:"))
        self.edit_command = QLineEdit()
        self.edit_command.setPlaceholderText("输入指令，如: GET_ALL, SET_PA1,HIGH")
        self.edit_command.returnPressed.connect(self.send_command)
        h_layout.addWidget(self.edit_command)
        
        btn_send = QPushButton("发送")
        btn_send.clicked.connect(self.send_command)
        h_layout.addWidget(btn_send)
        
        group_cmd_layout.addLayout(h_layout)
        
        # 预设按钮
        preset_layout = QHBoxLayout()
        presets = [
            ("获取全部状态", "GET_ALL"),
            ("读取PA0", "GET_PA0"),
            ("设置PA1高", "SET_PA1,HIGH"),
            ("设置PA1低", "SET_PA1,LOW"),
            ("PWM PA0 50%", "PWM_PA0,50"),
        ]
        for name, cmd in presets:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, c=cmd: self.edit_command.setText(c))
            preset_layout.addWidget(btn)
        
        group_cmd_layout.addLayout(preset_layout)
        group_cmd.setLayout(group_cmd_layout)
        layout.addWidget(group_cmd)
        
        layout.addStretch()
        
        return widget
    
    def create_pins_tab(self) -> QWidget:
        """创建引脚状态页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 控制按钮
        btn_layout = QHBoxLayout()
        self.btn_refresh_status = QPushButton("刷新状态")
        self.btn_refresh_status.clicked.connect(self.refresh_pin_status)
        btn_layout.addWidget(self.btn_refresh_status)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 引脚状态表格
        self.pin_table = QTableWidget()
        self.pin_table.setColumnCount(5)
        self.pin_table.setHorizontalHeaderLabels(['引脚', '状态', '模式', '最后更新', '操作'])
        self.pin_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.pin_table)
        
        # 初始化引脚列表
        self.init_pin_table()
        
        return widget
    
    def init_pin_table(self):
        """初始化引脚表格"""
        pins = []
        for port in ['A', 'B', 'C']:
            for num in range(16):
                pins.append(f'P{port}{num}')
        
        self.pin_table.setRowCount(len(pins))
        
        for i, pin in enumerate(pins):
            # 引脚名称
            self.pin_table.setItem(i, 0, QTableWidgetItem(pin))
            
            # 状态
            status_item = QTableWidgetItem('UNKNOWN')
            status_item.setBackground(QColor(200, 200, 200))
            self.pin_table.setItem(i, 1, status_item)
            
            # 模式
            mode_item = QTableWidgetItem('INPUT')
            self.pin_table.setItem(i, 2, mode_item)
            
            # 最后更新
            self.pin_table.setItem(i, 3, QTableWidgetItem('-'))
            
            # 操作按钮
            btn_widget = QWidget()
            btn_layout = QHBoxLayout()
            btn_layout.setContentsMargins(0, 0, 0, 0)
            
            btn_high = QPushButton("高")
            btn_high.setFixedWidth(40)
            btn_high.clicked.connect(lambda checked, p=pin: self.set_pin_high(p))
            btn_layout.addWidget(btn_high)
            
            btn_low = QPushButton("低")
            btn_low.setFixedWidth(40)
            btn_low.clicked.connect(lambda checked, p=pin: self.set_pin_low(p))
            btn_layout.addWidget(btn_low)
            
            btn_widget.setLayout(btn_layout)
            self.pin_table.setCellWidget(i, 4, btn_widget)
            
            self.pin_status[pin] = {'status': None, 'mode': 'INPUT'}
    
    def create_pwm_tab(self) -> QWidget:
        """创建 PWM 控制页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # PWM 引脚选择
        h_layout = QHBoxLayout()
        h_layout.addWidget(QLabel("PWM 引脚:"))
        self.combo_pwm_pin = QComboBox()
        self.combo_pwm_pin.addItems([
            'PA0', 'PA1', 'PA2', 'PA3', 'PA6', 'PA7', 'PB0', 'PB1'
        ])
        h_layout.addWidget(self.combo_pwm_pin)
        
        h_layout.addStretch()
        layout.addLayout(h_layout)
        
        # PWM 滑块
        group = QGroupBox("PWM 占空比控制")
        group_layout = QVBoxLayout()
        
        self.slider_pwm = QSlider(Qt.Horizontal)
        self.slider_pwm.setMinimum(0)
        self.slider_pwm.setMaximum(100)
        self.slider_pwm.setValue(50)
        self.slider_pwm.valueChanged.connect(self.pwm_slider_changed)
        group_layout.addWidget(self.slider_pwm)
        
        self.label_pwm_value = QLabel("50%")
        self.label_pwm_value.setAlignment(Qt.AlignCenter)
        self.label_pwm_value.setStyleSheet("font-size: 24px; font-weight: bold;")
        group_layout.addWidget(self.label_pwm_value)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_apply = QPushButton("应用到 STM32")
        btn_apply.clicked.connect(self.apply_pwm)
        btn_layout.addWidget(btn_apply)
        
        btn_set_zero = QPushButton("设置 0%")
        btn_set_zero.clicked.connect(lambda: self.slider_pwm.setValue(0))
        btn_layout.addWidget(btn_set_zero)
        
        btn_set_half = QPushButton("设置 50%")
        btn_set_half.clicked.connect(lambda: self.slider_pwm.setValue(50))
        btn_layout.addWidget(btn_set_half)
        
        btn_set_full = QPushButton("设置 100%")
        btn_set_full.clicked.connect(lambda: self.slider_pwm.setValue(100))
        btn_layout.addWidget(btn_set_full)
        
        group_layout.addLayout(btn_layout)
        group.setLayout(group_layout)
        layout.addWidget(group)
        
        # PWM 预览
        self.edit_pwm_preview = QTextEdit()
        self.edit_pwm_preview.setReadOnly(True)
        self.edit_pwm_preview.setMaximumHeight(150)
        group_preview = QGroupBox("生成的 PWM 代码预览")
        group_preview_layout = QVBoxLayout()
        group_preview_layout.addWidget(self.edit_pwm_preview)
        group_preview.setLayout(group_preview_layout)
        layout.addWidget(group_preview)
        
        layout.addStretch()
        
        # 初始预览
        self.update_pwm_preview()
        
        return widget
    
    def create_code_tab(self) -> QWidget:
        """创建代码生成页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 工程路径
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("工程路径:"))
        self.edit_project_path = QLineEdit()
        self.edit_project_path.setReadOnly(True)
        path_layout.addWidget(self.edit_project_path)
        
        btn_browse = QPushButton("浏览")
        btn_browse.clicked.connect(self.open_project)
        path_layout.addWidget(btn_browse)
        
        layout.addLayout(path_layout)
        
        # 代码生成选项
        options_group = QGroupBox("代码生成选项")
        options_layout = QGridLayout()
        
        # 引脚选择
        options_layout.addWidget(QLabel("GPIO 引脚:"), 0, 0)
        self.combo_gpio_pin = QComboBox()
        pins = []
        for port in ['A', 'B', 'C']:
            for num in range(16):
                pins.append(f'P{port}{num}')
        self.combo_gpio_pin.addItems(pins)
        options_layout.addWidget(self.combo_gpio_pin, 0, 1)
        
        # 模式选择
        options_layout.addWidget(QLabel("模式:"), 0, 2)
        self.combo_gpio_mode = QComboBox()
        self.combo_gpio_mode.addItems(['OUT (推挽输出)', 'IN (浮空输入)', 'PU (上拉输入)'])
        options_layout.addWidget(self.combo_gpio_mode, 0, 3)
        
        # 生成 GPIO 按钮
        btn_gen_gpio = QPushButton("生成 GPIO 代码")
        btn_gen_gpio.clicked.connect(self.generate_gpio_code)
        options_layout.addWidget(btn_gen_gpio, 0, 4)
        
        # PWM 引脚
        options_layout.addWidget(QLabel("PWM 引脚:"), 1, 0)
        self.combo_pwm_select = QComboBox()
        self.combo_pwm_select.addItems(['PA0', 'PA1', 'PA2', 'PA3', 'PA6', 'PA7', 'PB0', 'PB1'])
        options_layout.addWidget(self.combo_pwm_select, 1, 1)
        
        # PWM 频率
        options_layout.addWidget(QLabel("频率(Hz):"), 1, 2)
        self.edit_pwm_freq = QLineEdit('50')
        options_layout.addWidget(self.edit_pwm_freq, 1, 3)
        
        # 生成 PWM 按钮
        btn_gen_pwm = QPushButton("生成 PWM 代码")
        btn_gen_pwm.clicked.connect(self.generate_pwm_code)
        options_layout.addWidget(btn_gen_pwm, 1, 4)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # 代码预览
        self.edit_code_preview = QTextEdit()
        self.edit_code_preview.setFont(QFont("Courier New", 10))
        group_preview = QGroupBox("代码预览")
        group_preview_layout = QVBoxLayout()
        group_preview_layout.addWidget(self.edit_code_preview)
        group_preview.setLayout(group_preview_layout)
        layout.addWidget(group_preview)
        
        # 保存按钮
        btn_save_layout = QHBoxLayout()
        btn_save = QPushButton("保存代码文件")
        btn_save.clicked.connect(self.save_generated_code)
        btn_save_layout.addWidget(btn_save)
        btn_save_layout.addStretch()
        layout.addLayout(btn_save_layout)
        
        return widget
    
    def create_log_tab(self) -> QWidget:
        """创建日志页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_clear = QPushButton("清空日志")
        btn_clear.clicked.connect(lambda: self.edit_log.clear())
        btn_layout.addWidget(btn_clear)
        
        btn_save = QPushButton("保存日志")
        btn_save.clicked.connect(self.save_log)
        btn_layout.addWidget(btn_save)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 日志文本框
        self.edit_log = QTextEdit()
        self.edit_log.setReadOnly(True)
        self.edit_log.setFont(QFont("Courier New", 9))
        layout.addWidget(self.edit_log)
        
        return widget
    
    def create_tutorial_tab(self) -> QWidget:
        """创建使用教程页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 教程文本
        tutorial_text = """
<h1>STM32 上位机监视程序 - 使用教程</h1>

<h2>一、准备工作</h2>
<ol>
<li><b>硬件准备：</b>
    <ul>
        <li>STM32F103 开发板</li>
        <li>USB 转 TTL 串口模块 (CH340/CH341)</li>
        <li>杜邦线若干</li>
    </ul>
</li>
<li><b>接线：</b>
    <ul>
        <li>STM32 USART1 TX (PA9) → USB模块 RX</li>
        <li>STM32 USART1 RX (PA10) → USB模块 TX</li>
        <li>GND → GND</li>
        <li>（可选）5V → 5V（供电）</li>
    </ul>
</li>
<li><b>STM32 程序烧录：</b>
    <ul>
        <li>打开 Keil 工程</li>
        <li>确保已添加 USART_Comm.c/h 文件</li>
        <li>编译并烧录到 STM32</li>
    </ul>
</li>
</ol>

<h2>二、快速开始</h2>
<ol>
<li><b>启动软件：</b> 双击 <code>run_venv.bat</code> 或运行 <code>venv\Scripts\python.exe main.py</code></li>
<li><b>选择串口：</b> 在"串口连接"页面，选择 COM 端口（如 COM3）</li>
<li><b>设置波特率：</b> 默认 115200</li>
<li><b>点击连接：</b> 如果连接成功，状态会显示绿色"已连接到 COMX"</li>
<li><b>测试通信：</b> 在指令框输入 <code>GET_ALL</code> 并发送，应该收到 <code>STATUS,OK</code></li>
</ol>

<h2>三、各功能介绍</h2>

<h3>1. 串口连接</h3>
<ul>
<li><b>刷新：</b> 重新扫描可用串口</li>
<li><b>快捷指令：</b> 点击预设按钮快速发送命令</li>
<li><b>自定义指令：</b> 在输入框输入命令，按回车或点击发送</li>
</ul>

<h3>2. 引脚状态</h3>
<ul>
<li><b>刷新状态：</b> 发送 GET_ALL 命令获取所有引脚状态</li>
<li><b>控制引脚：</b> 点击"高"/"低"按钮设置引脚输出</li>
<li><b>实时监控：</b> 连接后自动每秒刷新状态</li>
</ul>

<h3>3. PWM 控制</h3>
<ul>
<li><b>选择引脚：</b> 支持 PA0, PA1, PA2, PA3, PA6, PA7, PB0, PB1</li>
<li><b>调节占空比：</b> 拖动滑块或点击预设按钮</li>
<li><b>发送到 STM32：</b> 点击"应用到 STM32"生效</li>
</ul>

<h3>4. 代码生成</h3>
<ul>
<li><b>GPIO 代码：</b> 选择引脚和模式，生成初始化代码</li>
<li><b>PWM 代码：</b> 选择引脚和频率，生成 PWM 配置代码</li>
<li><b>保存：</b> 点击"保存代码文件"到工程目录</li>
</ul>

<h3>5. 通信日志</h3>
<ul>
<li><b>查看记录：</b> 所有发送和接收的数据都会记录在此</li>
<li><b>清空：</b> 点击"清空日志"清除记录</li>
<li><b>保存：</b> 点击"保存日志"导出到文件</li>
</ul>

<h2>四、命令协议</h2>
<table border="1" cellpadding="5">
<tr><th>命令</th><th>说明</th><th>示例</th></tr>
<tr><td>GET_ALL</td><td>获取所有引脚状态</td><td><code>GET_ALL</code></td></tr>
<tr><td>SET_xx,HIGH/LOW</td><td>设置引脚输出高低</td><td><code>SET_PA1,HIGH</code></td></tr>
<tr><td>PWM_xx,value</td><td>设置 PWM 占空比</td><td><code>PWM_PA0,50</code></td></tr>
<tr><td>CONFIG_xx,mode</td><td>配置引脚模式</td><td><code>CONFIG_PA0,OUT</code></td></tr>
</table>

<h2>五、常见问题</h2>

<h3>Q1: 点击连接后程序卡死</h3>
<b>A:</b> 
<ul>
<li>检查串口是否被其他软件占用（串口调试助手、Arduino IDE 等）</li>
<li>关闭其他占用串口的程序后重试</li>
<li>尝试重新插拔 USB 转串口模块</li>
</ul>

<h3>Q2: 发送命令后无响应</h3>
<b>A:</b>
<ul>
<li>确认 STM32 已烧录 USART 通信代码</li>
<li>检查接线是否正确（TX↔RX 交叉）</li>
<li>确认波特率匹配（115200）</li>
</ul>

<h3>Q3: 串口列表为空</h3>
<b>A:</b>
<ul>
<li>检查 USB 转串口模块是否插好</li>
<li>安装 CH340/CH341 驱动</li>
<li>在设备管理器中查看 COM 端口</li>
</ul>

<h3>Q4: 引脚控制无效</h3>
<b>A:</b>
<ul>
<li>确认引脚在 STM32 代码中已配置为输出模式</li>
<li>检查引脚是否被其他外设占用</li>
</ul>

<h2>六、技术支持</h2>
<p>如有问题，请检查：</p>
<ul>
<li>STM32 与 USB 模块共地（GND 连接）</li>
<li>电压匹配（3.3V 或 5V）</li>
<li>串口参数：115200, 8N1</li>
</ul>

<hr>
<p><i>STM32 上位机监视程序 v1.0</i></p>
"""
        
        # 教程显示区域
        browser = QTextEdit()
        browser.setHtml(tutorial_text)
        browser.setReadOnly(True)
        browser.setFont(QFont("微软雅黑", 10))
        layout.addWidget(browser)
        
        return widget
    
    def setup_signals(self):
        """设置信号连接"""
        self.serial_manager.data_received.connect(self.on_data_received)
        self.serial_manager.connection_status.connect(self.on_connection_changed)
        self.serial_manager.error_occurred.connect(self.on_error)
        
    @pyqtSlot(bool, str)
    def on_connection_changed(self, connected, message):
        """连接状态改变"""
        self.label_status.setText(message)
        if connected:
            self.label_status.setStyleSheet("color: green; font-weight: bold;")
            self.btn_connect.setText("断开")
            self.btn_test.setEnabled(True)
            self.statusBar().showMessage(message)
            # 开始定时刷新
            self.refresh_timer.start(3000)  # 每3秒刷新
        else:
            self.label_status.setStyleSheet("color: red; font-weight: bold;")
            self.btn_connect.setText("连接")
            self.btn_test.setEnabled(False)
            self.statusBar().showMessage(message)
            self.refresh_timer.stop()
    
    @pyqtSlot(str)
    def on_data_received(self, data):
        """收到数据"""
        # 添加到日志
        self.log_message(f"← {data}")
        
        # 解析状态更新
        self.parse_status(data)
    
    @pyqtSlot(str)
    def on_error(self, error):
        """错误发生"""
        self.log_message(f"错误: {error}")
        QMessageBox.warning(self, "错误", error)
    
    def log_message(self, msg):
        """添加日志消息"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.edit_log.append(f"[{timestamp}] {msg}")
        
        # 切换到日志页
        # self.tabs.setCurrentWidget(self.tab_log)
    
    def parse_status(self, data):
        """解析状态数据"""
        # 格式: STATUS,PA0:HIGH,PA1:LOW,...
        if data.startswith("STATUS,"):
            parts = data[7:].split(',')
            for part in parts:
                if ':' in part:
                    pin, status = part.split(':')
                    if pin in self.pin_status:
                        self.pin_status[pin]['status'] = status
                        self.update_pin_display(pin, status)
    
    def update_pin_display(self, pin, status):
        """更新引脚显示"""
        # 查找行
        for i in range(self.pin_table.rowCount()):
            item = self.pin_table.item(i, 0)
            if item and item.text() == pin:
                # 更新状态
                status_item = self.pin_table.item(i, 1)
                if status_item:
                    status_item.setText(status)
                    if status == 'HIGH':
                        status_item.setBackground(QColor(100, 255, 100))
                    elif status == 'LOW':
                        status_item.setBackground(QColor(255, 100, 100))
                    else:
                        status_item.setBackground(QColor(200, 200, 200))
                
                # 更新时间
                from datetime import datetime
                self.pin_table.item(i, 3).setText(datetime.now().strftime("%H:%M:%S"))
                break
    
    def refresh_pin_status(self):
        """刷新引脚状态"""
        if self.serial_manager.is_connected:
            self.serial_manager.get_all_pin_status()
            self.log_message("→ GET_ALL")
    
    def refresh_ports(self):
        """刷新串口列表"""
        ports = self.serial_manager.get_available_ports()
        self.combo_port.clear()
        for port, desc in ports:
            self.combo_port.addItem(port, desc)
    
    def toggle_connection(self):
        """切换连接状态"""
        if self.serial_manager.is_connected:
            self.serial_manager.disconnect()
        else:
            port = self.combo_port.currentText()
            if not port:
                QMessageBox.warning(self, "警告", "请先选择串口！\n点击'刷新'按钮获取可用串口列表")
                return
            
            # 禁用按钮防止重复点击
            self.btn_connect.setEnabled(False)
            self.btn_connect.setText("连接中...")
            
            baudrate = int(self.combo_baud.currentText())
            
            # 使用工作线程连接，避免阻塞 GUI
            self.connect_worker = SerialConnectWorker(self.serial_manager, port, baudrate)
            self.connect_worker.connected.connect(self.on_connect_finished)
            self.connect_worker.start()
    
    def on_connect_finished(self, success, message):
        """连接完成回调"""
        self.btn_connect.setEnabled(True)
        self.btn_connect.setText("连接")
        if success:
            self.btn_test.setEnabled(True)
        else:
            self.btn_test.setEnabled(False)
            self.label_status.setText(message if message else "连接失败")
            self.statusBar().showMessage(message if message else "连接失败")
    
    def test_connection(self):
        """测试连接 - 发送命令并等待响应"""
        if self.serial_manager.is_connected:
            self.log_message("→ [测试通信]")
            self.serial_manager.send_command("GET_ALL")
    
    def send_command(self):
        """发送指令"""
        cmd = self.edit_command.text().strip()
        if cmd:
            if self.serial_manager.send_command(cmd):
                self.log_message(f"→ {cmd}")
            self.edit_command.clear()
    
    def check_pin_configured(self, pin, mode='OUT') -> bool:
        """检查引脚是否已配置，如果没有则生成代码并提示"""
        if not self.code_generator:
            # 没有加载工程，提示用户先加载
            reply = QMessageBox.question(
                self,
                "未加载工程",
                f"控制 {pin} 引脚需要先配置工程代码。\n\n"
                f"是否现在选择工程目录并配置 {pin}？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                self.open_project()
                if self.code_generator:
                    return self.check_pin_configured(pin, mode)
            return False
        
        try:
            # 检查引脚是否已配置
            configured = self.code_generator.is_pin_configured(pin)
            if not configured:
                # 未配置，生成代码
                reply = QMessageBox.question(
                    self,
                    "引脚未配置",
                    f"{pin} 引脚尚未配置为 {mode} 模式！\n\n"
                    f"程序将自动生成 {pin} 的配置代码并保存到工程。\n"
                    f"然后请在 Keil 中编译并下载到 STM32。\n\n"
                    f"是否继续？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                
                if reply == QMessageBox.Yes:
                    # 生成 GPIO 代码
                    if mode == 'OUT':
                        self.code_generator.generate_gpio_init(pin, 'OUT')
                    self.code_generator.save_gpio_files(pin)
                    
                    QMessageBox.information(
                        self,
                        "代码已生成",
                        f"已将 {pin} 配置代码保存到工程目录。\n\n"
                        f"请执行以下步骤：\n"
                        f"1. 打开 Keil 工程\n"
                        f"2. 编译并下载到 STM32\n"
                        f"3. 回到上位机点击连接\n\n"
                        f"工程路径：{self.code_generator.project_path}"
                    )
                    return False
            return True
        except Exception as e:
            QMessageBox.warning(self, "错误", f"检查配置失败：{str(e)}")
            return False
    
    def check_pwm_configured(self, pin) -> bool:
        """检查 PWM 引脚是否已配置"""
        if not self.code_generator:
            reply = QMessageBox.question(
                self,
                "未加载工程",
                f"控制 {pin} PWM 需要先配置工程代码。\n\n"
                f"是否现在选择工程目录？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                self.open_project()
                if self.code_generator:
                    return self.check_pwm_configured(pin)
            return False
        
        try:
            configured = self.code_generator.is_pin_configured(pin)
            if not configured:
                reply = QMessageBox.question(
                    self,
                    "PWM 未配置",
                    f"{pin} 引脚尚未配置为 PWM 模式！\n\n"
                    f"程序将自动生成 PWM 配置代码。\n"
                    f"是否继续？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                
                if reply == QMessageBox.Yes:
                    self.code_generator.generate_pwm_init(pin)
                    self.code_generator.save_pwm_files(pin)
                    
                    QMessageBox.information(
                        self,
                        "代码已生成",
                        f"已将 {pin} PWM 配置代码保存到工程。\n\n"
                        f"请在 Keil 中编译并下载到 STM32。"
                    )
                    return False
            return True
        except Exception as e:
            QMessageBox.warning(self, "错误", f"检查配置失败：{str(e)}")
            return False
    
    def set_pin_high(self, pin):
        """设置引脚高"""
        if not self.serial_manager.is_connected:
            QMessageBox.warning(self, "警告", "请先连接串口！")
            return
        
        # 检查引脚是否已配置
        if not self.check_pin_configured(pin, 'OUT'):
            return
        
        self.serial_manager.set_pin(pin, 'HIGH')
        self.log_message(f"→ SET_{pin},HIGH")
    
    def set_pin_low(self, pin):
        """设置引脚低"""
        if not self.serial_manager.is_connected:
            QMessageBox.warning(self, "警告", "请先连接串口！")
            return
        
        # 检查引脚是否已配置
        if not self.check_pin_configured(pin, 'OUT'):
            return
        
        self.serial_manager.set_pin(pin, 'LOW')
        self.log_message(f"→ SET_{pin},LOW")
    
    def pwm_slider_changed(self, value):
        """PWM 滑块改变"""
        self.label_pwm_value.setText(f"{value}%")
        self.update_pwm_preview()
    
    def update_pwm_preview(self):
        """更新 PWM 预览"""
        pin = self.combo_pwm_pin.currentText()
        value = self.slider_pwm.value()
        
        if self.code_generator:
            try:
                code = self.code_generator.generate_pwm_init(pin)
                self.edit_pwm_preview.setPlainText(code)
            except Exception as e:
                self.edit_pwm_preview.setPlainText(f"错误: {str(e)}")
        else:
            self.edit_pwm_preview.setPlainText(f"请先选择工程路径")
    
    def apply_pwm(self):
        """应用 PWM 到 STM32"""
        if not self.serial_manager.is_connected:
            QMessageBox.warning(self, "警告", "请先连接串口！\n在'串口连接'页面选择串口并点击'连接'")
            self.tabs.setCurrentWidget(self.tab_connection)
            return
        
        pin = self.combo_pwm_pin.currentText()
        
        # 检查 PWM 是否已配置
        if not self.check_pwm_configured(pin):
            return
        
        value = self.slider_pwm.value()
        self.serial_manager.set_pwm(pin, value)
        self.log_message(f"→ PWM_{pin},{value}")
    
    def open_project(self):
        """打开工程"""
        path = QFileDialog.getExistingDirectory(self, "选择工程目录")
        if path:
            self.edit_project_path.setText(path)
            self.code_generator = CodeGenerator(path)
            self.statusBar().showMessage(f"已加载工程: {path}")
            self.log_message(f"加载工程: {path}")
    
    def generate_gpio_code(self):
        """生成 GPIO 代码"""
        if not self.code_generator:
            QMessageBox.warning(self, "警告", "请先选择工程路径")
            return
        
        pin = self.combo_gpio_pin.currentText()
        mode_text = self.combo_gpio_mode.currentText()
        mode = mode_text.split()[0]  # 获取 OUT, IN, 或 PU
        
        try:
            code = self.code_generator.generate_gpio_init(pin, mode)
            self.edit_code_preview.setPlainText(code)
            self.generated_code = code
            self.generated_pin = pin
            self.generated_type = 'GPIO'
        except Exception as e:
            QMessageBox.warning(self, "错误", str(e))
    
    def generate_pwm_code(self):
        """生成 PWM 代码"""
        if not self.code_generator:
            QMessageBox.warning(self, "警告", "请先选择工程路径")
            return
        
        pin = self.combo_pwm_select.currentText()
        freq = int(self.edit_pwm_freq.text())
        
        try:
            code = self.code_generator.generate_pwm_init(pin, freq)
            self.edit_code_preview.setPlainText(code)
            self.generated_code = code
            self.generated_pin = pin
            self.generated_type = 'PWM'
        except Exception as e:
            QMessageBox.warning(self, "错误", str(e))
    
    def save_generated_code(self):
        """保存生成的代码"""
        if not hasattr(self, 'generated_code'):
            QMessageBox.warning(self, "警告", "请先生成代码")
            return
        
        try:
            if self.generated_type == 'GPIO':
                c_file, h_file = self.code_generator.save_gpio_files(self.generated_pin)
            else:
                c_file, h_file = self.code_generator.save_pwm_files(self.generated_pin)
            
            QMessageBox.information(self, "成功", f"代码已保存到:\n{c_file}\n{h_file}")
            self.log_message(f"保存代码: {c_file}, {h_file}")
        except Exception as e:
            QMessageBox.warning(self, "错误", str(e))
    
    def save_log(self):
        """保存日志"""
        path, _ = QFileDialog.getSaveFileName(self, "保存日志", "serial_log.txt", "Text Files (*.txt)")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.edit_log.toPlainText())
            QMessageBox.information(self, "成功", "日志已保存")
    
    def inject_project_code(self):
        """导入工程并注入通信代码"""
        # 选择工程目录
        path = QFileDialog.getExistingDirectory(self, "选择 STM32 工程目录")
        if not path:
            return
        
        # 检查是否是有效的 Keil 工程
        injector = ProjectInjector(path)
        
        if not injector.is_valid_project():
            QMessageBox.warning(
                self, 
                "无效工程", 
                "未找到 Keil 工程文件 (.uvprojx)\n请选择正确的工程目录"
            )
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认导入",
            "此操作将：\n\n"
            "1. 在 User 目录创建 USART_Comm.c 和 USART_Comm.h\n"
            "2. 修改 main.c 添加串口初始化\n"
            "3. 将新文件添加到 Keil 工程\n\n"
            "是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 执行注入
        try:
            results = injector.inject_communication_code()
            
            # 显示结果
            msg = "代码注入成功！\n\n已创建/修改的文件：\n"
            for r in results:
                msg += f"• {os.path.basename(r)}\n"
            
            msg += "\n请重新编译工程并下载到 STM32！"
            
            QMessageBox.information(self, "成功", msg)
            self.log_message(f"工程代码注入成功: {path}")
            
            # 自动加载工程
            self.edit_project_path.setText(path)
            self.code_generator = CodeGenerator(path)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"代码注入失败:\n{str(e)}")
            self.log_message(f"工程代码注入失败: {str(e)}")
