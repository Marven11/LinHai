# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [ ] qwen的百炼API需要传入如下所示参数才能统计token用量，修改config格式，支持在创建OpenAI类时和每次创建completion时传入自定义的**kwargs
    - [ ] 添加对应的unittest
    - [ ] 尝试启动linhai，使用`python -m linhai --config ./config.toml -m '@qwen 读取当前token用量输出到usage.txt中，如果无法获得则写入“无法获得token用量”，然后退出'`测试
```python
client = OpenAI(
    api_key=os.environ["DASHSCOPE_API_KEY"],
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

completion = client.chat.completions.create(
    model="qwen-plus",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "请介绍一下自己"}
    ],
    stream=True,
    stream_options={"include_usage": True}
)
```
- [ ] 运行并修复unittest
- [ ] 使用pyright检查代码并修复，修复之后运行并修复unittest

注意：一定记得参考历史commit|git commit|历史压缩|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，linhai不会使用STDIO输出消息，更不会在结束时自动退出！你应该在message中告诉linhai使用工具写文件并退出！

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
