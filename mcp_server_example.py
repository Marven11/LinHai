from mcp.server.fastmcp import FastMCP

mcp = FastMCP("calculator")

@mcp.tool()
async def add(a: float, b: float) -> str:
    """计算 a + b 并返回结果（作为字符串）。"""
    return str(a + b)

def main():
    # Initialize and run the server
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()