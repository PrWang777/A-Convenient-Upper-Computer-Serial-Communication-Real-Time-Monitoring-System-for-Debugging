# -*- coding: utf-8 -*-
"""
STM32 代码生成器
自动生成 GPIO 和 PWM 配置代码
"""

import os
from datetime import datetime


class CodeGenerator:
    """STM32 代码生成器"""
    
    # GPIO 端口映射
    GPIO_PORTS = {
        'A': 'GPIOA',
        'B': 'GPIOB',
        'C': 'GPIOC'
    }
    
    # TIM 定时器映射（用于 PWM）
    TIM_MAPPING = {
        'PA0': ('TIM2', 1, 'TIM_OC1Init'),
        'PA1': ('TIM2', 2, 'TIM_OC2Init'),
        'PA2': ('TIM2', 3, 'TIM_OC3Init'),
        'PA3': ('TIM2', 4, 'TIM_OC4Init'),
        'PA6': ('TIM3', 1, 'TIM_OC1Init'),
        'PA7': ('TIM3', 2, 'TIM_OC2Init'),
        'PB0': ('TIM3', 3, 'TIM_OC3Init'),
        'PB1': ('TIM3', 4, 'TIM_OC4Init'),
    }
    
    def __init__(self, project_path):
        self.project_path = project_path
        self.hardware_path = os.path.join(project_path, 'Hardware')
        
    def generate_gpio_init(self, pin, mode='OUT'):
        """
        生成 GPIO 初始化代码
        pin: "PA0", "PB1" 等
        mode: "IN" (输入), "OUT" (输出), "PU" (上拉输入)
        """
        port = pin[2]  # 'A' from 'PA0'
        pin_num = int(pin[3:])  # 0 from 'PA0'
        gpio_port = self.GPIO_PORTS[port]
        
        if mode == 'OUT':
            mode_str = "GPIO_Mode_Out_PP"  # 推挽输出
            default = "GPIO_SetBits"  # 默认高电平
        elif mode == 'IN':
            mode_str = "GPIO_Mode_IN_FLOATING"  # 浮空输入
            default = None
        elif mode == 'PU':
            mode_str = "GPIO_Mode_IPU"  # 上拉输入
            default = None
        else:
            mode_str = "GPIO_Mode_Out_PP"
            default = None
        
        # 确定时钟
        if port == 'A':
            rcc = "RCC_APB2Periph_GPIOA"
        elif port == 'B':
            rcc = "RCC_APB2Periph_GPIOB"
        else:
            rcc = "RCC_APB2Periph_GPIOC"
        
        code = f"""/**
  * 函    数：{pin} 初始化
  * 参    数：mode - 引脚模式
  * 返 回 值：无
  */
void GPIO_{pin}_Init(void)
{{
    /*开启时钟*/
    RCC_APB2PeriphClockCmd({rcc}, ENABLE);
    
    /*GPIO初始化*/
    GPIO_InitTypeDef GPIO_InitStructure;
    GPIO_InitStructure.GPIO_Mode = {mode_str};
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_{pin_num};
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init({gpio_port}, &GPIO_InitStructure);
"""
        if default:
            code += f"    /*设置默认电平*/\n    {default}({gpio_port}, GPIO_Pin_{pin_num});\n"
        
        code += "}\n"
        
        # 添加 Set/Reset 函数
        code += f"""
/**
  * 函    数：{pin} 设置高电平
  */
void GPIO_{pin}_Set(void)
{{
    GPIO_SetBits({gpio_port}, GPIO_Pin_{pin_num});
}}

/**
  * 函    数：{pin} 设置低电平
  */
void GPIO_{pin}_Reset(void)
{{
    GPIO_ResetBits({gpio_port}, GPIO_Pin_{pin_num});
}}

/**
  * 函    数：{pin} 状态翻转
  */
void GPIO_{pin}_Toggle(void)
{{
    if (GPIO_ReadOutputDataBit({gpio_port}, GPIO_Pin_{pin_num}) == 0)
    {{
        GPIO_SetBits({gpio_port}, GPIO_Pin_{pin_num});
    }}
    else
    {{
        GPIO_ResetBits({gpio_port}, GPIO_Pin_{pin_num});
    }}
}}

/**
  * 函    数：读取 {pin} 状态
  * 返 回 值：0 或 1
  */
uint8_t GPIO_{pin}_Read(void)
{{
    return GPIO_ReadInputDataBit({gpio_port}, GPIO_Pin_{pin_num});
}}
"""
        return code
    
    def generate_pwm_init(self, pin, frequency=50, period=2000):
        """
        生成 PWM 初始化代码
        pin: "PA0" 等
        frequency: 频率 (Hz)
        period: 周期 (计数值)
        """
        if pin not in self.TIM_MAPPING:
            raise ValueError(f"PWM 不支持引脚 {pin}")
        
        tim, channel, oc_init = self.TIM_MAPPING[pin]
        port = pin[2]
        pin_num = int(pin[3:])
        gpio_port = self.GPIO_PORTS[port]
        
        # 计算预分频
        # 72MHz / (PSC+1) / (ARR+1) = 频率
        # 假设 ARR = period-1, PSC = 7200-1, 则频率 = 50Hz (20ms周期)
        psc = 72 * 1000000 // (frequency * period) - 1
        if psc < 1:
            psc = 1
        
        # 确定 APB 时钟
        if tim == 'TIM2':
            rcc_timer = "RCC_APB1Periph_TIM2"
        elif tim == 'TIM3':
            rcc_timer = "RCC_APB1Periph_TIM3"
        else:
            rcc_timer = "RCC_APB1Periph_TIM2"
        
        code = f"""/**
  * 函    数：{pin} PWM 初始化
  * 参    数：无
  * 返 回 值：无
  */
void PWM_{pin}_Init(void)
{{
    /*开启时钟*/
    RCC_APB1PeriphClockCmd({rcc_timer}, ENABLE);
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIO{port}, ENABLE);
    
    /*GPIO初始化*/
    GPIO_InitTypeDef GPIO_InitStructure;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF_PP;
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_{pin_num};
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_Init({gpio_port}, &GPIO_InitStructure);
    
    /*时基单元初始化*/
    TIM_TimeBaseInitTypeDef TIM_TimeBaseInitStructure;
    TIM_TimeBaseInitStructure.TIM_ClockDivision = TIM_CKD_DIV1;
    TIM_TimeBaseInitStructure.TIM_CounterMode = TIM_CounterMode_Up;
    TIM_TimeBaseInitStructure.TIM_Period = {period - 1};
    TIM_TimeBaseInitStructure.TIM_Prescaler = {psc - 1};
    TIM_TimeBaseInitStructure.TIM_RepetitionCounter = 0;
    TIM_TimeBaseInit({tim}, &TIM_TimeBaseInitStructure);
    
    /*PWM输出配置*/
    TIM_OCInitTypeDef TIM_OCInitStructure;
    TIM_OCStructInit(&TIM_OCInitStructure);
    TIM_OCInitStructure.TIM_OCMode = TIM_OCMode_PWM1;
    TIM_OCInitStructure.TIM_OCPolarity = TIM_OCPolarity_High;
    TIM_OCInitStructure.TIM_OutputState = TIM_OutputState_Enable;
    TIM_OCInitStructure.TIM_Pulse = 0;
    {oc_init}({tim}, &TIM_OCInitStructure);
    
    /*使能定时器*/
    TIM_Cmd({tim}, ENABLE);
}}

/**
  * 函    数：设置 {pin} PWM 占空比
  * 参    数：compare - 占空比值 (0-{period-1})
  */
void PWM_{pin}_SetCompare(uint16_t compare)
{{
    TIM_SetCompare{channel}({tim}, compare);
}}
"""
        return code
    
    def generate_header(self, pin, type='GPIO'):
        """生成头文件"""
        if type == 'GPIO':
            funcs = [
                f"void GPIO_{pin}_Init(void);",
                f"void GPIO_{pin}_Set(void);",
                f"void GPIO_{pin}_Reset(void);",
                f"void GPIO_{pin}_Toggle(void);",
                f"uint8_t GPIO_{pin}_Read(void);"
            ]
        else:
            funcs = [
                f"void PWM_{pin}_Init(void);",
                f"void PWM_{pin}_SetCompare(uint16_t compare);"
            ]
        
        code = f"""#ifndef __{pin}_{type}_H
#define __{pin}_{type}_H

#include "stm32f10x.h"

"""
        code += '\n'.join(funcs)
        code += f"""

#endif
"""
        return code
    
    def save_gpio_files(self, pin):
        """保存 GPIO 配置文件"""
        c_file = os.path.join(self.hardware_path, f"GPIO_{pin}.c")
        h_file = os.path.join(self.hardware_path, f"GPIO_{pin}.h")
        
        # 生成代码
        c_code = f"#include \"stm32f10x.h\"\n#include \"GPIO_{pin}.h\"\n\n"
        c_code += self.generate_gpio_init(pin, 'OUT')
        
        h_code = self.generate_header(pin, 'GPIO')
        
        # 写入文件
        with open(c_file, 'w', encoding='utf-8') as f:
            f.write(c_code)
        
        with open(h_file, 'w', encoding='utf-8') as f:
            f.write(h_code)
        
        return c_file, h_file
    
    def save_pwm_files(self, pin):
        """保存 PWM 配置文件"""
        c_file = os.path.join(self.hardware_path, f"PWM_{pin}.c")
        h_file = os.path.join(self.hardware_path, f"PWM_{pin}.h")
        
        # 生成代码
        c_code = f"#include \"stm32f10x.h\"\n#include \"PWM_{pin}.h\"\n\n"
        c_code += self.generate_pwm_init(pin)
        
        h_code = self.generate_header(pin, 'PWM')
        
        # 写入文件
        with open(c_file, 'w', encoding='utf-8') as f:
            f.write(c_code)
        
        with open(h_file, 'w', encoding='utf-8') as f:
            f.write(h_code)
        
        return c_file, h_file
    
    def get_available_pwm_pins(self):
        """获取可用的 PWM 引脚列表"""
        return list(self.TIM_MAPPING.keys())
    
    def get_all_pins(self):
        """获取所有可用引脚"""
        pins = []
        for port in ['A', 'B', 'C']:
            for num in range(16):
                pins.append(f"P{port}{num}")
        return pins
    
    def is_pin_configured(self, pin):
        """检查引脚是否已在工程中配置"""
        # 检查 Hardware 目录下是否有对应的 .c 文件
        gpio_file = os.path.join(self.hardware_path, f"GPIO_{pin}.c")
        pwm_file = os.path.join(self.hardware_path, f"PWM_{pin}.c")
        
        if os.path.exists(gpio_file) or os.path.exists(pwm_file):
            return True
        return False
    
    def get_configured_pins(self):
        """获取工程中已配置的所有引脚"""
        configured = []
        if not os.path.exists(self.hardware_path):
            return configured
        
        for f in os.listdir(self.hardware_path):
            if f.startswith('GPIO_P') and f.endswith('.c'):
                pin = f[4:-2]  # GPIO_PA0.c -> PA0
                configured.append(('GPIO', pin))
            elif f.startswith('PWM_P') and f.endswith('.c'):
                pin = f[3:-2]  # PWM_PA0.c -> PA0
                configured.append(('PWM', pin))
        
        return configured
