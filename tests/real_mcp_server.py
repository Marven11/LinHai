#!/usr/bin/env python3
"""A real MCP server for testing with calculator tools."""

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("real-mcp-test-server")


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
    """Initialize and run the server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
