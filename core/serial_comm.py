# -*- coding: utf-8 -*-
"""
STM32 串口通信模块
处理与 STM32 的串口通信
"""

import serial
import serial.tools.list_ports
import threading
import time
from PyQt5.QtCore import QObject, pyqtSignal


class SerialManager(QObject):
    """串口管理器"""
    
    # 信号定义
    data_received = pyqtSignal(str)           # 收到数据
    connection_status = pyqtSignal(bool, str)  # 连接状态变化
    error_occurred = pyqtSignal(str)           # 错误发生
    
    def __init__(self):
        super().__init__()
        self.serial_port = None
        self.is_connected = False
        self.receive_thread = None
        self.running = False
        self.read_buffer = ""
        
    def get_available_ports(self):
        """获取可用串口列表"""
        ports = serial.tools.list_ports.comports()
        return [(port.device, port.description) for port in ports]
    
    def connect(self, port, baudrate=115200, timeout=1):
        """连接串口"""
        try:
            if self.is_connected:
                self.disconnect()
            
            # 直接打开串口（不尝试预关闭，避免阻塞）
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                timeout=3,
                write_timeout=3,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            
            # 清空缓冲区
            self.serial_port.flushInput()
            self.serial_port.flushOutput()
            
            self.is_connected = True
            self.running = True
            
            # 启动接收线程
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()
            
            self.connection_status.emit(True, f"已连接到 {port}")
            return True
            
        except serial.SerialException as e:
            self.error_occurred.emit(f"连接失败: {str(e)}")
            return False
        except Exception as e:
            self.error_occurred.emit(f"连接错误: {str(e)}")
            return False
    
    def disconnect(self):
        """断开串口连接"""
        self.running = False
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.is_connected = False
        self.connection_status.emit(False, "已断开连接")
    
    def send_command(self, command):
        """发送命令"""
        if not self.is_connected or not self.serial_port:
            self.error_occurred.emit("未连接串口")
            return False
        
        # 重试机制
        for attempt in range(3):
            try:
                # 添加换行符
                cmd = command.strip() + '\r\n'
                self.serial_port.write(cmd.encode('utf-8'))
                self.serial_port.flush()
                return True
            except Exception as e:
                if attempt < 2:
                    time.sleep(0.1)
                    continue
                self.error_occurred.emit(f"发送失败: {str(e)}")
                return False
    
    def _receive_loop(self):
        """接收数据循环"""
        while self.running and self.serial_port:
            try:
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    text = data.decode('utf-8', errors='ignore')
                    self.read_buffer += text
                    
                    # 处理完整命令（以换行符结尾）
                    while '\n' in self.read_buffer:
                        line, self.read_buffer = self.read_buffer.split('\n', 1)
                        line = line.strip()
                        if line:
                            self.data_received.emit(line)
                            
            except Exception as e:
                if self.running:
                    self.error_occurred.emit(f"接收错误: {str(e)}")
                break
            time.sleep(0.05)
    
    def get_all_pin_status(self):
        """获取所有引脚状态"""
        return self.send_command("GET_ALL")
    
    def set_pin(self, pin, state):
        """设置引脚状态"""
        # pin: "PA0", state: "HIGH" or "LOW"
        return self.send_command(f"SET_{pin},{state}")
    
    def set_pwm(self, pin, value):
        """设置 PWM"""
        # pin: "PA0", value: 0-100
        return self.send_command(f"PWM_{pin},{value}")
    
    def config_pin(self, pin, mode):
        """配置引脚模式"""
        # pin: "PA0", mode: "IN", "OUT", "PWM", "AIN"
        return self.send_command(f"CONFIG_{pin},{mode}")
