import httpx
import time

url = "https://news.ycombinator.com/item?id=45657428"
timeout = 10

print(f"开始请求: {url}")
print(f"超时设置: {timeout}秒")
start_time = time.time()

try:
    # 使用httpx请求URL
    response = httpx.get(url, timeout=timeout)
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    print(f"请求成功!")
    print(f"状态码: {response.status_code}")
    print(f"响应大小: {len(response.text)} 字符")
    print(f"耗时: {elapsed_time:.2f}秒")
    
    # 保存响应内容供分析
    with open("response_sample.html", "w", encoding="utf-8") as f:
        f.write(response.text[:1000])  # 只保存前1000字符用于分析
    print("已保存响应样本到 response_sample.html")
    
except httpx.TimeoutException:
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"请求超时! 耗时: {elapsed_time:.2f}秒")
    print("问题可能在于网络连接或目标服务器响应慢")
    
except Exception as e:
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"请求异常: {e}")
    print(f"耗时: {elapsed_time:.2f}秒")