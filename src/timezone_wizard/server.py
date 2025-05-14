from datetime import datetime, timedelta
from enum import Enum
import json
from typing import Sequence
import asyncio # Added asyncio for the serve function
import sys # For stderr printing

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
    if local_tz_override:
        return ZoneInfo(local_tz_override)

    # Default to UTC if we can't determine the local timezone
    try:
        # Try to get local timezone from datetime.now()
        tzinfo = datetime.now().astimezone(tz=None).tzinfo
        if tzinfo is not None:
            # Convert abbreviated timezone to IANA name if needed
            try:
                return ZoneInfo(str(tzinfo))
            except Exception:
                # If we can't get the timezone name directly, default to UTC
                pass
    except Exception:
        pass
        
    # Default to UTC
    return ZoneInfo("UTC")


def get_zoneinfo(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except Exception as e:
        raise McpError(f"Invalid timezone: {str(e)}")


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
            raise ValueError("Invalid time format. Expected HH:MM [24-hour format]")

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


async def serve(local_timezone_override: str | None = None) -> None: 
    print("DEBUG: serve() called", file=sys.stderr) # DEBUG
    server = Server("timezone-wizard") 
    time_wizard_server = TimeServer() 
    # local_tz = str(get_local_tz(local_timezone_override)) # DEFER THIS

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        print("DEBUG: list_tools() called", file=sys.stderr) # DEBUG
        # Use a placeholder for local_tz in descriptions for now
        # The actual local_tz will be determined in call_tool if needed
        local_tz_placeholder = "<local_timezone_placeholder (see tool call for actual default)>"
        
        tools = [
            Tool(
                name=TimeTools.GET_CURRENT_TIME.value,
                description="Get current time in a specific timezone", 
                inputSchema={
                    "type": "object",
                    "properties": {
                        "timezone": {
                            "type": "string",
                            "description": f"IANA timezone name (e.g., 'America/New_York', 'Europe/London'). Defaults to system local timezone ({local_tz_placeholder}) if not provided.",
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
                            "description": f"Source IANA timezone name. Defaults to system local timezone ({local_tz_placeholder}) if not provided.",
                        },
                        "time": {
                            "type": "string",
                            "description": "Time to convert in 24-hour format (HH:MM)",
                        },
                        "target_timezone": {
                            "type": "string",
                            "description": f"Target IANA timezone name. Defaults to system local timezone ({local_tz_placeholder}) if not provided.",
                        },
                    },
                    "required": ["source_timezone", "time", "target_timezone"],
                },
            ),
        ]
        print(f"DEBUG: list_tools() returning: {tools}", file=sys.stderr) # DEBUG
        return tools

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict
    ) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        print(f"DEBUG: call_tool() called for {name} with args: {arguments}", file=sys.stderr) # DEBUG
        # Determine local_tz now, only when a tool is actually called
        # This is "lazy loading" of this potentially slow operation.
        effective_local_tz = str(get_local_tz(local_timezone_override))
        print(f"DEBUG: effective_local_tz in call_tool: {effective_local_tz}", file=sys.stderr) # DEBUG

        try:
            match name:
                case TimeTools.GET_CURRENT_TIME.value:
                    timezone = arguments.get("timezone")
                    if not timezone:
                        timezone = effective_local_tz 
                    result = time_wizard_server.get_current_time(timezone)

                case TimeTools.CONVERT_TIME.value:
                    source_timezone = arguments.get("source_timezone")
                    time_arg = arguments.get("time") 
                    target_timezone = arguments.get("target_timezone")

                    if not source_timezone:
                        source_timezone = effective_local_tz
                    if not time_arg:
                        raise ValueError("Missing required argument: time")
                    if not target_timezone:
                        # Using effective_local_tz as a default for target_timezone
                        # if not provided, to align with the description.
                        target_timezone = effective_local_tz
                        
                    result = time_wizard_server.convert_time(
                        source_timezone,
                        time_arg,
                        target_timezone,
                    )
                case _:
                    raise ValueError(f"Unknown tool: {name}")

            return_val = [
                TextContent(type="text", text=json.dumps(result.model_dump(), indent=2))
            ]
            print(f"DEBUG: call_tool() for {name} returning: {return_val}", file=sys.stderr) # DEBUG
            return return_val

        except Exception as e:
            print(f"ERROR: call_tool() for {name} failed: {str(e)}", file=sys.stderr) # DEBUG
            raise McpError(f"Error processing timezone-wizard query for tool '{name}': {str(e)}")

    options = server.create_initialization_options()
    print(f"DEBUG: Server options created: {options}", file=sys.stderr) # DEBUG
    print("DEBUG: Entering stdio_server context manager", file=sys.stderr) # DEBUG
    async with stdio_server() as (read_stream, write_stream):
        print("DEBUG: stdio_server streams obtained. Running server.run()", file=sys.stderr) # DEBUG
        await server.run(read_stream, write_stream, options)
    print("DEBUG: server.run() completed or exited.", file=sys.stderr) # DEBUG

# If running this script directly (optional, for local testing)
if __name__ == "__main__":
    # Add a handler for asyncio exceptions for better debugging if run directly
    def handle_exception(loop, context):
        print(f"ERROR: Asyncio exception: {context['message']}", file=sys.stderr)
        if 'exception' in context:
            print(f"ERROR: Exception details: {context['exception']}", file=sys.stderr)
        sys.exit(1)

    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)
    try:
        loop.run_until_complete(serve())
    finally:
        loop.close() 