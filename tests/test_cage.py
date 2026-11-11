"""Tests for running issues with codex-cage: python3 -m unittest discover tests"""
import importlib.machinery
import importlib.util
import json
import os
import stat
import sys
import tempfile
import textwrap
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_loader = importlib.machinery.SourceFileLoader("herdr_issues", os.path.join(ROOT, "bin", "herdr-issues"))
hi = importlib.util.module_from_spec(importlib.util.spec_from_loader("herdr_issues", _loader))
_loader.exec_module(hi)

URL = "https://github.com/o/r/issues/7"

# Stands in for `codex-cage run`: writes the run's events and result where the
# real one does, then exits. FAKE_OUTCOME picks how the run ends.
FAKE_CODEX_CAGE = textwrap.dedent("""\
    #!{python}
    import json, os, sys
    args = sys.argv[1:]
    run_id = args[args.index("--run-id") + 1]
    result = args[args.index("--result-json") + 1]
    with open(os.environ["FAKE_LOG"] + ".cage", "w") as f:
        json.dump({{"args": args, "execution": os.environ.get("CODEX_CAGE_EXECUTION")}}, f)
    os.makedirs(".codex-cage/runs/" + run_id, exist_ok=True)
    events = [
        {{"type": "run.started", "payload": {{"issueKey": "#7", "issueTitle": "Add multiply()"}}}},
        {{"type": "stage.started", "stage": "prepare", "stageAttempt": 1, "payload": {{}}}},
        {{"type": "stage.started", "stage": "implement", "stageAttempt": 1, "payload": {{}}}},
        {{"type": "implementation.iteration_started", "stage": "implement", "stageAttempt": 1,
          "payload": {{"iteration": 2, "maxIterations": 3}}}},
        {{"type": "command.started", "payload": {{"command": "npm test"}}}},
        {{"type": "stage.started", "stage": "implement", "stageAttempt": 2, "payload": {{}}}},
    ]
    with open(".codex-cage/runs/%s/events.ndjson" % run_id, "w") as f:
        f.writelines(json.dumps(e) + "\\n" for e in events)
    outcome = os.environ["FAKE_OUTCOME"]
    if outcome == "crash":
        sys.exit(3)
    ok = outcome == "succeeded"
    with open(result, "w") as f:
        json.dump({{"runId": run_id, "status": outcome, "failureCode": None if ok else "verify_failed",
                   "prUrl": "https://github.com/o/r/pull/9" if ok else None}}, f)
    sys.exit(0 if ok else 1)
""")

# Stands in for herdr: logs each command; FAKE_HERDR_FAIL makes every command fail.
FAKE_HERDR = textwrap.dedent("""\
    #!{python}
    import json, os, sys
    with open(os.environ["FAKE_LOG"], "a") as f:
        f.write(json.dumps(sys.argv[1:]) + "\\n")
    if os.environ.get("FAKE_HERDR_FAIL"):
        print(json.dumps({{"error": {{"code": "server_unavailable", "message": "no herdr server"}}}}))
        sys.exit(1)
    print(json.dumps({{"result": {{}}}}))
""")


def script(directory, name, body):
    path = os.path.join(directory, name)
    with open(path, "w") as f:
        f.write(body.format(python=sys.executable))
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
    return path


class RunWrapperTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.repo = os.path.join(self.dir.name, "repo")
        os.makedirs(self.repo)
        self.log = os.path.join(self.dir.name, "herdr.log")
        self.saved = (hi.HERDR, hi.CODEX_CAGE, hi.RUN_POLL_SECONDS, os.getcwd(), dict(os.environ))
        hi.HERDR = script(self.dir.name, "herdr", FAKE_HERDR)
        hi.CODEX_CAGE = script(self.dir.name, "codex-cage", FAKE_CODEX_CAGE)
        hi.RUN_POLL_SECONDS = 0.05
        os.environ.update(HERDR_ENV="1", HERDR_PANE_ID="wX:p4", FAKE_LOG=self.log)
        os.environ.pop("FAKE_HERDR_FAIL", None)
        os.chdir(self.repo)

    def tearDown(self):
        hi.HERDR, hi.CODEX_CAGE, hi.RUN_POLL_SECONDS, cwd, env = self.saved
        os.chdir(cwd)
        os.environ.clear()
        os.environ.update(env)
        self.dir.cleanup()

    def run_wrapper(self, outcome):
        os.environ["FAKE_OUTCOME"] = outcome
        stderr = sys.stderr
        sys.stderr = open(os.devnull, "w")
        try:
            with open(os.devnull, "w") as quiet:
                stdout, sys.stdout = sys.stdout, quiet
                try:
                    code = hi.cmd_run([URL])
                finally:
                    sys.stdout = stdout
        finally:
            sys.stderr.close()
            sys.stderr = stderr
        return code

    def herdr_commands(self):
        commands = []
        with open(self.log) as f:
            for line in f:
                args = json.loads(line)
                if "--seq" in args:  # check that it increases, then hide it
                    i = args.index("--seq") + 1
                    seq = int(args[i])
                    self.assertGreater(seq, getattr(self, "_last_seq", 0))
                    self._last_seq = seq
                    args[i] = "<seq>"
                commands.append(args)
        return commands

    def state(self):
        with open(os.path.join(self.repo, ".codex-cage", "runs", "delegate-7.json")) as f:
            return json.load(f)

    def test_a_successful_run_reports_each_stage_then_the_pr(self):
        self.assertEqual(self.run_wrapper("succeeded"), 0)

        agent = ["pane", "report-agent", "wX:p4", "--source", "herdr-issues", "--agent", "codex-cage"]
        meta = lambda title, display: ["pane", "report-metadata", "wX:p4", "--source", "herdr-issues",
                                       "--agent", "codex-cage", "--title", title,
                                       "--display-agent", display, "--seq", "<seq>"]
        state = self.state()
        self.assertEqual(self.herdr_commands(), [
            agent + ["--state", "working", "--message", "run " + state["runId"], "--seq", "<seq>"],
            meta("#7", "starting"),
            meta("#7 Add multiply()", "starting"),
            meta("#7 Add multiply()", "prepare"),
            meta("#7 Add multiply()", "implement"),
            meta("#7 Add multiply()", "implement 2/3"),
            meta("#7 Add multiply()", "implement try 2"),
            meta("#7 Add multiply()", "PR opened"),
            agent + ["--state", "idle", "--message", "PR opened. https://github.com/o/r/pull/9", "--seq", "<seq>"],
            ["notification", "show", "codex-cage #7: PR opened", "--body", "https://github.com/o/r/pull/9",
             "--sound", "done"],
        ])
        self.assertEqual(state, {"runId": state["runId"], "status": "succeeded", "failureCode": None,
                                 "prUrl": "https://github.com/o/r/pull/9", "issueUrl": URL, "pane": "wX:p4"})
        self.assertRegex(state["runId"], r"^run-\d{14}-[0-9a-f]{6}$")

        with open(self.log + ".cage") as f:
            cage = json.load(f)
        self.assertEqual(cage["execution"], "docker")
        self.assertEqual(cage["args"][:4], ["run", URL, "--run-id", state["runId"]])
        self.assertFalse(os.path.exists(cage["args"][-1]), "the temporary result file is removed")

    def test_a_failed_run_is_blocked_and_asks_for_attention(self):
        self.assertEqual(self.run_wrapper("failed"), 1)

        commands = self.herdr_commands()
        run_id = self.state()["runId"]
        self.assertEqual(commands[-3][-3], "verify_failed")  # --display-agent
        self.assertEqual(commands[-2][-4:-2], ["--message", "failed: verify_failed. Inspect it with: "
                                               "codex-cage runs show " + run_id])
        self.assertEqual(commands[-2][8], "blocked")
        self.assertEqual(commands[-1][-1], "request")
        self.assertEqual(self.state()["failureCode"], "verify_failed")

    def test_a_run_that_exits_without_a_result_is_crashed(self):
        self.assertEqual(self.run_wrapper("crash"), 3)

        self.assertEqual(self.state()["status"], "crashed")
        self.assertEqual(self.state()["exitCode"], 3)
        self.assertEqual(self.herdr_commands()[-3][-3], "crashed")

    def test_the_run_continues_when_herdr_fails(self):
        os.environ["FAKE_HERDR_FAIL"] = "1"

        self.assertEqual(self.run_wrapper("succeeded"), 0)

        self.assertEqual(len(self.herdr_commands()), 1, "the first failure turns reporting off")
        self.assertEqual(self.state()["status"], "succeeded")

    def test_outside_herdr_nothing_is_reported(self):
        del os.environ["HERDR_ENV"]

        self.assertEqual(self.run_wrapper("succeeded"), 0)

        self.assertFalse(os.path.exists(self.log))
        self.assertEqual(self.state()["pane"], None)


class RunStatesTest(unittest.TestCase):
    def test_states_come_from_delegate_files_and_dead_runs_are_stopped(self):
        with tempfile.TemporaryDirectory() as root:
            runs = os.path.join(root, ".codex-cage", "runs")
            hi.write_json(os.path.join(runs, "delegate-1.json"), {"status": "running", "stage": "verify", "pid": os.getpid()})
            hi.write_json(os.path.join(runs, "delegate-2.json"), {"status": "running", "pid": 2 ** 22 + 12345})
            hi.write_json(os.path.join(runs, "delegate-3.json"), {"status": "failed", "failureCode": "review_rejected"})
            hi.write_json(os.path.join(runs, "other.json"), {"status": "failed"})

            states = hi.run_states(root)

        self.assertEqual(sorted(states), [1, 2, 3])
        self.assertEqual(hi.run_label(states[1]), ("◐", "verify", 4))
        self.assertEqual(hi.run_label(states[2]), ("■", "stopped", 0))
        self.assertEqual(hi.run_label(states[3]), ("✗", "review_rejected", 3))
        self.assertEqual(hi.run_label({"status": "succeeded"}), ("✓", "PR opened", 1))

    def test_no_runs_directory_means_no_states(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(hi.run_states(root), {})


class EventTailTest(unittest.TestCase):
    def test_it_returns_only_complete_new_lines(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "events.ndjson")
            tail = hi.EventTail(path)
            self.assertEqual(tail.read(), [], "the file does not exist yet")
            with open(path, "w") as f:
                f.write('{"type": "a"}\n{"type": ')
            self.assertEqual(tail.read(), [{"type": "a"}])
            with open(path, "a") as f:
                f.write('"b"}\nnot json\n')
            self.assertEqual(tail.read(), [{"type": "b"}])
            self.assertEqual(tail.read(), [])


class StartCommandTest(unittest.TestCase):
    def test_the_pane_runs_the_wrapper_then_exits(self):
        command = hi.start_run_command("https://github.com/o/r/issues/7?x=1&y=2")

        self.assertTrue(command.endswith(" run 'https://github.com/o/r/issues/7?x=1&y=2'; exit"))
        self.assertTrue(command.startswith(os.path.realpath(os.path.join(ROOT, "bin", "herdr-issues"))))


if __name__ == "__main__":
    unittest.main()
