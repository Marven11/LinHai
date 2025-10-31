import os
import select
import termios
import subprocess
import fcntl
import struct


class TerminalController:
    def __init__(self, width=80, height=24):
        self.width = width
        self.height = height
        self.master_fd = None
        self.slave_fd = None
        self.process = None
        self.original_termios = None

        # 允许的按键名称集合，参考PyAutoGUI的KEYBOARD_KEYS
        self.allowed_keys = set(
            [
                "\t",
                "\n",
                "\r",
                " ",
                "!",
                '"',
                "#",
                "$",
                "%",
                "&",
                "'",
                "(",
                ")",
                "*",
                "+",
                ",",
                "-",
                ".",
                "/",
                "0",
                "1",
                "2",
                "3",
                "4",
                "5",
                "6",
                "7",
                "8",
                "9",
                ":",
                ";",
                "<",
                "=",
                ">",
                "?",
                "@",
                "[",
                "\\",
                "]",
                "^",
                "_",
                "`",
                "a",
                "b",
                "c",
                "d",
                "e",
                "f",
                "g",
                "h",
                "i",
                "j",
                "k",
                "l",
                "m",
                "n",
                "o",
                "p",
                "q",
                "r",
                "s",
                "t",
                "u",
                "v",
                "w",
                "x",
                "y",
                "z",
                "{",
                "|",
                "}",
                "~",
                "accept",
                "add",
                "alt",
                "altleft",
                "altright",
                "apps",
                "backspace",
                "browserback",
                "browserfavorites",
                "browserforward",
                "browserhome",
                "browserrefresh",
                "browsersearch",
                "browserstop",
                "capslock",
                "clear",
                "convert",
                "ctrl",
                "ctrlleft",
                "ctrlright",
                "decimal",
                "del",
                "delete",
                "divide",
                "down",
                "end",
                "enter",
                "esc",
                "escape",
                "execute",
                "f1",
                "f10",
                "f11",
                "f12",
                "f13",
                "f14",
                "f15",
                "f16",
                "f17",
                "f18",
                "f19",
                "f2",
                "f20",
                "f21",
                "f22",
                "f23",
                "f24",
                "f3",
                "f4",
                "f5",
                "f6",
                "f7",
                "f8",
                "f9",
                "final",
                "fn",
                "hanguel",
                "hangul",
                "hanja",
                "help",
                "home",
                "insert",
                "junja",
                "kana",
                "kanji",
                "launchapp1",
                "launchapp2",
                "launchmail",
                "launchmediaselect",
                "left",
                "modechange",
                "multiply",
                "nexttrack",
                "nonconvert",
                "num0",
                "num1",
                "num2",
                "num3",
                "num4",
                "num5",
                "num6",
                "num7",
                "num8",
                "num9",
                "numlock",
                "pagedown",
                "pageup",
                "pause",
                "pgdn",
                "pgup",
                "playpause",
                "prevtrack",
                "print",
                "printscreen",
                "prntscrn",
                "prtsc",
                "prtscr",
                "return",
                "right",
                "scrolllock",
                "select",
                "separator",
                "shift",
                "shiftleft",
                "shiftright",
                "sleep",
                "space",
                "stop",
                "subtract",
                "tab",
                "up",
                "volumedown",
                "volumemute",
                "volumeup",
                "win",
                "winleft",
                "winright",
                "yen",
                "command",
                "option",
                "optionleft",
                "optionright",
                "ctrl_c",
                "ctrl_d",
                "ctrl_z",  # 额外添加用于终端控制
            ]
        )

        # 按键映射字典，参考PyAutoGUI的KEYBOARD_KEYS设计
        self.key_mappings = {
            "enter": "\n",
            "tab": "\t",
            "backspace": "\x08",
            "escape": "\x1b",
            "space": " ",
            "left": "\x1b[D",
            "right": "\x1b[C",
            "up": "\x1b[A",
            "down": "\x1b[B",
            "home": "\x1b[H",
            "end": "\x1b[F",
            "insert": "\x1b[2~",
            "delete": "\x1b[3~",
            "pageup": "\x1b[5~",
            "pagedown": "\x1b[6~",
            "f1": "\x1bOP",
            "f2": "\x1bOQ",
            "f3": "\x1bOR",
            "f4": "\x1bOS",
            "f5": "\x1b[15~",
            "f6": "\x1b[17~",
            "f7": "\x1b[18~",
            "f8": "\x1b[19~",
            "f9": "\x1b[20~",
            "f10": "\x1b[21~",
            "f11": "\x1b[23~",
            "f12": "\x1b[24~",
            "return": "\r",
            "esc": "\x1b",
            "del": "\x1b[3~",
            "pgup": "\x1b[5~",
            "pgdn": "\x1b[6~",
            "ctrl_c": "\x03",
            "ctrl_d": "\x04",
            "ctrl_z": "\x1a",
        }

    def create_terminal(self):
        """创建伪终端"""
        try:
            # 创建伪终端对
            self.master_fd, self.slave_fd = os.openpty()

            # 设置终端大小
            winsize = struct.pack("HHHH", self.height, self.width, 0, 0)
            fcntl.ioctl(self.slave_fd, termios.TIOCSWINSZ, winsize)

            # 启动shell进程
            self.process = subprocess.Popen(
                ["/bin/bash", "--login"],
                stdin=self.slave_fd,
                stdout=self.slave_fd,
                stderr=self.slave_fd,
                preexec_fn=os.setsid,
            )

            # 设置非阻塞读取
            flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            print(f"终端已创建: {self.width}x{self.height}")
            return True

        except Exception as e:
            print(f"创建终端失败: {e}")
            return False

    def read_terminal(self, timeout=0.1):
        """按行读取终端内容"""
        if not self.master_fd:
            return []

        lines = []
        current_line = ""

        try:
            # 读取所有可用数据
            while True:
                ready, _, _ = select.select([self.master_fd], [], [], timeout)
                if not ready:
                    break

                data = os.read(self.master_fd, 1024).decode("utf-8", errors="ignore")
                if not data:
                    break

                # 处理数据，按行分割
                for char in data:
                    if char == "\n" or char == "\r":
                        if current_line:
                            lines.append(current_line)
                            current_line = ""
                    else:
                        current_line += char

            # 添加最后一行（如果有）
            if current_line:
                lines.append(current_line)

        except (OSError, IOError):
            pass

        return lines

    def read_terminal_raw(self, max_chars=1024):
        """读取原始终端输出（不按行分割）"""
        if not self.master_fd:
            return ""

        try:
            output = ""
            ready, _, _ = select.select([self.master_fd], [], [], 0.1)
            if ready:
                data = os.read(self.master_fd, max_chars).decode(
                    "utf-8", errors="ignore"
                )
                output = data
            return output
        except (OSError, IOError):
            return ""

    def send_key(self, key, control_code=None):
        """发送按键到终端"""
        if not self.master_fd:
            return False

        try:
            if control_code:
                # 发送控制码
                os.write(self.master_fd, control_code.encode())
            else:
                # 发送普通按键
                os.write(self.master_fd, key.encode())
            return True
        except (OSError, IOError) as e:
            print(f"发送按键失败: {e}")
            return False

    def send_keypress(self, key_names: list[str]):
        """发送按键名称列表到终端，参考PyAutoGUI设计"""

        for key_name in key_names:
            if key_name not in self.allowed_keys:
                raise ValueError(f"Invalid key name: {key_name}")
            if len(key_name) == 1:
                # 单字符按键直接发送
                if not self.send_key(key_name):
                    return False
            else:
                # 多字符按键查找映射
                if key_name in self.key_mappings:
                    if not self.send_key("", self.key_mappings[key_name]):
                        return False
                else:
                    raise ValueError(f"No mapping for key: {key_name}")
        return True

    def send_command(self, command):
        """发送完整命令"""
        success = True
        for char in command:
            if not self.send_key(char):
                success = False
        if success:
            self.send_keypress(["enter"])
        return success

    def close(self):
        """关闭终端"""
        if self.process:
            self.process.kill()
            self.process.wait()
        if self.master_fd:
            os.close(self.master_fd)
        if self.slave_fd:
            os.close(self.slave_fd)


# 使用示例
def main():
    # 创建终端控制器
    terminal = TerminalController(width=80, height=24)

    # 创建终端
    if terminal.create_terminal():
        print("终端创建成功！")

        # 等待终端初始化
        import time

        time.sleep(0.5)

        # 读取初始输出
        lines = terminal.read_terminal()
        for line in lines:
            print(f"终端: {line}")

        # 发送命令
        print("发送 'ls' 命令...")
        terminal.send_command("ls")

        # 等待命令执行
        time.sleep(1)

        # 读取命令输出
        lines = terminal.read_terminal()
        for line in lines:
            print(f"输出: {line}")

        print("发送Ctrl+C...")
        terminal.send_keypress(["ctrl_c"])

        # 清理
        terminal.close()


if __name__ == "__main__":
    main()
