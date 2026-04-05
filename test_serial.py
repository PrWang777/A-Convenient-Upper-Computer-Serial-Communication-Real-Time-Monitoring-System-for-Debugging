#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单串口测试工具
直接测试 STM32 串口通信
"""

import serial
import time
import sys

# 配置
PORT = 'COM3'
BAUDRATE = 115200
TIMEOUT = 3

def send_command(ser, cmd):
    """发送命令并显示响应"""
    print(f"-> {cmd}")
    ser.write((cmd + '\r\n').encode('utf-8'))
    time.sleep(0.5)
    
    # 读取响应
    response = b""
    start = time.time()
    while time.time() - start < 2:
        if ser.in_waiting:
            response += ser.read(ser.in_waiting)
        time.sleep(0.1)
    
    if response:
        print(f"<- {response.decode('utf-8', errors='ignore').strip()}")
    else:
        print("<- (no response)")
    print()

def test_basic():
    """基本通信测试"""
    print("=== Basic Communication Test ===\n")
    send_command(serial.Serial(PORT, BAUDRATE, timeout=TIMEOUT), "GET_ALL")

def test_pin_control():
    """引脚控制测试"""
    print("=== Pin Control Test ===\n")
    ser = serial.Serial(PORT, BAUDRATE, timeout=TIMEOUT)
    time.sleep(0.5)
    ser.flushInput()
    
    # 测试 SET 命令
    send_command(ser, "SET_PA1,HIGH")
    send_command(ser, "SET_PA1,LOW")
    
    # 测试 PWM 命令
    send_command(ser, "PWM_PA0,50")
    send_command(ser, "PWM_PA0,100")
    
    ser.close()

def interactive():
    """交互模式"""
    print("=== Interactive Mode ===")
    print("Commands: GET_ALL, SET_Pxx,HIGH/LOW, PWM_Pxx,value")
    print("Type 'quit' to exit\n")
    
    ser = serial.Serial(PORT, BAUDRATE, timeout=TIMEOUT)
    time.sleep(0.5)
    ser.flushInput()
    
    while True:
        cmd = input("Command> ").strip()
        if not cmd:
            continue
        if cmd.lower() == 'quit':
            break
        
        send_command(ser, cmd)
    
    ser.close()

def main():
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        if mode == 'pin':
            test_pin_control()
        elif mode == 'test':
            test_basic()
        else:
            interactive()
    else:
        test_basic()
    
    print("\n=== Test Complete ===")

if __name__ == '__main__':
    try:
        main()
    except serial.SerialException as e:
        print(f"[X] Error: {e}")
    except KeyboardInterrupt:
        print("\n[X] Interrupted")
    
    input("\nPress Enter to exit...")
