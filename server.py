#!/usr/bin/env python3
"""Linux Process Tree Visualizer - backend.

Reads /proc directly (no third-party packages), samples it in a background
thread, and serves a JSON API plus the static web UI. Read-only: it never
sends signals to, or modifies, any process.
"""
import argparse
import json
import os
import pwd
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

CLK = os.sysconf("SC_CLK_TCK")      # clock ticks per second
PAGE = os.sysconf("SC_PAGE_SIZE")   # bytes per memory page
STATIC = Path(__file__).resolve().parent / "static"

_prev = {}            # pid -> (cpu_ticks, sample_time, start_ticks)
_snapshot = {"ts": 0, "hostname": "", "count": 0, "processes": []}
_lock = threading.Lock()
_users = {}


def parse_stat(raw):
    """Parse the text of /proc/<pid>/stat.

    The command name sits in parentheses and may itself contain spaces or
    parentheses, so split on the FIRST '(' and the LAST ')'.
    """
    l, r = raw.index("("), raw.rindex(")")
    rest = raw[r + 2:].split()
    return {
        "pid": int(raw[:l].strip()),
        "name": raw[l + 1:r],
        "state": rest[0],
        "ppid": int(rest[1]),
        "ticks": int(rest[11]) + int(rest[12]),   # utime + stime
        "threads": int(rest[17]),
        "start": int(rest[19]),
        "rss": int(rest[21]) * PAGE,
    }


def uname(uid):
    if uid not in _users:
        try:
            _users[uid] = pwd.getpwuid(uid).pw_name
        except KeyError:
            _users[uid] = str(uid)
    return _users[uid]


def read_process(pid):
    """Return one process record, or None if it vanished / is unreadable."""
    try:
        with open(f"/proc/{pid}/stat") as f:
            p = parse_stat(f.read())
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            cmd = f.read().replace(b"\0", b" ").decode("utf-8", "replace").strip()
        p["user"] = uname(os.stat(f"/proc/{pid}").st_uid)
    except (OSError, ValueError, IndexError):
        return None
    p["cmd"] = cmd[:300] if cmd else f"[{p['name']}]"   # kernel threads: no cmdline
    return p


_cpu_prev = None


def sys_stats():
    global _cpu_prev
    out = {"cores": os.cpu_count() or 1, "cpu": 0.0, "mem_total": 0, "mem_used": 0, "load": [0, 0, 0]}
    try:
        with open("/proc/stat") as f:
            v = [int(x) for x in f.readline().split()[1:]]
        idle, tot = v[3] + v[4], sum(v)
        if _cpu_prev and tot > _cpu_prev[0]:
            out["cpu"] = round(100 * ((tot - _cpu_prev[0]) - (idle - _cpu_prev[1])) / (tot - _cpu_prev[0]), 1)
        _cpu_prev = (tot, idle)
        mi = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, _, rest = line.partition(":")
                mi[k] = int(rest.split()[0]) * 1024
        out["mem_total"] = mi["MemTotal"]
        out["mem_used"] = mi["MemTotal"] - mi["MemAvailable"]
        out["load"] = [round(x, 2) for x in os.getloadavg()]
    except (OSError, ValueError, KeyError):
        pass
    return out


def take_snapshot():
    now = time.time()
    try:
        with open("/proc/uptime") as f:
            uptime = float(f.read().split()[0])
    except (OSError, ValueError):
        uptime = 0.0
    procs, alive = [], set()
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        p = read_process(int(entry))
        if p is None:
            continue
        pid, ticks, start = p["pid"], p.pop("ticks"), p.pop("start")
        old = _prev.get(pid)
        cpu = 0.0
        if old and old[2] == start and now > old[1]:      # same process, not a reused PID
            cpu = max(0.0, (ticks - old[0]) / CLK / (now - old[1]) * 100)
        _prev[pid] = (ticks, now, start)
        alive.add(pid)
        p["cpu"] = round(cpu, 1)
        p["age"] = int(max(0, uptime - start / CLK))
        procs.append(p)
    for pid in list(_prev):
        if pid not in alive:
            del _prev[pid]
    procs.sort(key=lambda x: x["pid"])
    return {"ts": now, "hostname": socket.gethostname(), "count": len(procs), "uptime": uptime, "sys": sys_stats(), "processes": procs}


def refresh():
    global _snapshot
    snap = take_snapshot()
    with _lock:
        _snapshot = snap


def get_snapshot():
    with _lock:
        return _snapshot


def sampler(interval):
    while True:
        time.sleep(interval)
        refresh()


def build_tree(procs):
    """Nested parent->children structure under a virtual 'system' root."""
    nodes = {p["pid"]: dict(p, children=[]) for p in procs}
    roots = []
    for n in nodes.values():
        parent = nodes.get(n["ppid"])
        if parent is not None and parent is not n:
            parent["children"].append(n)
        else:
            roots.append(n)      # PID 1 / kernel roots / orphans whose parent vanished
    return {"pid": 0, "name": "system", "children": roots}


STATUS_KEYS = {"Name", "State", "Tgid", "PPid", "Uid", "Threads", "VmSize", "VmRSS",
               "voluntary_ctxt_switches", "nonvoluntary_ctxt_switches"}


def detail(pid):
    if not os.path.isdir(f"/proc/{pid}"):
        return None
    d = {"pid": pid, "status": {}}
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                k, _, v = line.partition(":")
                if k in STATUS_KEYS:
                    d["status"][k] = v.strip()
    except OSError:
        pass
    for key in ("exe", "cwd"):
        try:
            d[key] = os.readlink(f"/proc/{pid}/{key}")
        except OSError:
            d[key] = None          # permission denied or kernel thread
    try:
        d["open_fds"] = len(os.listdir(f"/proc/{pid}/fd"))
    except OSError:
        d["open_fds"] = None
    return d


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="application/json"):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/health":
            self._send(200, {"ok": True})
        elif path == "/api/processes":
            self._send(200, get_snapshot())
        elif path == "/api/tree":
            snap = get_snapshot()
            self._send(200, {"ts": snap["ts"], "tree": build_tree(snap["processes"])})
        elif path.startswith("/api/process/"):
            tail = path.rsplit("/", 1)[1]
            d = detail(int(tail)) if tail.isdigit() else None
            self._send(200 if d else 404, d or {"error": "no such process"})
        else:
            self._send(404, {"error": "not found"})


def main():
    ap = argparse.ArgumentParser(description="Linux Process Tree Visualizer")
    ap.add_argument("--host", default="127.0.0.1", help="bind address (default: localhost only)")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--interval", type=float, default=1.0, help="sampling interval in seconds")
    args = ap.parse_args()
    refresh()
    threading.Thread(target=sampler, args=(args.interval,), daemon=True).start()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Process Tree Visualizer running at http://{args.host}:{args.port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
