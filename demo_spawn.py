#!/usr/bin/env python3
"""Builds a harmless, visible process tree for live demos.

Creates: demo-root -> 3 workers -> 2 leaves each, a CPU-light burner, a
zombie producer, and short-lived 'flash' children that appear and vanish.
Everything is cleaned up on Ctrl+C. Only processes created here are touched.
"""
import ctypes
import os
import signal
import sys
import time

libc = ctypes.CDLL(None)


def set_name(name):
    libc.prctl(15, name.encode()[:15], 0, 0, 0)     # PR_SET_NAME


kids = []


def stop(*_):
    for pid in kids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    os._exit(0)


def spawn(name, body):
    pid = os.fork()
    if pid:
        kids.append(pid)
        return pid
    kids.clear()
    set_name(name)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    body()
    os._exit(0)


def idle():
    while True:
        time.sleep(1)


def branch(spec):
    name, subs = spec
    def body():
        for s in subs:
            spawn(*_args(s))
        idle()
    return body


def _args(spec):
    return spec[0], branch(spec)


def burner():
    while True:                      # ~30% CPU
        end = time.time() + 0.03
        while time.time() < end:
            pass
        time.sleep(0.07)


def zombie_maker():
    while True:
        pid = os.fork()
        if pid == 0:
            set_name("zombie-kid")
            os._exit(0)              # exits at once; parent doesn't wait -> <defunct>
        time.sleep(12)
        os.waitpid(pid, 0)           # finally reaps it
        time.sleep(3)


def flash_child():
    set_name("flash")
    time.sleep(6)
    os._exit(0)


TREE = ("worker-1", [("leaf-1a", []), ("leaf-1b", [])]), \
       ("worker-2", [("leaf-2a", []), ("leaf-2b", [])]), \
       ("worker-3", [("leaf-3a", []), ("leaf-3b", [])])


def main():
    set_name("demo-root")
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    for t in TREE:
        spawn(*_args(t))
    spawn("cpu-burner", burner)
    spawn("zombie-parent", zombie_maker)
    print(f"demo tree running under PID {os.getpid()} - Ctrl+C to stop")
    while True:
        time.sleep(4)
        pid = os.fork()
        if pid == 0:
            flash_child()
        kids.append(pid)
        for k in list(kids):         # reap finished flash children
            try:
                done, _ = os.waitpid(k, os.WNOHANG)
                if done:
                    kids.remove(k)
            except ChildProcessError:
                kids.remove(k)


if __name__ == "__main__":
    if not sys.platform.startswith("linux"):
        sys.exit("Linux only")
    main()
