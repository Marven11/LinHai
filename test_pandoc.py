import subprocess
import tempfile
import time
import os

input_html = "selenium_output.html"
output_md = "test_pandoc_output.md"
timeout = 30

print(f"开始测试pandoc转换")
print(f"输入文件: {input_html}")
print(f"输出文件: {output_md}")
print(f"超时设置: {timeout}秒")

# 检查输入文件是否存在
if not os.path.exists(input_html):
    print(f"错误: 输入文件 {input_html} 不存在")
    exit(1)

print(f"输入文件大小: {os.path.getsize(input_html)} 字节")

start_time = time.time()

try:
    # 检查pandoc是否可用
    if subprocess.run(["which", "pandoc"], capture_output=True).returncode != 0:
        print("错误: pandoc未安装")
        exit(1)
    
    print("pandoc已安装，开始转换...")
    
    # 使用与fetch_article工具相同的pandoc命令
    cmd = [
        "pandoc",
        input_html,
        "-o",
        output_md,
        "--to=markdown"
        "-header_attributes"
        "-link_attributes"
        "-fenced_code_attributes"
        "-inline_code_attributes"
        "-bracketed_spans"
        "-markdown_in_html_blocks"
        "-raw_html"
        "-fenced_divs"
        "-native_divs"
        "-native_spans"
        "-simple_tables"
        "+pipe_tables",
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    
    result = subprocess.run(
        cmd,
        timeout=timeout,
        capture_output=True,
        text=True
    )
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    print(f"pandoc转换完成! 耗时: {elapsed_time:.2f}秒")
    print(f"退出码: {result.returncode}")
    
    if result.returncode == 0:
        print("pandoc转换成功!")
        if os.path.exists(output_md):
            print(f"输出文件大小: {os.path.getsize(output_md)} 字节")
            # 读取前几行内容
            with open(output_md, 'r', encoding='utf-8') as f:
                content = f.read(500)
                print(f"输出文件前500字符:\n{content}")
    else:
        print(f"pandoc转换失败!")
        print(f"STDERR: {result.stderr}")
        
except subprocess.TimeoutExpired:
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"pandoc转换超时! 耗时: {elapsed_time:.2f}秒")
    print("假设8可能正确: pandoc在转换时卡死")
    
except Exception as e:
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"pandoc转换异常: {e}")
    print(f"耗时: {elapsed_time:.2f}秒")