#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
STM32 上位机监视程序 - 入口文件
用于控制机械臂项目的 GPIO、PWM 引脚配置和实时状态监测
"""

import sys
from PyQt5.QtWidgets import QApplication
from gui.main_window import MainWindow


def main():
    """主函数"""
    try:
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
        
        window = MainWindow()
        window.show()
        
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f"程序启动失败: {e}")
        import traceback
        traceback.print_exc()
        input("按回车键退出...")


if __name__ == '__main__':
    main()
