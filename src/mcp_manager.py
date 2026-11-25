#!/usr/bin/env python3
"""tool-mcp-manager — registers and manages MCP servers / tool bindings from Spec-444 §3
(`tool_bindings`, `mcp_servers`), exposes them to agents, tracks auth scopes and health.

Endpoints (base /v1):
  POST /bootstraps/{id}/tools/sync    load tool_bindings + mcp_servers from a bootstrap YAML
  GET  /servers                       list MCP servers (+health)
  GET  /tools                         list tool bindings (name, type, server, auth_scope)
  GET  /tools/{name}                  tool detail incl. input schema placeholder
  POST /servers/{name}/health         probe health_check.endpoint (stub: records last_check)

Run: python src/mcp_manager.py --port 8092 --store tools.json
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import yaml


class Store:
    def __init__(self, path=None):
        self.servers = {}
        self.tools = {}
        self.path = path
        if path and Path(path).exists():
            d = json.load(open(path))
            self.servers, self.tools = d.get("servers", {}), d.get("tools", {})

    def save(self):
        if self.path:
            json.dump({"servers": self.servers, "tools": self.tools}, open(self.path, "w"), indent=2)


def sync_from_bootstrap(store, yaml_path, bootstrap_id):
    bp = (yaml.safe_load(open(yaml_path))).get("bootstrap_profile", {})
    for s in bp.get("mcp_servers", []):
        store.servers[s["name"]] = {**s, "bootstrap_id": bootstrap_id,
                                    "health": {"status": "unknown", "last_check": None}}
    for name, t in bp.get("tool_bindings", {}).items():
        store.tools[name] = {**t, "bootstrap_id": bootstrap_id}
    store.save()


class Handler(BaseHTTPRequestHandler):
    store: Store = None

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def log_message(self, *a):
        pass

    def do_GET(self):
        p = urlparse(self.path).path.strip("/").split("/")
        if p == ["v1", "servers"]:
            return self._send(200, list(self.store.servers.values()))
        if p == ["v1", "tools"]:
            return self._send(200, list(self.store.tools.values()))
        if len(p) == 3 and p[:2] == ["v1", "tools"]:
            t = self.store.tools.get(unquote(p[2]))
            return self._send(200, t) if t else self._send(404, {"error": "not found"})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        p = urlparse(self.path).path.strip("/").split("/")
        if len(p) == 5 and p[:2] == ["v1", "bootstraps"] and p[3] == "tools" and p[4] == "sync":
            sync_from_bootstrap(self.store, self._body()["path"], p[2])
            return self._send(200, {"servers": len(self.store.servers), "tools": len(self.store.tools)})
        if len(p) == 4 and p[:2] == ["v1", "servers"] and p[3] == "health":
            s = self.store.servers.get(unquote(p[2]))
            if not s:
                return self._send(404, {"error": "not found"})
            s["health"] = {"status": "healthy", "last_check": "2026-11-25T00:00:00Z"}  # stub probe
            self.store.save()
            return self._send(200, s["health"])
        return self._send(404, {"error": "not found"})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8092)
    ap.add_argument("--store", default=None)
    a = ap.parse_args()
    Handler.store = Store(a.store)
    print(f"tool-mcp-manager listening on :{a.port}")
    HTTPServer(("0.0.0.0", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
