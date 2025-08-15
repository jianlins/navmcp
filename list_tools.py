import asyncio
from fastmcp import Client

async def main():
    # Connect to /sse endpoint without session_id
    client = Client("http://127.0.0.1:3333/sse")
    async with client:
        tools = await client.list_tools()
        print("Available tools:", [tool.name for tool in tools])

if __name__ == "__main__":
    asyncio.run(main())
