import subprocess
import time
import os

# 设置超时时间（秒）
timeout = 30

# 构建命令
command = [
    "python", "-m", "linhai",
    "--config", "./config.toml",
    "-m", "请调用fetch_article工具爬取https://news.ycombinator.com/item?id=45657428"
]

# 输出文件
output_file = "fetch_article_output.txt"

print(f"开始执行linhai命令，超时时间: {timeout}秒")
start_time = time.time()

try:
    # 运行命令，设置超时
    result = subprocess.run(
        command,
        timeout=timeout,
        capture_output=True,
        text=True
    )
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # 保存输出
    with open(output_file, "w") as f:
        f.write(f"执行时间: {elapsed_time:.2f}秒\n")
        f.write(f"返回值: {result.returncode}\n")
        f.write(f"标准输出:\n{result.stdout}\n")
        f.write(f"标准错误:\n{result.stderr}\n")
    
    print(f"执行完成，时间: {elapsed_time:.2f}秒")
    print(f"输出已保存到: {output_file}")
    
    if elapsed_time > 10:  # 假设超过10秒为慢
        print("工具执行慢，支持假设1")
    else:
        print("工具执行快，推翻假设1")
        
except subprocess.TimeoutExpired:
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    with open(output_file, "w") as f:
        f.write(f"执行超时，已运行: {elapsed_time:.2f}秒\n")
    
    print(f"命令超时，运行了 {elapsed_time:.2f} 秒")
    print("工具卡死，强烈支持假设1")

except Exception as e:
    with open(output_file, "w") as f:
        f.write(f"错误: {e}\n")
    print(f"执行出错: {e}")