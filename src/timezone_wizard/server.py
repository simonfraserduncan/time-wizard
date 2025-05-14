from datetime import datetime, timedelta
from enum import Enum
import json
from typing import Sequence
import asyncio # For serve and if __name__ == "__main__"
import sys # For stderr debug prints

from zoneinfo import ZoneInfo
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from mcp.shared.exceptions import McpError

from pydantic import BaseModel


class TimeTools(str, Enum):
    GET_CURRENT_TIME = "get_current_time"
    CONVERT_TIME = "convert_time"


class TimeResult(BaseModel):
    timezone: str
    datetime: str
    is_dst: bool


class TimeConversionResult(BaseModel):
    source: TimeResult
    target: TimeResult
    time_difference: str


# Removed TimeConversionInput as it wasn't used in the stdio reference server.py

def get_local_tz(local_tz_override: str | None = None) -> ZoneInfo:
    print("DEBUG: get_local_tz() called.", file=sys.stderr)
    if local_tz_override:
        print(f"DEBUG: get_local_tz() using override: {local_tz_override}", file=sys.stderr)
        return ZoneInfo(local_tz_override)

    print("DEBUG: get_local_tz() attempting to get system timezone.", file=sys.stderr)
    try:
        tzinfo = datetime.now().astimezone(tz=None).tzinfo
        if tzinfo is not None:
            print(f"DEBUG: get_local_tz() system tzinfo found: {tzinfo}", file=sys.stderr)
            # Convert abbreviated timezone to IANA name if needed
            try:
                zi = ZoneInfo(str(tzinfo))
                print(f"DEBUG: get_local_tz() successfully created ZoneInfo from system: {zi}", file=sys.stderr)
                return zi
            except Exception as e_zi:
                print(f"DEBUG: get_local_tz() failed to create ZoneInfo from tzinfo '{tzinfo}': {e_zi}. Defaulting to UTC.", file=sys.stderr)
                pass # Fall through to UTC
    except Exception as e_dt:
        print(f"DEBUG: get_local_tz() failed to get system tzinfo: {e_dt}. Defaulting to UTC.", file=sys.stderr)
        pass # Fall through to UTC
    
    print("DEBUG: get_local_tz() defaulting to UTC.", file=sys.stderr)
    return ZoneInfo("UTC")


