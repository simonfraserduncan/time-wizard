import asyncio
import json
import subprocess
import time
import uuid
import httpx
import traceback


async def main():
    # Start the server as a subprocess
    server_process = subprocess.Popen(
        ["./.venv/bin/timezone-wizard", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    # Allow some time for the server to start up
    print("Starting server, waiting 2 seconds...")
    time.sleep(2)
    
    # Base URL for the MCP server
    base_url = "http://127.0.0.1:8000"
    
    try:
        print("\nAttempting to connect with proper session handling...")
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                # First, make an initial request to get a session ID
                print("Making initial request to get session ID...")
                initial_headers = {
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json"
                }
                
                # Initial request
                initial_response = await client.get(f"{base_url}/mcp/tools", headers=initial_headers)
                print(f"Initial response status: {initial_response.status_code}")
                
                # Extract the session ID from the response headers
                session_id = initial_response.headers.get("mcp-session-id")
                if session_id:
                    print(f"Received session ID: {session_id}")
                    
                    # Update headers with the session ID for subsequent requests
                    headers = {
                        **initial_headers,
                        "mcp-session-id": session_id
                    }
                    
                    try:
                        # Now try listing tools again with the session ID
                        print("\nFetching tool list with session ID...")
                        tools_response = await client.get(f"{base_url}/mcp/tools", headers=headers)
                        print(f"Tools response status: {tools_response.status_code}")
                        
                        if tools_response.status_code == 200:
                            try:
                                print(f"Raw response: {tools_response.text}")
                                tools = tools_response.json()
                                print("\nTOOLS REGISTERED WITH THE SERVER:")
                                for tool in tools:
                                    print(f" - {tool['name']}: {tool['description']}")
                                    if 'parameters' in tool:
                                        print(f"   Parameters: {json.dumps(tool.get('parameters', {}), indent=2)}")
                            except json.JSONDecodeError as e:
                                print(f"Error decoding JSON: {e}")
                                print(f"Raw response content: {tools_response.text}")
                        else:
                            print(f"Failed to get tools: {tools_response.status_code} - {tools_response.text}")
                        
                        try:
                            # Try calling get_current_time
                            print("\nTesting get_current_time...")
                            current_time_response = await client.post(
                                f"{base_url}/mcp/tools/get_current_time",
                                json={"timezone": "America/New_York"},
                                headers=headers
                            )
                            print(f"get_current_time response status: {current_time_response.status_code}")
                            
                            if current_time_response.status_code == 200:
                                try:
                                    print(f"Raw response: {current_time_response.text}")
                                    result = current_time_response.json()
                                    print("\nRESULT OF get_current_time:")
                                    print(json.dumps(result, indent=2))
                                except json.JSONDecodeError as e:
                                    print(f"Error decoding JSON: {e}")
                                    print(f"Raw response content: {current_time_response.text}")
                            else:
                                print(f"Failed to call get_current_time: {current_time_response.status_code} - {current_time_response.text}")
                        except Exception as e:
                            print(f"Error during get_current_time call: {e}")
                            traceback.print_exc()
                        
                        try:
                            # Try calling convert_time
                            print("\nTesting convert_time...")
                            convert_time_response = await client.post(
                                f"{base_url}/mcp/tools/convert_time",
                                json={
                                    "source_timezone": "America/New_York",
                                    "time": "15:30",
                                    "target_timezone": "Europe/London"
                                },
                                headers=headers
                            )
                            print(f"convert_time response status: {convert_time_response.status_code}")
                            
                            if convert_time_response.status_code == 200:
                                try:
                                    print(f"Raw response: {convert_time_response.text}")
                                    result = convert_time_response.json()
                                    print("\nRESULT OF convert_time:")
                                    print(json.dumps(result, indent=2))
                                except json.JSONDecodeError as e:
                                    print(f"Error decoding JSON: {e}")
                                    print(f"Raw response content: {convert_time_response.text}")
                            else:
                                print(f"Failed to call convert_time: {convert_time_response.status_code} - {convert_time_response.text}")
                        except Exception as e:
                            print(f"Error during convert_time call: {e}")
                            traceback.print_exc()
                    except Exception as e:
                        print(f"Error during tool operations: {e}")
                        traceback.print_exc()
                else:
                    print("No session ID received from server. Cannot proceed.")
            except Exception as e:
                print(f"Error during session setup: {e}")
                traceback.print_exc()
                
    except Exception as e:
        print(f"Error during API calls: {e}")
        traceback.print_exc()
    finally:
        # Terminate the server
        print("\nShutting down server...")
        server_process.terminate()
        stdout, stderr = server_process.communicate()
        if stdout:
            print(f"Server stdout: {stdout.decode()}")
        if stderr:
            print(f"Server stderr: {stderr.decode()}")


if __name__ == "__main__":
    asyncio.run(main()) 