"""Runtime patches that keep the browser -> Gradio server connection alive.

Adds a lightweight /wangp/heartbeat endpoint and injects a frontend script that
pings it every second from a background interval.  This prevents proxies, the
browser, and uvicorn from treating the connection as idle and closing it.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ENABLE_CONNECTION_KEEPALIVE = True
PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PATCH_SENTINEL = "window.__wangpConnectionKeepalive"
_TARGET_TEMPLATES = {"frontend/index.html", "frontend/share.html"}

_heartbeat_routes_installed = False
_heartbeat_original_create_app = None
_html_patch_installed = False
_html_original_get_source = None


def _get_javascript() -> str:
    if not ENABLE_CONNECTION_KEEPALIVE:
        return ""
    return f"""
(function () {{
  if (typeof window === "undefined" || window.__wangpConnectionKeepalive) {{
    return;
  }}
  window.__wangpConnectionKeepalive = true;

  const HEARTBEAT_INTERVAL_MS = 1000;
  const HEARTBEAT_TIMEOUT_MS = 3000;

  function pingServer() {{
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), HEARTBEAT_TIMEOUT_MS);
    fetch(`${{window.location.origin}}/wangp/heartbeat?t=${{Date.now()}}`, {{
      method: "GET",
      cache: "no-store",
      signal: controller.signal,
      headers: {{ "Accept": "application/json" }},
    }}).catch(() => {{}}).finally(() => clearTimeout(timeoutId));
  }}

  setInterval(pingServer, HEARTBEAT_INTERVAL_MS);
  pingServer();

  console.info("[WanGP keepalive] heartbeat installed");
}})();
"""


def _inject_script(template_source: str) -> str:
    if _PATCH_SENTINEL in template_source:
        return template_source
    script_tag = f"\n\t\t<script>\n{_get_javascript()}\n\t\t</script>\n"
    module_tag = '<script type="module"'
    insert_at = template_source.find(module_tag)
    if insert_at != -1:
        return template_source[:insert_at] + script_tag + template_source[insert_at:]
    head_close = template_source.find("</head>")
    if head_close != -1:
        return template_source[:head_close] + script_tag + template_source[head_close:]
    return template_source + script_tag


def install_html_patch() -> bool:
    global _html_patch_installed, _html_original_get_source
    if not ENABLE_CONNECTION_KEEPALIVE:
        return False
    if _html_patch_installed:
        return True

    import gradio.routes as gradio_routes

    templates = getattr(gradio_routes, "templates", None)
    loader = getattr(getattr(templates, "env", None), "loader", None)
    if loader is None:
        return False

    _html_original_get_source = loader.get_source

    def patched_get_source(environment, template):
        source, filename, uptodate = _html_original_get_source(environment, template)
        if template in _TARGET_TEMPLATES:
            source = _inject_script(source)
        return source, filename, uptodate

    loader.get_source = patched_get_source
    loader._wangp_connection_keepalive_installed = True
    _html_patch_installed = True
    templates.env.cache.clear()
    return True


def _install_heartbeat_route(fastapi_app) -> None:
    if getattr(fastapi_app, "_wangp_heartbeat_route_installed", False):
        return

    @fastapi_app.get("/wangp/heartbeat")
    async def _wangp_heartbeat():
        return {"status": "ok", "time": time.time()}

    fastapi_app._wangp_heartbeat_route_installed = True


def install_routes() -> bool:
    global _heartbeat_routes_installed, _heartbeat_original_create_app
    if not ENABLE_CONNECTION_KEEPALIVE:
        return False
    if _heartbeat_routes_installed:
        return True

    from gradio.routes import App

    _heartbeat_original_create_app = App.create_app

    def patched_create_app(*args, **kwargs):
        fastapi_app = _heartbeat_original_create_app(*args, **kwargs)
        _install_heartbeat_route(fastapi_app)
        return fastapi_app

    App.create_app = staticmethod(patched_create_app)
    _heartbeat_routes_installed = True
    return True


def install() -> bool:
    if not ENABLE_CONNECTION_KEEPALIVE:
        return False
    argv0 = Path(sys.argv[0]).name.lower() if sys.argv and sys.argv[0] else ""
    cwd = Path.cwd().resolve()
    if cwd != PROJECT_ROOT and PROJECT_ROOT not in cwd.parents and argv0 != "wgp.py":
        return False
    ok_routes = install_routes()
    ok_html = install_html_patch()
    return ok_routes or ok_html


__all__ = [
    "ENABLE_CONNECTION_KEEPALIVE",
    "install",
    "install_html_patch",
    "install_routes",
]
