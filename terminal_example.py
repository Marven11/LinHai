import pyte
import subprocess
import pty
import os
import select
import json


class PyteTerminal:
    def __init__(self, columns=80, lines=24):
        self.screen = pyte.Screen(columns, lines)
        self.stream = pyte.Stream()
        self.stream.attach(self.screen)

        self.master, self.slave = pty.openpty()

        env = os.environ.copy()
        env["TERM"] = "vt100"
        env["COLUMNS"] = str(columns)
        env["LINES"] = str(lines)

        self.process = subprocess.Popen(
            ["/usr/bin/env", "bash"],
            stdin=self.slave,
            stdout=self.slave,
            stderr=self.slave,
            env=env,
            preexec_fn=os.setsid,
        )

        # 在初始化时读取JSON文件一次
        with open("key_mappings.json", "r", encoding="utf-8") as f:
            self.key_mappings = json.load(f)

    def send(self, data):
        """发送命令到终端"""
        if isinstance(data, str):
            data = data.encode("utf-8")
        os.write(self.master, data)

    def update(self):
        """更新屏幕状态"""
        while select.select([self.master], [], [], 0.1)[0]:
            try:
                data = os.read(self.master, 1024).decode("utf-8", errors="ignore")
                self.stream.feed(data)
            except (OSError, UnicodeDecodeError):
                break

    def get_screen(self):
        """获取当前屏幕内容"""
        return "\n".join("".join(line) for line in self.screen.display)

    def send_key(self, key_name):
        """发送可读的按键名到终端"""
        # 直接使用存储的映射，有错误直接raise
        key_data = self.key_mappings[key_name]
        # 处理转义字符
        key_data = key_data.encode('utf-8').decode('unicode_escape')
        self.send(key_data)

    def close(self):
        self.process.terminate()
        os.close(self.master)
        os.close(self.slave)


# 使用示例：使用vim创建并写入文件
term = PyteTerminal()
import time

# 启动vim并创建新文件
term.send("vim example.txt\r")

# 进入插入模式并写入内容
term.send("i")
term.send("这是使用Vim写入的示例文件内容喵~\n")
term.send("第二行内容：114514\n")
term.send("第三行内容：李田所")

# 退出插入模式并保存文件
term.send_key("esc")  # 使用可读按键名发送ESC键
term.send(":wq")
term.send_key("enter")  # 使用可读按键名发送回车键

# 显示最终屏幕内容
term.update()
screen_content = term.get_screen()
print("屏幕内容:")
print(screen_content)

# 验证文件是否创建成功
term.send("cat example.txt\r")
term.update()
file_content = term.get_screen()
print("\n文件内容:")
print(file_content)

# 演示更多按键功能
print("\n演示更多按键功能:")
term.send("ls")
term.send_key("tab")  # 自动补全
term.update()
time.sleep(0.5)
term.send_key("enter")  # 执行命令
term.update()
time.sleep(0.5)

# 清屏
term.send("clear\r")
term.update()

term.close()

print("\n按键映射功能已添加完成！支持以下按键名:")
print("enter, esc, tab, space, backspace, up, down, left, right")
print("home, end, insert, delete, pageup, pagedown, f1-f12")