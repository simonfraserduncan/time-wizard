import asyncio
import subprocess
import json
from mcp.client import Client


async def main():
    # Start the server as a subprocess
    server_process = subprocess.Popen(
        ["timezone-wizard"], 
        stdin=subprocess.PIPE, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    # Create a stdio-based client
    client = Client(
        stdin=server_process.stdout,
        stdout=server_process.stdin,
    )
    
    try:
        # Initialize the client with server
        await client.initialize({})
        
        # List tools to check the tool registry
        tools = await client.list_tools()
        print("TOOLS REGISTERED WITH THE SERVER:")
        for tool in tools:
            print(f" - {tool.name}: {tool.description}")
            print(f"   Input schema: {json.dumps(tool.input_schema, indent=2)}")
        
        # Test calling a tool
        if tools:
            # Example: Getting current time in a specific timezone
            if any(tool.name == "get_current_time" for tool in tools):
                result = await client.call_tool("get_current_time", {"timezone": "America/New_York"})
                print("\nRESULT OF get_current_time:")
                print(result)
            
            # Example: Converting time between timezones
            if any(tool.name == "convert_time" for tool in tools):
                result = await client.call_tool(
                    "convert_time", 
                    {
                        "source_timezone": "America/New_York", 
                        "time": "15:30", 
                        "target_timezone": "Europe/London"
                    }
                )
                print("\nRESULT OF convert_time:")
                print(result)
        
    finally:
        # Close the client and terminate the server
        await client.close()
        server_process.terminate()
        server_process.wait()


if __name__ == "__main__":
    asyncio.run(main()) 