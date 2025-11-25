# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行 git commit，消息参考历史

- [x] 修改 http_request
  - 添加默认 User Agent，声明自己为 Chrome 兼容的 LinHai
  - 在响应为二进制内容时将内容保存到临时文件，并返回临时文件的路径
    - 看 Content-Type 和 chardet 编码检测
    - 编写 unittest
- [ ] 搜索rg '  #' linhai并删除废话注释
  - 废话注释指的是完全没有额外信息量，去掉注释也能流畅看懂对应代码的注释

注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] 添加假设颠覆法
- [ ] 添加响应式 SubAgent
  - 避免拍马屁
  - 避免在工具调用未结束时就报告“完成”
  - 避免同时读取并写入文件
  - 避免使用无序分点甚至 emoji 总结
