import json
import os
import subprocess
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

import server


def find(node, pid):
    if node.get("pid") == pid:
        return node
    for c in node.get("children", []):
        r = find(c, pid)
        if r:
            return r
    return None


class ParseTests(unittest.TestCase):
    def test_comm_with_spaces_and_parens(self):
        rest = ["S", "42"] + ["0"] * 50
        rest[11], rest[12], rest[17], rest[19], rest[21] = "100", "50", "4", "1000", "10"
        p = server.parse_stat("123 (my (odd) proc) " + " ".join(rest))
        self.assertEqual((p["pid"], p["name"], p["state"], p["ppid"]), (123, "my (odd) proc", "S", 42))
        self.assertEqual((p["ticks"], p["threads"]), (150, 4))


class LiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.child = subprocess.Popen(["sleep", "60"])
        time.sleep(0.3)
        server.refresh()
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.child.terminate()
        cls.child.wait()
        cls.srv.shutdown()

    def get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}") as r:
            return json.loads(r.read())

    def test_parent_child_link(self):
        procs = {p["pid"]: p for p in self.get("/api/processes")["processes"]}
        self.assertIn(self.child.pid, procs)
        self.assertEqual(procs[self.child.pid]["ppid"], os.getpid())

    def test_tree_nesting(self):
        tree = self.get("/api/tree")["tree"]
        parent = find(tree, os.getpid())
        self.assertIsNotNone(parent)
        self.assertIn(self.child.pid, [c["pid"] for c in parent["children"]])

    def test_detail_and_404(self):
        self.assertEqual(self.get(f"/api/process/{os.getpid()}")["pid"], os.getpid())
        with self.assertRaises(urllib.error.HTTPError):
            self.get("/api/process/99999999")

    def test_exited_process_disappears(self):
        c = subprocess.Popen(["sleep", "60"])
        time.sleep(0.2)
        server.refresh()
        self.assertTrue(any(p["pid"] == c.pid for p in server.get_snapshot()["processes"]))
        c.terminate()
        c.wait()
        server.refresh()
        self.assertFalse(any(p["pid"] == c.pid for p in server.get_snapshot()["processes"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
