import json, subprocess, sys, time, urllib.request
from pathlib import Path
import pytest

SRV = Path(__file__).resolve().parents[1] / "src" / "mcp_manager.py"
BOOT = "/tmp/boot-example.yaml"

@pytest.fixture(scope="module")
def server(tmp_path_factory):
    import urllib.request as u
    u.urlretrieve("https://raw.githubusercontent.com/Agentic-Operation/agent-bootstrap-management/main/examples/loyalty-agent/bootstrap.yaml", BOOT)
    proc = subprocess.Popen([sys.executable, str(SRV), "--port", "8496", "--store", str(tmp_path_factory.mktemp("s") / "t.json")],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    yield "http://localhost:8496"
    proc.terminate()

def post(url, obj):
    req = urllib.request.Request(url, data=json.dumps(obj).encode(), headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req)

def test_sync_and_list(server):
    r = post(f"{server}/v1/bootstraps/loyalty-management-agent-v1-bootstrap/tools/sync", {"path": BOOT})
    d = json.loads(r.read())
    assert d["servers"] == 2 and d["tools"] == 3
    with urllib.request.urlopen(f"{server}/v1/tools/E-commerce%20%2F%20POS") as r:
        t = json.loads(r.read())
    assert t["type"] == "mcp_tool" and t["mcp_server"] == "pos-and-ecom"
