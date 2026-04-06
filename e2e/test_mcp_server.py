from mcp.server.fastmcp import FastMCP

mcp = FastMCP("test-server")


@mcp.tool()
async def add(a: float, b: float) -> float:
    """Add two numbers.

    Args:
        a: First number
        b: Second number

    Returns:
        The sum of a and b
    """
    return a + b


@mcp.tool()
async def multiply(a: float, b: float) -> float:
    """Multiply two numbers.

    Args:
        a: First number
        b: Second number

    Returns:
        The product of a and b
    """
    return a * b


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
