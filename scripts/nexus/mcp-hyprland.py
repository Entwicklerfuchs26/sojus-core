#!/usr/bin/env python3
import subprocess
import json
import os
from fastmcp import FastMCP

mcp = FastMCP("fuchs-hyprland")


def hyprctl(*args, as_json=True):
    cmd = ["hyprctl"]
    if as_json:
        cmd.append("-j")
    cmd.extend(str(a) for a in args)
    result = subprocess.run(cmd, capture_output=True, text=True,
                            env={**os.environ})
    if result.returncode != 0 and result.stderr:
        return {"error": result.stderr.strip()}
    if as_json and result.stdout.strip():
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return result.stdout.strip()
    return result.stdout.strip()


@mcp.tool()
def hypr_get_clients() -> list:
    """List all open windows with address, class, title, workspace, position, size."""
    return hyprctl("clients")


@mcp.tool()
def hypr_get_active_window() -> dict:
    """Get the currently focused window."""
    return hyprctl("activewindow")


@mcp.tool()
def hypr_get_workspaces() -> list:
    """List all workspaces with id, name, monitor, window count."""
    return hyprctl("workspaces")


@mcp.tool()
def hypr_get_monitors() -> list:
    """List all monitors with resolution, position, scale, active workspace."""
    return hyprctl("monitors")


@mcp.tool()
def hypr_get_binds() -> list:
    """List all configured keybindings."""
    return hyprctl("binds")


@mcp.tool()
def hypr_get_devices() -> dict:
    """List all input devices (keyboards, mice, tablets)."""
    return hyprctl("devices")


@mcp.tool()
def hypr_get_layers() -> dict:
    """List all layer surfaces (bars, notifications, overlays)."""
    return hyprctl("layers")


@mcp.tool()
def hypr_get_version() -> dict:
    """Get Hyprland version and build info."""
    return hyprctl("version")


@mcp.tool()
def hypr_dispatch(command: str, args: str = "") -> str:
    """
    Dispatch a Hyprland command. Examples:
    - workspace 2              → switch to workspace 2
    - movetoworkspace 3        → move active window to workspace 3
    - focuswindow class:firefox
    - closewindow address:0x...
    - movewindow l / r / u / d
    - resizeactive 100 0
    - togglefloating
    - fullscreen 0             → real fullscreen, 1 = maximize
    - exec kitty               → launch program
    - killactive               → close active window
    - cyclenext                → focus next window
    - swapnext                 → swap with next window
    - togglespecialworkspace
    - pin                      → pin floating window (visible on all workspaces)
    """
    if args:
        return hyprctl("dispatch", command, args, as_json=False)
    return hyprctl("dispatch", command, as_json=False)


@mcp.tool()
def hypr_keyword(keyword: str, value: str) -> str:
    """
    Set a Hyprland config keyword at runtime. Examples:
    - keyword general:gaps_out 10
    - keyword decoration:rounding 8
    - keyword animations:enabled false
    """
    return hyprctl("keyword", keyword, value, as_json=False)


@mcp.tool()
def hypr_reload() -> str:
    """Reload Hyprland config file."""
    return hyprctl("reload", as_json=False)


@mcp.tool()
def hypr_notify(icon: int, duration_ms: int, color: str, message: str) -> str:
    """
    Send a Hyprland built-in notification.
    icon: -1=no icon, 0=warning, 1=info, 2=hint, 3=error, 4=confused, 5=ok
    color: hex without # e.g. 'ff0000' or '0' for default
    duration_ms: e.g. 3000
    """
    return hyprctl("notify", str(icon), str(duration_ms), f"rgb({color})", message, as_json=False)


@mcp.tool()
def hypr_batch(commands: list[str]) -> str:
    """
    Run multiple hyprctl commands in one call.
    commands: list of 'dispatch workspace 2', 'keyword general:gaps_out 10', etc.
    """
    batch_str = " ; ".join(commands)
    result = subprocess.run(
        ["hyprctl", "--batch", batch_str],
        capture_output=True, text=True, env={**os.environ}
    )
    return result.stdout.strip() or result.stderr.strip()


if __name__ == "__main__":
    mcp.run()
