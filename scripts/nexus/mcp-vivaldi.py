#!/usr/bin/env python3
"""Vivaldi browser control via direct CDP — FastMCP stdio server for nexus."""

import asyncio
import base64
import json
import httpx
import websockets
from fastmcp import FastMCP

CDP_HTTP = "http://localhost:9222"
SCREENSHOT_DIR = "/home/fuchs/pictures"

mcp = FastMCP("fuchs-vivaldi")


def http_get(path: str):
    with httpx.Client(timeout=10) as client:
        return client.get(f"{CDP_HTTP}{path}").json()


async def _cdp(ws_url: str, method: str, params: dict = None, timeout: float = 15.0):
    async with websockets.connect(ws_url, ping_interval=None) as ws:
        await ws.send(json.dumps({"id": 1, "method": method, "params": params or {}}))
        while True:
            data = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
            if data.get("id") == 1:
                if "error" in data:
                    raise RuntimeError(data["error"].get("message", "CDP error"))
                return data.get("result", {})


def page_tabs() -> list:
    return [t for t in http_get("/json") if t.get("type") == "page"]


def find_tab(tab_id: str = None) -> dict | None:
    tabs = page_tabs()
    if not tabs:
        return None
    if tab_id:
        return next((t for t in tabs if t["id"] == tab_id), None)
    return tabs[0]


@mcp.tool()
def vivaldi_list_tabs() -> list:
    """List all open Vivaldi tabs with id, title, url."""
    return [{"id": t["id"], "title": t.get("title", ""), "url": t.get("url", "")} for t in page_tabs()]


@mcp.tool()
def vivaldi_new_tab(url: str = "about:blank") -> str:
    """Open a new tab in Vivaldi, optionally navigating to a URL."""
    with httpx.Client(timeout=10) as client:
        t = client.get(f"{CDP_HTTP}/json/new?{url}").json()
        return f"New tab: {t.get('id')} — {url}"


@mcp.tool()
def vivaldi_close_tab(tab_id: str) -> str:
    """Close a Vivaldi tab by its ID (get IDs from vivaldi_list_tabs)."""
    with httpx.Client(timeout=10) as client:
        return client.get(f"{CDP_HTTP}/json/close/{tab_id}").text.strip()


@mcp.tool()
async def vivaldi_activate_tab(tab_id: str) -> str:
    """Bring a tab to the foreground (switch to it). Get IDs from vivaldi_list_tabs."""
    tab = find_tab(tab_id)
    if not tab:
        return f"Tab not found: {tab_id}"
    await _cdp(tab["webSocketDebuggerUrl"], "Target.activateTarget", {"targetId": tab_id})
    return f"Activated: {tab.get('title', tab_id)}"


@mcp.tool()
async def vivaldi_navigate(url: str, tab_id: str = None) -> str:
    """Navigate a tab to a URL. Uses the first tab if tab_id is omitted."""
    tab = find_tab(tab_id)
    if not tab:
        return "No tab found"
    await _cdp(tab["webSocketDebuggerUrl"], "Page.navigate", {"url": url})
    return f"Navigated to {url}"


@mcp.tool()
async def vivaldi_screenshot(tab_id: str = None, filename: str = "vivaldi-screenshot.png") -> str:
    """Take a PNG screenshot of a Vivaldi tab. Saves to ~/pictures/."""
    tab = find_tab(tab_id)
    if not tab:
        return "No tab found"
    result = await _cdp(tab["webSocketDebuggerUrl"], "Page.captureScreenshot", {"format": "png"})
    data = result.get("data", "")
    if not data:
        return "No screenshot data received"
    path = f"{SCREENSHOT_DIR}/{filename}"
    with open(path, "wb") as f:
        f.write(base64.b64decode(data))
    return f"Screenshot saved: {path}"


@mcp.tool()
async def vivaldi_evaluate(js: str, tab_id: str = None) -> str:
    """Execute JavaScript in a Vivaldi tab and return the result (max 5000 chars)."""
    tab = find_tab(tab_id)
    if not tab:
        return "No tab found"
    result = await _cdp(tab["webSocketDebuggerUrl"], "Runtime.evaluate", {
        "expression": js,
        "returnByValue": True,
    })
    v = result.get("result", {}).get("value")
    return str(v)[:5000] if v is not None else json.dumps(result)


@mcp.tool()
async def vivaldi_get_text(tab_id: str = None) -> str:
    """Get the visible text content of the active page (max 4000 chars)."""
    tab = find_tab(tab_id)
    if not tab:
        return "No tab found"
    result = await _cdp(tab["webSocketDebuggerUrl"], "Runtime.evaluate", {
        "expression": "document.body?.innerText || ''",
        "returnByValue": True,
    })
    text = result.get("result", {}).get("value", "")
    return text[:4000]


@mcp.tool()
async def vivaldi_click(selector: str, tab_id: str = None) -> str:
    """Click a DOM element by CSS selector."""
    tab = find_tab(tab_id)
    if not tab:
        return "No tab found"
    js = f"""
(function() {{
    const el = document.querySelector({json.dumps(selector)});
    if (!el) return 'Element not found: {selector}';
    el.click();
    return 'Clicked: ' + el.tagName + (el.id ? '#' + el.id : '');
}})()
"""
    result = await _cdp(tab["webSocketDebuggerUrl"], "Runtime.evaluate", {
        "expression": js,
        "returnByValue": True,
    })
    return str(result.get("result", {}).get("value", "done"))


if __name__ == "__main__":
    mcp.run()
