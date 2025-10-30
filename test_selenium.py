import tempfile
from selenium import webdriver
from bs4 import BeautifulSoup
import time

url = "https://news.ycombinator.com/item?id=45657428"
timeout = 30

print(f"开始测试Selenium: {url}")
print(f"超时设置: {timeout}秒")
start_time = time.time()

try:
    options = webdriver.FirefoxOptions()
    options.add_argument("--headless")
    
    print("启动Firefox驱动...")
    with webdriver.Firefox(options=options) as driver:
        print("驱动启动成功，开始获取页面...")
        driver.get(url)
        
        print("页面加载完成，开始解析HTML...")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # 删除javascript:链接
        for a in soup.find_all("a", href=True):
            if a["href"].startswith("javascript:"):
                a.decompose()

        # 删除无用image元素
        for img in soup.find_all("img", src=True):
            src = img.get("src", "")
            if len(str(src)) > 400:
                img.decompose()

        for svg in soup.find_all("svg"):
            svg.decompose()
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Selenium处理完成! 耗时: {elapsed_time:.2f}秒")
        print(f"HTML大小: {len(str(soup))} 字符")
        
        # 保存解析后的HTML供检查
        with open("selenium_output.html", "w", encoding="utf-8") as f:
            f.write(str(soup))
        print("已保存解析后的HTML到 selenium_output.html")

except Exception as e:
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Selenium测试异常: {e}")
    print(f"耗时: {elapsed_time:.2f}秒")