import subprocess
import time
import sys

# 设置超时时间（秒）
TIMEOUT = 30

# 构建命令
command = [".venv/bin/python", "-m", "linhai", "--config", "./config.toml", "-m", "fetch_article https://news.ycombinator.com/item?id=45657428"]

try:
    print(f"开始执行命令，超时时间: {TIMEOUT}秒")
    start_time = time.time()
    
    # 运行命令，设置超时
    result = subprocess.run(
        command,
        timeout=TIMEOUT,
        capture_output=True,
        text=True
    )
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    print(f"命令执行完成，耗时: {elapsed_time:.2f}秒")
    print("STDOUT:")
    print(result.stdout)
    print("STDERR:")
    print(result.stderr)
    print(f"退出码: {result.returncode}")
    
    if result.returncode == 0:
        print("实验成功: 工具正常完成，未超时")
    else:
        print(f"实验失败: 工具返回错误码 {result.returncode}")
        
except subprocess.TimeoutExpired:
    print(f"实验超时: 命令在{TIMEOUT}秒后未完成，假设1可能正确")
    sys.exit(1)
except Exception as e:
    print(f"实验异常: {e}")
    sys.exit(1)