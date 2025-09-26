# 文章抓取与Markdown转换分析报告

## 实现过程

1. **网页抓取**
   - 使用Selenium + ChromeDriver抓取目标网页
   - 通过`webdriver_manager`自动管理浏览器驱动
   - 保存完整HTML到临时文件

2. **格式转换**
   - 使用pandoc命令转换HTML为Markdown
   - 关键参数：`--to=markdown-markdown_in_html_blocks-fenced_divs-native_divs`
   - 保留原始HTML结构中的代码块和区块元素

## 转换效果

| 特性 | 支持情况 | 说明 |
|------|----------|------|
| 代码块 | ✅ | 转换为fenced code blocks |
| 表格 | ✅ | 保留表格结构 |
| 图片 | ✅ | 转换为Markdown图片语法 |
| 内联样式 | ⚠️ | 部分样式信息丢失 |
| JavaScript内容 | ❌ | 不执行JS，仅抓取初始HTML |

## 使用示例

```python
# 基本用法
md_content = fetch_and_convert("https://example.com/article")

# 自定义输出路径
fetch_and_convert("https://example.com", "article.md")
```

## 注意事项

1. 需要系统已安装pandoc（`brew install pandoc`或`sudo apt install pandoc`）
2. Selenium需要对应版本的浏览器驱动
3. 对于需要JS渲染的页面，可能需要增加等待时间
4. 部分网站的反爬机制可能需要添加headers或代理

## 优化建议

- 添加自动检测页面渲染完成的机制
- 支持更多格式的转换参数配置
- 增加对微信公众号等特定平台的解析规则