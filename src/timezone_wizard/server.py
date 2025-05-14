from datetime import datetime, timedelta
from enum import Enum
import json
from typing import Sequence

from zoneinfo import ZoneInfo
from mcp.server import Server
from mcp.server.fastmcp import FastMCP
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


class TimeConversionInput(BaseModel):
    source_tz: str
    time: str
    target_tz_list: list[str]


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
            # For fractional hours like Nepal\'s UTC+5:45
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


async def serve(local_timezone: str | None = None, host: str = "0.0.0.0", port: int = 8000) -> None:
    """Start the timezone-wizard MCP server"""
    time_server = TimeServer()
    local_tz = str(get_local_tz(local_timezone))
    
    # Create a FastMCP app
    app = FastMCP(name="timezone-wizard")
    
    # Register tools
    @app.tool(
        name=TimeTools.GET_CURRENT_TIME.value,
        description="Get current time in a specific timezone"
    )
    async def get_current_time(timezone: str) -> dict:
        """Get current time in specified timezone"""
        result = time_server.get_current_time(timezone)
        return result.model_dump()
    
    @app.tool(
        name=TimeTools.CONVERT_TIME.value,
        description="Convert time between timezones"
    )
    async def convert_time(
        source_timezone: str,
        time: str,
        target_timezone: str
    ) -> dict:
        """Convert time between timezones"""
        result = time_server.convert_time(
            source_timezone,
            time,
            target_timezone
        )
        return result.model_dump()
    
    # Start the server using Uvicorn with the correct app
    print(f"Starting timezone-wizard server on {host}:{port}...")
    import uvicorn
    # Get the ASGI application from FastMCP
    asgi_app = app.streamable_http_app()
    # Configure and start Uvicorn
    config = uvicorn.Config(asgi_app, host=host, port=port)
    server = uvicorn.Server(config)
    await server.serve() 