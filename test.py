import mistune
from linhai.markdown_parser import CodeBlockRenderer

md = """
```json toolcall
{}
```
"""


renderer = CodeBlockRenderer()
markdown = mistune.create_markdown(renderer=renderer)
markdown(md)
for block in renderer.code_blocks:
    print(block)
