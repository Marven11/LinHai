import json
import sys
import subprocess
import os
from pathlib import Path


class Trojan:
    def __init__(self):
        self.current_dir = os.getcwd()

    def run_command(self, command, timeout=30):
        """执行命令"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.current_dir,
            )
            output = f"返回码: {result.returncode}\n"
            if result.stdout:
                output += f"stdout:\n{result.stdout}\n"
            if result.stderr:
                output += f"stderr:\n{result.stderr}"
            return {"message": output}
        except subprocess.TimeoutExpired:
            return {"error": f"命令超时: {timeout}秒"}
        except Exception as e:
            return {"error": str(e)}

    def change_directory(self, directory):
        """改变当前目录"""
        try:
            os.chdir(directory)
            self.current_dir = os.getcwd()
            return {"message": f"已切换到目录: {self.current_dir}"}
        except Exception as e:
            return {"error": str(e)}

    def read_file(self, filepath, show_line_numbers=False):
        """读取文件"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            if show_line_numbers:
                lines = content.splitlines()
                numbered = [f"{i+1}: {line}" for i, line in enumerate(lines)]
                content = "\n".join(numbered)

            return {"message": content}
        except Exception as e:
            return {"error": str(e)}

    def write_file(self, filepath, content, override=False):
        """写入文件"""
        try:
            if os.path.exists(filepath) and not override:
                return {"error": f"文件已存在: {filepath}"}

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return {"message": f"文件已写入: {filepath}"}
        except Exception as e:
            return {"error": str(e)}

    def append_file(self, filepath, content, assume_empty_line=True):
        """追加文件"""
        try:
            if not os.path.exists(filepath):
                return {"error": f"文件不存在: {filepath}"}

            with open(filepath, "a", encoding="utf-8") as f:
                f.write(content)
            return {"message": f"内容已追加到: {filepath}"}
        except Exception as e:
            return {"error": str(e)}

    def replace_file_content(self, filepath, old, new, replace_times=None):
        """替换文件内容"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            if old not in content:
                return {"error": f"未找到内容: {old}"}

            if replace_times is None:
                if content.count(old) != 1:
                    return {"error": f"找到多次匹配: {content.count(old)}次"}
                new_content = content.replace(old, new, 1)
                count = 1
            elif replace_times > 0:
                new_content = content.replace(old, new, replace_times)
                count = replace_times
            elif replace_times == -1:
                new_content = content.replace(old, new)
                count = content.count(old)
            else:
                return {"error": f"无效的替换次数: {replace_times}"}

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            return {"message": f"已替换{count}次"}
        except Exception as e:
            return {"error": str(e)}

    def list_files(self, dirpath):
        """列出文件"""
        try:
            path = Path(dirpath)
            if not path.exists():
                return {"error": f"路径不存在: {dirpath}"}

            items = []
            for item in path.iterdir():
                items.append(
                    {
                        "name": item.name,
                        "is_dir": item.is_dir(),
                        "size": item.stat().st_size if item.is_file() else 0,
                    }
                )
            
            lines = []
            for item in items:
                dir_mark = "📁" if item["is_dir"] else "📄"
                size = f" ({item['size']}B)" if not item["is_dir"] else ""
                lines.append(f"{dir_mark} {item['name']}{size}")
            
            return {"message": "\n".join(lines)}
        except Exception as e:
            return {"error": str(e)}

    def get_absolute_path(self, path):
        """获取绝对路径"""
        try:
            abs_path = Path(path).absolute()
            return {"message": str(abs_path)}
        except Exception as e:
            return {"error": str(e)}

    def run_sed_expression(self, expression, filepath):
        """执行sed表达式"""
        try:
            result = subprocess.run(
                ["sed", "-n", expression, filepath], capture_output=True, text=True
            )
            if result.returncode != 0:
                return {"error": result.stderr}
            return {"message": result.stdout}
        except Exception as e:
            return {"error": str(e)}

    def modify_file_with_sed(self, expression, filepath):
        """使用sed修改文件"""
        try:
            import platform

            system = platform.system()
            if system == "Darwin":
                cmd = ["sed", "-i", "", expression, filepath]
            else:
                cmd = ["sed", "-i", expression, filepath]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return {"error": result.stderr}
            return {"message": "文件已修改"}
        except Exception as e:
            return {"error": str(e)}

    def insert_at_line(self, filepath, line_number, content, expected_line_content):
        """插入内容到指定行"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()

            if line_number < 1 or line_number > len(lines) + 1:
                return {"error": f"行号无效: {line_number}"}

            if line_number <= len(lines):
                actual_line = lines[line_number - 1].rstrip("\n")
                if actual_line != expected_line_content:
                    return {
                        "error": f"行内容不匹配: 实际'{actual_line}', 预期'{expected_line_content}'"
                    }

            content_with_newline = content if content.endswith("\n") else content + "\n"
            lines.insert(line_number - 1, content_with_newline)

            with open(filepath, "w", encoding="utf-8") as f:
                f.writelines(lines)

            return {"message": f"已插入到第{line_number}行"}
        except Exception as e:
            return {"error": str(e)}


def main():
    trojan = Trojan()

    for line in sys.stdin:
        request = None
        try:
            request = json.loads(line.strip())
            method = request.get("method")
            params = request.get("params", {})

            if hasattr(trojan, method):
                result = getattr(trojan, method)(**params)
                response = {"jsonrpc": "2.0", "id": request.get("id"), "result": result}
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {"message": f"方法未找到: {method}"},
                }

            print(json.dumps(response), flush=True)
        except Exception as e:
            request_id = None
            if request is not None:
                request_id = request.get("id")
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"message": str(e)},
            }
            print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
