"""Real end-to-end MCP round-trip: spawn the actual installed server binary
via stdio and call tools through a real ClientSession. This is the only
level of testing that proves the tool registration/schema plumbing
actually works -- unit tests on the plain functions can all pass while the
server itself is misconfigured.

Requires Safari to be running with automation permission already granted
(same as any other safari-mcp usage) -- these tests drive real Safari.
"""
import asyncio
import shutil

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    server_bin = shutil.which("safari-mcp-server")
    assert server_bin, "safari-mcp-server not found on PATH -- is the package installed?"

    params = StdioServerParameters(command=server_bin, args=[])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}
            expected = {
                "safari_tabs", "safari_open", "safari_close", "safari_read",
                "safari_js", "safari_click", "safari_fill",
                "safari_element_exists", "safari_wait_for",
            }
            missing = expected - tool_names
            assert not missing, f"missing tools: {missing}"
            print(f"OK: all {len(expected)} expected tools registered")

            result = await session.call_tool("safari_open", {"url": "https://example.com"})
            print("safari_open result:", result.content[0].text if result.content else result)

            result = await session.call_tool("safari_read", {})
            print("safari_read result:", result.content[0].text if result.content else result)

            result = await session.call_tool("safari_tabs", {})
            text = result.content[0].text if result.content else ""
            print("safari_tabs result (truncated):", text[:200])

    print("\nEnd-to-end MCP round-trip: PASSED")


if __name__ == "__main__":
    asyncio.run(main())
