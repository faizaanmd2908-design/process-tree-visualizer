# Project Report - Linux Process Tree Visualizer

**Course:** Operating Systems and System Programming  |  **Team:** 3, Section 9
**Members and roles:** _(fill in: name - role, e.g. backend /proc parser, frontend, testing, docs/PPT)_

## 1. Problem statement
Build a tool that displays the hierarchy of running processes and their parent-child
relationships in real time, as a complete working web application.

## 2. Objectives
* Show all processes as a live parent-child tree.
* Show state, CPU, memory, threads and command per process.
* Make process creation, termination, zombies and orphans visible.
* Stay read-only and safe to run on a shared machine.

## 3. OS concepts used
* **Process hierarchy:** every process has a PPID; the tree is rooted at PID 1 (`init`/`systemd`).
* **`fork()`/`exec()`/`wait()`:** demo script uses `fork()` to build trees and `waitpid()` to reap children.
* **Process states:** R, S, D, Z, T, I as exposed in `/proc/<pid>/stat`.
* **Zombies and orphans:** a zombie is an exited child not yet waited on; orphans are re-parented to init.
* **`/proc` pseudo-filesystem:** kernel state exposed as files (`stat`, `status`, `cmdline`, `fd`, `exe`, `cwd`).
* **CPU accounting:** `utime + stime` in clock ticks (`SC_CLK_TCK`); CPU % = delta ticks / (ticks per second x elapsed seconds).
* **Memory accounting:** RSS = resident pages x page size (`SC_PAGE_SIZE`).

## 4. System design
```
 Linux kernel /proc  ->  sampler thread (every 1 s)  ->  cached snapshot  ->  HTTP JSON API  ->  browser UI
```
* **Sampler:** lists numeric directories in `/proc`, parses each process, computes CPU % from the previous sample, drops vanished PIDs.
* **API:** `ThreadingHTTPServer`; handlers serve the cached snapshot, so many browsers cost no extra `/proc` reads.
* **UI:** builds the tree from `pid -> ppid` links, diffs successive snapshots to detect births and deaths, renders a tree list or SVG graph.

## 5. Implementation notes
* `/proc/<pid>/stat` is parsed by splitting on the first `(` and last `)` because the command name may contain spaces or brackets.
* PID reuse is guarded by comparing the process start time before computing CPU deltas.
* Processes that disappear mid-read (race with exit) are skipped, not treated as errors.
* Orphans whose parent is missing are attached to a virtual `system` root so nothing is lost.
* Kernel threads have empty `cmdline`; they are displayed as `[name]`.

## 6. Technologies
Python 3 (standard library), HTML/CSS/vanilla JavaScript, SVG, Linux `/proc`, Git/GitHub.

## 7. Testing and validation
| # | Scenario | Expected | Result |
|---|---|---|---|
| 1 | Parse stat line with name `my (odd) proc` | name and PPID extracted correctly | Pass |
| 2 | Start `sleep 60` from test | child appears with PPID = test PID | Pass |
| 3 | `/api/tree` | child nested under parent | Pass |
| 4 | `/api/process/<pid>`; invalid PID | details; 404 | Pass |
| 5 | Terminate a process | disappears from next snapshot | Pass |
| 6 | `demo_spawn.py` | demo-root has 3 workers (2 leaves each), burner, zombie parent | Pass |
| 7 | Live UI | flash children appear green then struck-through; zombie shown red | Verify in demo |

Run with `python3 test_server.py -v`.

## 8. Results
The tool shows the full process tree of the host with sub-second refresh, makes forks, exits, zombies
and re-parenting visible, and costs negligible CPU because sampling is centralised.

## 9. Impact
Helps students learn process relationships visually, helps admins find runaway or zombie processes
and trace any process to its ancestors, and doubles as a teaching aid for `fork`/`wait` concepts.

## 10. Safety and responsible use
Read-only, no signals sent, localhost-bound by default, demo script only touches processes it created.

## 11. Future work
Event-driven updates (netlink proc connector), per-process CPU history charts, thread-level view,
container/cgroup grouping, optional authenticated kill action.