def get_zoneinfo(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except Exception as e:
        raise McpError(f"Invalid timezone: '{timezone_name}'. Details: {str(e)}")


class TimeServer:
    def get_current_time(self, timezone_name: str) -> TimeResult:
        """Get current time in specified timezone"""
        timezone = get_zoneinfo(timezone_name)
        current_time = datetime.now(timezone)

        return TimeResult(
            timezone=timezone_name,
            datetime=current_time.isoformat(timespec="seconds"),
            is_dst=bool(current_time.dst()),
        )

    def convert_time(
        self, source_tz: str, time_str: str, target_tz: str
    ) -> TimeConversionResult:
        """Convert time between timezones"""
        source_timezone = get_zoneinfo(source_tz)
        target_timezone = get_zoneinfo(target_tz)

        try:
            parsed_time = datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            raise McpError(f"Invalid time format for '{time_str}'. Expected HH:MM [24-hour format].")

        now = datetime.now(source_timezone)
        source_time = datetime(
            now.year,
            now.month,
            now.day,
            parsed_time.hour,
            parsed_time.minute,
            tzinfo=source_timezone,
        )

        target_time = source_time.astimezone(target_timezone)
        source_offset = source_time.utcoffset() or timedelta()
        target_offset = target_time.utcoffset() or timedelta()
        hours_difference = (target_offset - source_offset).total_seconds() / 3600

        if hours_difference.is_integer():
            time_diff_str = f"{hours_difference:+.1f}h"
        else:
            # For fractional hours like Nepal's UTC+5:45
            time_diff_str = f"{hours_difference:+.2f}".rstrip("0").rstrip(".") + "h"

        return TimeConversionResult(
            source=TimeResult(
                timezone=source_tz,
                datetime=source_time.isoformat(timespec="seconds"),
                is_dst=bool(source_time.dst()),
            ),
            target=TimeResult(
                timezone=target_tz,
                datetime=target_time.isoformat(timespec="seconds"),
                is_dst=bool(target_time.dst()),
            ),
            time_difference=time_diff_str,
        )


async def serve(local_timezone_arg: str | None = None) -> None: 
    print("DEBUG: serve() called.", file=sys.stderr)
    server = Server("timezone-wizard") 
    timezone_wizard_logic = TimeServer() 

    print("DEBUG: serve(): About to call get_local_tz().", file=sys.stderr)
    # local_tz = str(get_local_tz(local_timezone_arg)) # Temporarily commented out for debugging
    local_tz = "UTC" # Temporarily hardcoded for debugging
    print(f"DEBUG: serve(): get_local_tz() SKIPPED. local_tz hardcoded to: {local_tz}", file=sys.stderr)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        print("DEBUG: list_tools() called.", file=sys.stderr)
        tools = [
            Tool(
                name=TimeTools.GET_CURRENT_TIME.value,
                description="Get current time in a specific timezone", 
                inputSchema={
                    "type": "object",
                    "properties": {
                        "timezone": {
                            "type": "string",
                            "description": f"IANA timezone name (e.g., 'America/New_York', 'Europe/London'). Use '{local_tz}' as local timezone if no timezone provided by the user.",
                        }
                    },
                    "required": ["timezone"],
                },
            ),
            Tool(
                name=TimeTools.CONVERT_TIME.value,
                description="Convert time between timezones",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_timezone": {
                            "type": "string",
                            "description": f"Source IANA timezone name (e.g., 'America/New_York', 'Europe/London'). Use '{local_tz}' as local timezone if no source timezone provided by the user.",
                        },
                        "time": {
                            "type": "string",
                            "description": "Time to convert in 24-hour format (HH:MM)",
                        },
                        "target_timezone": {
                            "type": "string",
                            "description": f"Target IANA timezone name (e.g., 'Asia/Tokyo', 'America/San_Francisco'). Use '{local_tz}' as local timezone if no target timezone provided by the user.",
                        },
                    },
                    "required": ["source_timezone", "time", "target_timezone"],
                },
            ),
        ]
        print(f"DEBUG: list_tools() returning: {json.dumps([t.model_dump() for t in tools], indent=2)}", file=sys.stderr)
        return tools

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict
    ) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        print(f"DEBUG: call_tool() called for '{name}' with args: {arguments}", file=sys.stderr)
        
        try:
            result_model = None # To store Pydantic model before .model_dump()
            match name:
                case TimeTools.GET_CURRENT_TIME.value:
                    timezone_arg = arguments.get("timezone")
                    if not timezone_arg:
                        print(f"DEBUG: call_tool({name}): 'timezone' arg missing, defaulting to local_tz: {local_tz}", file=sys.stderr)
                        timezone_arg = local_tz
                    
                    result_model = timezone_wizard_logic.get_current_time(timezone_arg)

                case TimeTools.CONVERT_TIME.value:
                    source_tz_arg = arguments.get("source_timezone")
                    time_arg = arguments.get("time")
                    target_tz_arg = arguments.get("target_timezone")

                    if not time_arg: # time is always required
                        raise McpError("Missing required argument for convert_time: time")

                    if not source_tz_arg:
                        print(f"DEBUG: call_tool({name}): 'source_timezone' arg missing, defaulting to local_tz: {local_tz}", file=sys.stderr)
                        source_tz_arg = local_tz
                    if not target_tz_arg:
                        print(f"DEBUG: call_tool({name}): 'target_timezone' arg missing, defaulting to local_tz: {local_tz}", file=sys.stderr)
                        target_tz_arg = local_tz
                        
                    result_model = timezone_wizard_logic.convert_time(
                        source_tz_arg,
                        time_arg,
                        target_tz_arg,
                    )
                case _:
                    print(f"ERROR: call_tool(): Unknown tool: '{name}'", file=sys.stderr)
                    raise McpError(f"Unknown tool: {name}") # Use McpError for client-facing errors

            if result_model is None:
                print(f"ERROR: call_tool(): result_model is None for tool '{name}', this is unexpected.", file=sys.stderr)
                raise McpError(f"Internal server error: No result generated for tool '{name}'.")

            response_text = json.dumps(result_model.model_dump(), indent=2)
            print(f"DEBUG: call_tool() for '{name}' returning: {response_text}", file=sys.stderr)
            return [TextContent(type="text", text=response_text)]

        except McpError as e: # Catch our specific McpErrors to pass them on
            print(f"ERROR: call_tool() for '{name}' raised McpError: {str(e)}", file=sys.stderr)
            raise # Re-raise McpError as is
        except ValueError as e: # Catch ValueErrors from our logic (e.g. strptime)
            print(f"ERROR: call_tool() for '{name}' raised ValueError: {str(e)}", file=sys.stderr)
            raise McpError(f"Invalid arguments for tool '{name}': {str(e)}")
        except Exception as e: # Catch any other unexpected errors
            print(f"ERROR: call_tool() for '{name}' raised unexpected Exception: {str(e)}", file=sys.stderr)
            raise McpError(f"An unexpected error occurred while processing tool '{name}'.")

    print("DEBUG: serve(): Creating initialization options.", file=sys.stderr)
    options = server.create_initialization_options()
    print(f"DEBUG: serve(): Server options created: {options}", file=sys.stderr)
    
    print("DEBUG: serve(): Entering stdio_server context manager.", file=sys.stderr)
    async with stdio_server() as (read_stream, write_stream):
        print("DEBUG: serve(): stdio_server streams obtained. Running server.run().", file=sys.stderr)
        await server.run(read_stream, write_stream, options)
    
    print("DEBUG: serve(): server.run() completed or exited.", file=sys.stderr)

# If running this script directly (optional, for local testing)
if __name__ == "__main__":
    print("DEBUG: Script invoked directly.", file=sys.stderr)
    # Add a handler for asyncio exceptions for better debugging if run directly
    def handle_exception(loop, context):
        print(f"ERROR: Asyncio exception: {context['message']}", file=sys.stderr)
        if 'exception' in context:
            print(f"ERROR: Exception details: {context['exception']}", file=sys.stderr)
        sys.exit(1)

    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)
    try:
        print("DEBUG: __main__: Starting asyncio event loop with serve().", file=sys.stderr)
        loop.run_until_complete(serve())
    except KeyboardInterrupt:
        print("DEBUG: __main__: KeyboardInterrupt caught, stopping server.", file=sys.stderr)
    except Exception as e:
        print(f"ERROR: __main__: Unhandled exception in main loop: {e}", file=sys.stderr)
    finally:
        print("DEBUG: __main__: Closing asyncio event loop.", file=sys.stderr)
        loop.close() 