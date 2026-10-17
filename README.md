# Linux Process Tree Visualizer

A real-time web application that shows every running process on a Linux machine as a
parent-child tree, built for the OSSP hackathon (Team 3, Section 9).

* **Backend:** Python 3 standard library only. Reads `/proc/<pid>/stat`, `cmdline`, `status`, `fd`.
* **Frontend:** single HTML file, vanilla JavaScript, no CDN, so it works offline.
* **Read-only:** it never sends signals to or modifies any process. It binds to `127.0.0.1` by default.

## Requirements

* Linux (Ubuntu or WSL2 Ubuntu), Python 3.8+. Nothing to install and nothing to compile.

## Run

```bash
git clone <your-repo-url> && cd process-tree-visualizer
python3 server.py                 # open http://127.0.0.1:8080
python3 server.py --port 9000 --interval 0.5     # optional flags
```

## Demo (for the live presentation)

In a second terminal, create a safe, visible process tree:

```bash
python3 demo_spawn.py             # Ctrl+C removes everything it created
```

Then in the browser: search `demo`, click **Expand all**, and watch:

| What you see | OS concept it demonstrates |
|---|---|
| `demo-root` with 3 workers and 6 leaves | `fork()` builds a process hierarchy |
| `flash` rows turning green, then red and struck through | process creation and termination, live |
| `zombie-kid` in red, state *Zombie* | child exited, parent has not called `wait()` |
| `cpu-burner` at about 30 % CPU | per-process CPU from `/proc` tick deltas |
| Kill a worker from another terminal (`kill <pid>`): its leaves jump to PID 1 | orphan re-parenting to `init` |

## Features

* Live tree list and SVG graph view with refresh every 1, 2 or 5 seconds, plus pause
* Collapse and expand any subtree (graph view: double-click a node)
* Filter by name, PID, user or command (ancestors of matches stay visible)
* Colour-coded states: running, sleeping, disk wait, zombie, stopped, idle
* New processes flash green, exited ones stay struck-through for 3 s
* Detail panel: user, CPU %, RSS, threads, uptime, exe path, cwd, open fds, context switches, ancestry to init
* Live counters: processes, running, sleeping, zombies, threads

## API

| Endpoint | Returns |
|---|---|
| `GET /api/processes` | flat list of all processes (cached snapshot) |
| `GET /api/tree` | nested tree under a virtual `system` root |
| `GET /api/process/<pid>` | extra details for one process, 404 if gone |
| `GET /api/health` | `{"ok": true}` |

## Tests

```bash
python3 test_server.py -v
```

Covers: `/proc/<pid>/stat` parsing with odd names like `my (odd) proc`, real parent-child
links, tree nesting, detail endpoint and 404, and exited processes disappearing.

## Project layout

```
server.py          backend: /proc sampler + HTTP API
static/index.html  web UI
demo_spawn.py      demo process-tree generator
test_server.py     unit and integration tests
docs/REPORT.md     project report
docs/PPT_OUTLINE.md  slide-by-slide outline
```

## Limitations

* Linux only (needs `/proc`). Some details (exe, cwd, fds) are unreadable for other users' processes unless run as root.
* Polling model (1 s default); processes that live shorter than one interval can be missed.
