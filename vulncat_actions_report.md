# VulnCat Action 报告

## 信息收集类 Action

1. **analyze_source_code**
   - 描述：粗略判断源码中存在的漏洞类型。
   - 类型：`information_gathering`
   - 标签：`TAGS_FOR_ALL_LLM`

2. **analyze_api_exploit**
   - 描述：精细分析源码中的API如何调用以触发漏洞，并给出示例脚本。
   - 类型：`information_gathering`
   - 标签：`TAGS_FOR_ALL_LLM`

3. **action_http_request**
   - 描述：向指定URL发送HTTP GET请求并返回响应信息。
   - 类型：`information_gathering`
   - 标签：`TAGS_FOR_ALL_LLM`

4. **action_http_custom_request**
   - 描述：使用requests.request提交自定义HTTP请求。
   - 类型：`information_gathering`
   - 标签：`TAGS_FOR_ALL_LLM`

5. **action_http_raw_request**
   - 描述：使用TCP socket发送原始HTTP请求。
   - 类型：`information_gathering`
   - 标签：`TAGS_FOR_ALL_LLM`

6. **action_param_discovery**
   - 描述：测试URL可能存在的参数名。
   - 类型：`information_gathering`
   - 标签：`TAGS_FOR_ALL_LLM`

## 辅助功能类 Action

1. **list_knowledge_files**
   - 描述：列出知识库中的所有文件。
   - 类型：`auxiliary`
   - 标签：`TAGS_FOR_ALL_LLM`

2. **read_knowledge_file**
   - 描述：读取知识库中的文件内容。
   - 类型：`auxiliary`
   - 标签：`TAGS_FOR_ALL_LLM`

3. **read_local_file**
   - 描述：读取本地文件或列出目录内容。
   - 类型：`auxiliary`
   - 标签：`TAGS_FOR_ALL_LLM`

4. **download_file**
   - 描述：从URL下载文件到本地。
   - 类型：`auxiliary`
   - 标签：`TAGS_FOR_ALL_LLM`

5. **unzip_file**
   - 描述：解压ZIP文件到同名目录。
   - 类型：`auxiliary`
   - 标签：`TAGS_FOR_ALL_LLM`

6. **run_php_code**
   - 描述：在本地执行PHP代码并返回结果。
   - 类型：`auxiliary`
   - 标签：`TAGS_FOR_ALL_LLM`

## 漏洞利用类 Action

1. **analyze_source_code_ssti**
   - 描述：分析源码中的Jinja SSTI漏洞并生成示例exp。
   - 类型：`exploit`
   - 标签：`TAGS_FOR_DISTILLED_LLM`

2. **action_generate_ssti_payload_local_fenjing**
   - 描述：使用fenjing生成Jinja SSTI payload。
   - 类型：`exploit`
   - 标签：`TAGS_FOR_ADVANCED_LLM`

3. **action_generate_ssti_payload_remote_fenjing**
   - 描述：使用fenjing根据远程目标的WAF生成SSTI payload。
   - 类型：`exploit`
   - 标签：`TAGS_FOR_ADVANCED_LLM`

4. **action_file_include**
   - 描述：攻击文件包含漏洞，通过filter chain实现RCE。
   - 类型：`exploit`
   - 标签：`TAGS_FOR_ALL_LLM`

5. **action_sqlmap_scan**
   - 描述：调用sqlmap进行SQL注入扫描并总结结果。
   - 类型：`exploit`
   - 标签：`TAGS_FOR_ADVANCED_LLM`

6. **action_fuzz_ssti_api**
   - 描述：使用payload测试API的SSTI漏洞。
   - 类型：`exploit`
   - 标签：`TAGS_FOR_ALL_LLM`

7. **action_fuzz_file_read_or_include**
   - 描述：使用payload测试文件读取/包含漏洞。
   - 类型：`exploit`
   - 标签：`TAGS_FOR_ALL_LLM`

8. **action_exploit_from_payload**
   - 描述：根据payload生成并执行Python脚本。
   - 类型：`exploit`
   - 标签：`TAGS_FOR_ALL_LLM`

## 总结类 Action

1. **write_report_markdown**
   - 描述：总结攻击成果并生成报告。
   - 类型：`summarize`
   - 标签：`TAGS_FOR_ALL_LLM`

---

以上是VulnCat项目中所有的Action及其功能描述。