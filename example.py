"""
创建一个包含JavaScript代码的markdown文档示例
"""

def create_markdown_with_js():
    """创建包含JS代码的markdown文档"""
    
    # 使用不同的引号类型来避免转义反引号
    markdown_content = '''# JavaScript 代码示例

这是一个包含JavaScript代码的markdown文档喵~

## 代码块

''' + """```javascript
// 这是一个JavaScript代码块
function greet() {
    console.log("Hello, World!");
}

// 多行字符串包含三个反引号
const template = `
这是一个模板字符串
包含三个反引号：` + """ + """```
`;

greet();
```""" + """

## 说明

这个示例展示了如何在markdown中正确显示包含反引号的JavaScript代码喵~
"""
    
    return markdown_content

if __name__ == "__main__":
    content = create_markdown_with_js()
    
    # 写入文件
    with open("example.md", "w", encoding="utf-8") as f:
        f.write(content)
    
    print("Markdown文档创建成功喵~")
    print("文件已保存为: example.md")