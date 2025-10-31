import curses
import threading
import queue
import time

class TerminalController:
    def __init__(self, width=80, height=24):
        self.width = width
        self.height = height
        self.screen = None
        self.input_queue = queue.Queue()
        self.running = False
        self.terminal_content = [[' ' for _ in range(width)] for _ in range(height)]
        
    def init_curses(self):
        """初始化curses"""
        self.screen = curses.initscr()
        curses.noecho()
        curses.cbreak()
        self.screen.keypad(True)
        self.screen.nodelay(True)
        
    def cleanup_curses(self):
        """清理curses"""
        if self.screen:
            curses.nocbreak()
            self.screen.keypad(False)
            curses.echo()
            curses.endwin()
    
    def read_terminal(self):
        """
        读取终端内容，按行返回
        
        Returns:
            list: 包含终端每一行内容的列表
        """
        if not self.screen:
            return self._get_terminal_content()
            
        lines = []
        for y in range(self.height):
            line = ''
            for x in range(self.width):
                try:
                    char = self.screen.inch(y, x) & 0xFF
                    if char < 32 or char > 126:  # 只显示可打印字符
                        line += ' '
                    else:
                        line += chr(char)
                except:
                    line += ' '
            lines.append(line)
        return lines
    
    def _get_terminal_content(self):
        """在没有curses的情况下获取终端内容"""
        return [''.join(row) for row in self.terminal_content]
    
    def send_key(self, key_code, special_key=None):
        """
        发送按键到终端
        
        Args:
            key_code (str/int): 按键代码，可以是字符或curses特殊键常量
            special_key (str): 特殊按键类型，如 'enter', 'backspace', 'tab'等
        """
        if not self.screen:
            self._simulate_key_input(key_code, special_key)
            return
            
        if special_key:
            if special_key.lower() == 'enter':
                self.input_queue.put('\n')
            elif special_key.lower() == 'backspace':
                self.input_queue.put(curses.KEY_BACKSPACE)
            elif special_key.lower() == 'tab':
                self.input_queue.put('\t')
            elif special_key.lower() == 'escape':
                self.input_queue.put(curses.KEY_EXIT)
            elif special_key.lower() == 'up':
                self.input_queue.put(curses.KEY_UP)
            elif special_key.lower() == 'down':
                self.input_queue.put(curses.KEY_DOWN)
            elif special_key.lower() == 'left':
                self.input_queue.put(curses.KEY_LEFT)
            elif special_key.lower() == 'right':
                self.input_queue.put(curses.KEY_RIGHT)
        else:
            self.input_queue.put(key_code)
    
    def _simulate_key_input(self, key_code, special_key):
        """在没有curses的情况下模拟按键输入"""
        # 这里可以添加逻辑来更新terminal_content
        # 简化版本：只记录按键
        print(f"模拟按键: {key_code}, 特殊键: {special_key}")
    
    def process_input(self):
        """处理输入队列中的按键"""
        try:
            while not self.input_queue.empty():
                key = self.input_queue.get_nowait()
                if self.screen:
                    if isinstance(key, int):  # 特殊键
                        self.screen.addch(key)
                    else:  # 普通字符
                        self.screen.addstr(key)
                    self.screen.refresh()
        except queue.Empty:
            pass
    
    def update_terminal_content(self, content):
        """
        更新终端内容（用于模拟）
        
        Args:
            content (list): 新的终端内容，每行一个字符串
        """
        for i in range(min(len(content), self.height)):
            line = content[i]
            for j in range(min(len(line), self.width)):
                self.terminal_content[i][j] = line[j]
    
    def start_terminal(self):
        """启动终端模拟"""
        def run_terminal():
            self.init_curses()
            self.running = True
            
            try:
                while self.running:
                    # 处理用户输入
                    try:
                        key = self.screen.getch()
                        if key != -1:
                            self.input_queue.put(key)
                    except:
                        pass
                    
                    # 处理程序发送的按键
                    self.process_input()
                    
                    time.sleep(0.01)
            finally:
                self.cleanup_curses()
        
        # 在新线程中运行终端
        self.terminal_thread = threading.Thread(target=run_terminal)
        self.terminal_thread.daemon = True
        self.terminal_thread.start()
    
    def stop_terminal(self):
        """停止终端模拟"""
        self.running = False
        if hasattr(self, 'terminal_thread'):
            self.terminal_thread.join(timeout=1.0)

# 使用示例
def demo():
    terminal = TerminalController()
    
    try:
        # 启动终端
        terminal.start_terminal()
        time.sleep(0.5)  # 等待终端启动
        
        # 示例1：发送一些按键
        print("发送按键到终端...")
        terminal.send_key('H')
        terminal.send_key('e')
        terminal.send_key('l')
        terminal.send_key('l')
        terminal.send_key('o')
        terminal.send_key(' ', 'enter')
        terminal.send_key('W', 'enter')
        terminal.send_key('o', 'enter')
        terminal.send_key('r', 'enter')
        terminal.send_key('l', 'enter')
        terminal.send_key('d', 'enter')
        terminal.send_key('!', 'enter')
        
        time.sleep(1)
        
        # 示例2：读取终端内容
        print("\n读取终端内容:")
        content = terminal.read_terminal()
        for i, line in enumerate(content):
            print(f"行 {i:2d}: {line}")
        
        # 示例3：发送特殊按键
        print("\n发送特殊按键...")
        terminal.send_key(None, 'up')
        terminal.send_key(None, 'down')
        terminal.send_key(None, 'left')
        terminal.send_key(None, 'right')
        terminal.send_key(None, 'tab')
        
        time.sleep(1)
        
    finally:
        terminal.stop_terminal()

# 简化版本（不使用curses）
class SimpleTerminalController:
    def __init__(self, width=80, height=24):
        self.width = width
        self.height = height
        self.content = [[' ' for _ in range(width)] for _ in range(height)]
        self.current_line = 0
        self.current_pos = 0
    
    def read_terminal(self):
        """读取终端内容"""
        return [''.join(row) for row in self.content]
    
    def send_key(self, key_code, special_key=None):
        """发送按键"""
        if special_key == 'enter':
            self.current_line += 1
            self.current_pos = 0
            if self.current_line >= self.height:
                self._scroll_up()
                self.current_line = self.height - 1
        elif special_key == 'backspace':
            if self.current_pos > 0:
                self.current_pos -= 1
                self.content[self.current_line][self.current_pos] = ' '
        elif key_code and len(str(key_code)) == 1:
            if self.current_pos < self.width:
                self.content[self.current_line][self.current_pos] = str(key_code)
                self.current_pos += 1
    
    def _scroll_up(self):
        """向上滚动内容"""
        for i in range(self.height - 1):
            self.content[i] = self.content[i + 1][:]
        self.content[self.height - 1] = [' ' for _ in range(self.width)]
    
    def update_content(self, lines):
        """更新终端内容"""
        for i, line in enumerate(lines):
            if i < self.height:
                for j, char in enumerate(line):
                    if j < self.width:
                        self.content[i][j] = char

if __name__ == "__main__":
    # 运行演示
    demo()
    
    # 使用简化版本
    print("\n使用简化版本:")
    simple_term = SimpleTerminalController()
    simple_term.send_key('T')
    simple_term.send_key('e')
    simple_term.send_key('s')
    simple_term.send_key('t')
    simple_term.send_key(None, 'enter')
    simple_term.send_key('H')
    simple_term.send_key('i')
    simple_term.send_key('!')
    
    content = simple_term.read_terminal()
    for i, line in enumerate(content):
        print(f"行 {i:2d}: {line}")