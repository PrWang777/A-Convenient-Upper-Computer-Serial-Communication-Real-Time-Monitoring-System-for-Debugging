# -*- coding: utf-8 -*-
"""
STM32 工程导入和代码注入器
自动为 Keil 工程添加 USART 通信代码
"""

import os
import re
import xml.etree.ElementTree as ET


class ProjectInjector:
    """工程代码注入器"""
    
    def __init__(self, project_path):
        self.project_path = project_path
        self.user_path = os.path.join(project_path, 'User')
        self.hardware_path = os.path.join(project_path, 'Hardware')
        
        # 查找工程文件
        self.uvprojx = self._find_uvprojx()
        
    def _find_uvprojx(self):
        """查找 Keil 工程文件"""
        for f in os.listdir(self.project_path):
            if f.endswith('.uvprojx'):
                return os.path.join(self.project_path, f)
        return None
    
    def inject_communication_code(self):
        """注入通信代码到工程"""
        results = []
        
        # 1. 生成 USART 通信代码
        usart_files = self._generate_usart_code()
        results.extend(usart_files)
        
        # 2. 修改 main.c 添加命令解析
        main_modified = self._modify_main()
        if main_modified:
            results.append(main_modified)
        
        # 3. 添加文件到工程
        if self.uvprojx:
            self._add_files_to_project(usart_files)
            results.append(f"工程文件已更新: {self.uvprojx}")
        
        return results
    
    def _generate_usart_code(self):
        """生成 USART 通信代码"""
        files_created = []
        
        # USART 头文件
        usart_h = """#ifndef __USART_COMM_H
#define __USART_COMM_H

#include "stm32f10x.h"

void USART_Init(void);
void USART_SendChar(char c);
void USART_SendString(char *str);
void USART_SendData(uint8_t *data, uint16_t len);
void USART_Printf(char *fmt, ...);

// 命令处理
void HandleCommand(char *cmd);

#endif
"""
        
        # USART 源文件
        usart_c = """#include "stm32f10x.h"
#include "USART_Comm.h"
#include <stdio.h>
#include <string.h>
#include <stdarg.h>

// 引脚定义 - USART1 (PA9 TX, PA10 RX)
#define USART_TX_PIN GPIO_Pin_9
#define USART_RX_PIN GPIO_Pin_10
#define USART_GPIO GPIOA

// 接收缓冲区
#define RX_BUF_SIZE 256
static char rx_buffer[RX_BUF_SIZE];
static uint16_t rx_index = 0;

// 串口初始化
void USART_Init(void)
{
    // 开启时钟
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA, ENABLE);
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_USART1, ENABLE);
    
    // GPIO 配置 - PA9 TX (复用推挽输出)
    GPIO_InitTypeDef GPIO_InitStructure;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF_PP;
    GPIO_InitStructure.GPIO_Pin = USART_TX_PIN;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init(USART_GPIO, &GPIO_InitStructure);
    
    // GPIO 配置 - PA10 RX (浮空输入)
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_IN_FLOATING;
    GPIO_InitStructure.GPIO_Pin = USART_RX_PIN;
    GPIO_Init(USART_GPIO, &GPIO_InitStructure);
    
    // 串口配置
    USART_InitTypeDef USART_InitStructure;
    USART_InitStructure.USART_BaudRate = 115200;
    USART_InitStructure.USART_WordLength = USART_WordLength_8b;
    USART_InitStructure.USART_StopBits = USART_StopBits_1;
    USART_InitStructure.USART_Parity = USART_Parity_No;
    USART_InitStructure.USART_HardwareFlowControl = USART_HardwareFlowControl_None;
    USART_InitStructure.USART_Mode = USART_Mode_Rx | USART_Mode_Tx;
    USART_Init(USART1, &USART_InitStructure);
    
    // 使能串口
    USART_Cmd(USART1, ENABLE);
    
    // 使能接收中断
    USART_ITConfig(USART1, USART_IT_RXNE, ENABLE);
    
    // NVIC 配置
    NVIC_InitTypeDef NVIC_InitStructure;
    NVIC_InitStructure.NVIC_IRQChannel = USART1_IRQn;
    NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority = 0;
    NVIC_InitStructure.NVIC_IRQChannelSubPriority = 0;
    NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
    NVIC_Init(&NVIC_InitStructure);
    
    USART_Printf("\\r\\n=== STM32 Ready ===\\r\\n");
    USART_Printf("Commands: GET_ALL, SET_Pxx,HIGH/LOW, PWM_Pxx,value\\r\\n");
}

// 发送单个字符
void USART_SendChar(char c)
{
    while (USART_GetFlagStatus(USART1, USART_FLAG_TC) == RESET);
    USART_SendData(USART1, (uint8_t)c);
}

// 发送字符串
void USART_SendString(char *str)
{
    while (*str)
    {
        USART_SendChar(*str++);
    }
}

// 发送数据
void USART_SendData(uint8_t *data, uint16_t len)
{
    for (uint16_t i = 0; i < len; i++)
    {
        USART_SendChar(data[i]);
    }
}

// 格式化打印
void USART_Printf(char *fmt, ...)
{
    char buffer[256];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buffer, sizeof(buffer), fmt, args);
    va_end(args);
    USART_SendString(buffer);
}

// 串口中断处理
void USART1_IRQHandler(void)
{
    if (USART_GetITStatus(USART1, USART_IT_RXNE) != RESET)
    {
        char c = (char)USART_ReceiveData(USART1);
        
        if (c == '\\r' || c == '\\n')
        {
            if (rx_index > 0)
            {
                rx_buffer[rx_index] = '\\0';
                HandleCommand(rx_buffer);
                rx_index = 0;
            }
        }
        else if (rx_index < RX_BUF_SIZE - 1)
        {
            rx_buffer[rx_index++] = c;
        }
        
        USART_ClearITPendingBit(USART1, USART_IT_RXNE);
    }
}

// 获取引脚状态
void SendAllPinStatus(void)
{
    char status[64];
    char temp[16];
    
    USART_Printf("STATUS,");
    
    // PA0-PA15
    for (int i = 0; i < 16; i++)
    {
        snprintf(temp, sizeof(temp), "PA%d:%d", i, 
            GPIO_ReadInputDataBit(GPIOA, (1 << i)));
        USART_SendString(temp);
        if (i < 15) USART_SendString(",");
    }
    
    // PB0-PB15
    USART_Printf(",");
    for (int i = 0; i < 16; i++)
    {
        snprintf(temp, sizeof(temp), "PB%d:%d", i,
            GPIO_ReadInputDataBit(GPIOB, (1 << i)));
        USART_SendString(temp);
        if (i < 15) USART_SendString(",");
    }
    
    // PC0-PC15
    USART_Printf(",");
    for (int i = 0; i < 16; i++)
    {
        snprintf(temp, sizeof(temp), "PC%d:%d", i,
            GPIO_ReadInputDataBit(GPIOC, (1 << i)));
        USART_SendString(temp);
        if (i < 15) USART_SendString(",");
    }
    
    USART_Printf("\\r\\n");
}

// 解析并执行命令
void HandleCommand(char *cmd)
{
    // 去除空格
    while (*cmd == ' ') cmd++;
    
    // 获取命令类型
    if (strncmp(cmd, "GET_ALL", 7) == 0)
    {
        SendAllPinStatus();
    }
    else if (strncmp(cmd, "GET_", 4) == 0)
    {
        // GET_Pxx
        char *pin = cmd + 4;
        uint16_t gpio_port, gpio_pin;
        
        if (pin[0] == 'P' && pin[1] == 'A')
        {
            gpio_port = (uint32_t)GPIOA;
            gpio_pin = 1 << atoi(pin + 2);
        }
        else if (pin[0] == 'P' && pin[1] == 'B')
        {
            gpio_port = (uint32_t)GPIOB;
            gpio_pin = 1 << atoi(pin + 2);
        }
        else if (pin[0] == 'P' && pin[1] == 'C')
        {
            gpio_port = (uint32_t)GPIOC;
            gpio_pin = 1 << atoi(pin + 2);
        }
        
        uint8_t state = GPIO_ReadInputDataBit((GPIO_TypeDef*)gpio_port, gpio_pin);
        USART_Printf("STATUS,%s:%d\\r\\n", pin, state);
    }
    else if (strncmp(cmd, "SET_", 4) == 0)
    {
        // SET_Pxx,HIGH/LOW
        char *args = cmd + 4;
        char *comma = strchr(args, ',');
        if (comma)
        {
            *comma = '\\0';
            char *pin = args;
            char *state = comma + 1;
            
            GPIO_TypeDef* port;
            uint16_t pin_num = 0;
            
            if (pin[0] == 'P' && pin[1] == 'A')
            {
                port = GPIOA;
                pin_num = 1 << atoi(pin + 2);
            }
            else if (pin[0] == 'P' && pin[1] == 'B')
            {
                port = GPIOB;
                pin_num = 1 << atoi(pin + 2);
            }
            else if (pin[0] == 'P' && pin[1] == 'C')
            {
                port = GPIOC;
                pin_num = 1 << atoi(pin + 2);
            }
            
            if (strcmp(state, "HIGH") == 0)
            {
                GPIO_SetBits(port, pin_num);
                USART_Printf("ACK,OK\\r\\n");
            }
            else if (strcmp(state, "LOW") == 0)
            {
                GPIO_ResetBits(port, pin_num);
                USART_Printf("ACK,OK\\r\\n");
            }
            else
            {
                USART_Printf("ACK,ERR\\r\\n");
            }
        }
        else
        {
            USART_Printf("ACK,ERR\\r\\n");
        }
    }
    else if (strncmp(cmd, "PWM_", 4) == 0)
    {
        // PWM_Pxx,value
        // 注意: 这里需要根据实际的 PWM 配置
        USART_Printf("ACK,OK\\r\\n");
    }
    else if (strncmp(cmd, "CONFIG_", 7) == 0)
    {
        // CONFIG_Pxx,MODE
        USART_Printf("ACK,OK\\r\\n");
    }
    else
    {
        USART_Printf("ACK,ERR\\r\\n");
    }
}
"""
        
        # 写入文件
        usart_h_path = os.path.join(self.user_path, 'USART_Comm.h')
        usart_c_path = os.path.join(self.user_path, 'USART_Comm.c')
        
        with open(usart_h_path, 'w', encoding='utf-8') as f:
            f.write(usart_h)
        files_created.append(usart_h_path)
        
        with open(usart_c_path, 'w', encoding='utf-8') as f:
            f.write(usart_c)
        files_created.append(usart_c_path)
        
        return files_created
    
    def _modify_main(self):
        """修改 main.c 添加初始化调用"""
        main_c_path = os.path.join(self.user_path, 'main.c')
        
        if not os.path.exists(main_c_path):
            return None
        
        with open(main_c_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否已经包含
        if 'USART_Init' in content:
            return None
        
        # 添加头文件引用
        if '#include "USART_Comm.h"' not in content:
            # 找到最后一个 #include 位置
            lines = content.split('\n')
            insert_idx = 0
            for i, line in enumerate(lines):
                if line.startswith('#include'):
                    insert_idx = i + 1
            
            lines.insert(insert_idx, '#include "USART_Comm.h"')
            content = '\n'.join(lines)
        
        # 在 main 函数中添加 USART_Init() 调用
        # 找到 main 函数开始位置
        main_start = content.find('int main(void)')
        if main_start != -1:
            # 找到第一个 { 后的位置
            brace_start = content.find('{', main_start)
            # 在初始化部分添加 USART_Init()
            insert_pos = brace_start + 1
            content = content[:insert_pos] + '\n    USART_Init();  // 初始化串口通信\n' + content[insert_pos:]
        
        with open(main_c_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return main_c_path
    
    def _add_files_to_project(self, source_files):
        """添加源文件到 Keil 工程"""
        if not self.uvprojx:
            return
        
        try:
            # 解析 XML
            tree = ET.parse(self.uvprojx)
            root = tree.getroot()
            
            # 找到文件组
            # Keil 工程文件结构
            namespaces = {'u': 'http://www.keil.com/cv5'}
            
            # 查找目标组
            for target in root.findall('.//Target'):
                for group in target.findall('.//Group'):
                    group_name = group.find('GroupName')
                    if group_name is not None and group_name.text == 'User':
                        # 在 User 组中添加文件
                        for src_file in source_files:
                            if src_file.endswith('.c'):
                                file_name = os.path.basename(src_file)
                                
                                # 检查是否已存在
                                exists = False
                                for file in group.findall('Files/File'):
                                    file_path = file.find('FilePath')
                                    if file_path is not None and file_name in file_path.text:
                                        exists = True
                                        break
                                
                                if not exists:
                                    # 添加文件元素
                                    files_elem = group.find('Files')
                                    if files_elem is not None:
                                        file_elem = ET.SubElement(files_elem, 'File')
                                        ET.SubElement(file_elem, 'FileType').text = '1'  # C source
                                        ET.SubElement(file_elem, 'FilePath').text = src_file.replace('\\\\', '/')
            
            # 保存修改
            tree.write(self.uvprojx, encoding='utf-8')
            
        except Exception as e:
            print(f"工程文件更新失败: {e}")
            # 尝试备份并手动添加
            pass
    
    def is_valid_project(self):
        """检查是否是有效的 Keil 工程"""
        return self.uvprojx is not None and os.path.exists(self.uvprojx)
    
    def get_project_info(self):
        """获取工程信息"""
        info = {
            'project_file': self.uvprojx,
            'user_path': self.user_path,
            'hardware_path': self.hardware_path,
            'valid': self.is_valid_project()
        }
        
        # 检查现有文件
        if os.path.exists(self.user_path):
            info['existing_files'] = os.listdir(self.user_path)
        
        return info
