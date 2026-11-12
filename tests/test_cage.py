"""Tests for running issues with agent-cage: python3 -m unittest discover tests"""
import importlib.machinery
import importlib.util
import json
import os
import re
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

# Stands in for agent-cage. `runs list --json` prints FAKE_RUNS. `run` writes the
# run's events and result where the real one does, then exits; FAKE_OUTCOME picks
# how the run ends.
FAKE_AGENT_CAGE = textwrap.dedent("""\
    #!{python}
    import json, os, sys
    args = sys.argv[1:]
    if args == ["runs", "list", "--json"]:
        print(os.environ.get("FAKE_RUNS", "[]"))
        sys.exit(int(os.environ.get("FAKE_RUNS_EXIT", "0")))
    run_id = args[args.index("--run-id") + 1]
    result = args[args.index("--result-json") + 1]
    with open(os.environ["FAKE_LOG"] + ".cage", "w") as f:
        json.dump({{"args": args, "execution": os.environ.get("AGENT_CAGE_EXECUTION")}}, f)
    os.makedirs(".agent-cage/runs/" + run_id, exist_ok=True)
    events = [
        {{"type": "run.started", "payload": {{"issueKey": "#7", "issueTitle": "Add multiply()"}}}},
        {{"type": "stage.started", "stage": "prepare", "stageAttempt": 1, "payload": {{}}}},
        {{"type": "stage.started", "stage": "implement", "stageAttempt": 1, "payload": {{}}}},
        {{"type": "implementation.iteration_started", "stage": "implement", "stageAttempt": 1,
          "payload": {{"iteration": 2, "maxIterations": 3}}}},
        {{"type": "command.started", "payload": {{"command": "npm test"}}}},
        {{"type": "stage.started", "stage": "implement", "stageAttempt": 2, "payload": {{}}}},
    ]
    with open(".agent-cage/runs/%s/events.ndjson" % run_id, "w") as f:
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
# `tab create` makes the cage tab's pane wX:p9. `pane wait-output` stands for the
# run in that pane ending: it writes FAKE_PANE_RESULT, if set, to the result file
# the pane was told to write.
FAKE_HERDR = textwrap.dedent("""\
    #!{python}
    import json, os, sys
    args = sys.argv[1:]
    with open(os.environ["FAKE_LOG"], "a") as f:
        f.write(json.dumps(args) + "\\n")
    if os.environ.get("FAKE_HERDR_FAIL"):
        print(json.dumps({{"error": {{"code": "server_unavailable", "message": "no herdr server"}}}}))
        sys.exit(1)
    if args[:2] == ["tab", "create"]:
        print(json.dumps({{"result": {{"tab": {{"tab_id": "wX:t9"}}, "root_pane": {{"pane_id": "wX:p9"}}}}}}))
    elif args[:2] == ["pane", "wait-output"] and os.environ.get("FAKE_PANE_RESULT"):
        with open(os.environ["FAKE_LOG"]) as f:
            typed = [json.loads(line) for line in f if line.startswith('["pane", "run"')][-1][3]
        path = typed.split("--result-json ")[1].split(";")[0].strip("'")
        with open(path, "w") as f:
            f.write(os.environ["FAKE_PANE_RESULT"])
        print(json.dumps({{"result": {{}}}}))
    else:
        print(json.dumps({{"result": {{}}}}))
""")


def script(directory, name, body):
    path = os.path.join(directory, name)
    with open(path, "w") as f:
        f.write(body.format(python=sys.executable))
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
    return path


class FakesTestCase(unittest.TestCase):
    """Runs each test in a fresh repo directory, with fake agent-cage and herdr executables."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.repo = os.path.join(self.dir.name, "repo")
        os.makedirs(self.repo)
        self.log = os.path.join(self.dir.name, "herdr.log")
        self.saved = (hi.HERDR, hi.AGENT_CAGE, hi.RUN_POLL_SECONDS, os.getcwd(), dict(os.environ))
        hi.HERDR = script(self.dir.name, "herdr", FAKE_HERDR)
        hi.AGENT_CAGE = script(self.dir.name, "agent-cage", FAKE_AGENT_CAGE)
        hi.RUN_POLL_SECONDS = 0.05
        os.environ.update(HERDR_ENV="1", HERDR_PANE_ID="wX:p4", FAKE_LOG=self.log)
        for name in ("FAKE_HERDR_FAIL", "FAKE_RUNS", "FAKE_RUNS_EXIT"):
            os.environ.pop(name, None)
        os.chdir(self.repo)

    def cage_call(self):
        """The arguments and execution mode the fake agent-cage was run with."""
        with open(self.log + ".cage") as f:
            return json.load(f)

    def tearDown(self):
        hi.HERDR, hi.AGENT_CAGE, hi.RUN_POLL_SECONDS, cwd, env = self.saved
        os.chdir(cwd)
        os.environ.clear()
        os.environ.update(env)
        self.dir.cleanup()


class RunWrapperTest(FakesTestCase):
    def run_wrapper(self, outcome, *args):
        os.environ["FAKE_OUTCOME"] = outcome
        stderr = sys.stderr
        sys.stderr = open(os.devnull, "w")
        try:
            with open(os.devnull, "w") as quiet:
                stdout, sys.stdout = sys.stdout, quiet
                try:
                    code = hi.cmd_run([URL, *args])
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

    def test_a_successful_run_reports_each_stage_then_the_pr(self):
        self.assertEqual(self.run_wrapper("succeeded"), 0)

        cage = self.cage_call()
        run_id = cage["args"][3]
        agent = ["pane", "report-agent", "wX:p4", "--source", "herdr-issues", "--agent", "agent-cage"]
        meta = lambda title, display: ["pane", "report-metadata", "wX:p4", "--source", "herdr-issues",
                                       "--agent", "agent-cage", "--title", title,
                                       "--display-agent", display, "--seq", "<seq>"]
        self.assertEqual(self.herdr_commands(), [
            agent + ["--state", "working", "--message", "run " + run_id, "--seq", "<seq>"],
            meta("#7", "starting"),
            meta("#7 Add multiply()", "starting"),
            meta("#7 Add multiply()", "prepare"),
            meta("#7 Add multiply()", "implement"),
            meta("#7 Add multiply()", "implement 2/3"),
            meta("#7 Add multiply()", "implement try 2"),
            meta("#7 Add multiply()", "PR opened"),
            agent + ["--state", "idle", "--message", "PR opened. https://github.com/o/r/pull/9", "--seq", "<seq>"],
            ["notification", "show", "agent-cage #7: PR opened", "--body", "https://github.com/o/r/pull/9",
             "--sound", "done"],
        ])

        self.assertRegex(run_id, r"^run-\d{14}-[0-9a-f]{6}$")
        self.assertEqual(cage["execution"], "docker")
        self.assertEqual(cage["args"][:4], ["run", URL, "--run-id", run_id])
        self.assertFalse(os.path.exists(cage["args"][-1]), "the temporary result file is removed")
        self.assertEqual(os.listdir(os.path.join(self.repo, ".agent-cage", "runs")), [run_id],
                         "only agent-cage writes to the repo's run directory")

    def test_a_failed_run_is_blocked_and_asks_for_attention(self):
        self.assertEqual(self.run_wrapper("failed"), 1)

        commands = self.herdr_commands()
        run_id = self.cage_call()["args"][3]
        self.assertEqual(commands[-3][-3], "verify_failed")  # --display-agent
        self.assertEqual(commands[-2][-4:-2], ["--message", "failed: verify_failed. Inspect it with: "
                                               "agent-cage runs show " + run_id])
        self.assertEqual(commands[-2][8], "blocked")
        self.assertEqual(commands[-1][-1], "request")

    def test_a_run_that_exits_without_a_result_is_crashed(self):
        self.assertEqual(self.run_wrapper("crash"), 3)

        commands = self.herdr_commands()
        self.assertEqual(commands[-3][-3], "crashed")
        self.assertEqual(commands[-2][-4:-2], ["--message", "crashed. agent-cage exited with code 3; "
                                               "see the cage pane"])
        self.assertFalse(os.path.exists(self.cage_call()["args"][-1]), "the temporary result file is removed")

    def test_the_run_continues_when_herdr_fails(self):
        os.environ["FAKE_HERDR_FAIL"] = "1"

        self.assertEqual(self.run_wrapper("succeeded"), 0)

        self.assertEqual(len(self.herdr_commands()), 1, "the first failure turns reporting off")

    def test_outside_herdr_nothing_is_reported(self):
        del os.environ["HERDR_ENV"]

        self.assertEqual(self.run_wrapper("succeeded"), 0)

        self.assertFalse(os.path.exists(self.log))


def cage_run(run_id, issue_url, status, **fields):
    """An entry of `agent-cage runs list --json`."""
    finished = status in ("succeeded", "failed", "guard_failed", "aborted")
    return dict({"id": run_id, "issueUrl": issue_url, "status": status, "failureCode": None, "prUrl": None,
                 "startedAt": "2026-11-12T01:00:00.000Z",
                 "finishedAt": "2026-11-12T01:05:00.000Z" if finished else None,
                 "pid": 4242, "interrupted": False}, **fields)


class ResultJsonTest(RunWrapperTest):
    def test_result_json_gets_agent_cages_result(self):
        path = os.path.join(self.repo, "planner-7.json")

        self.run_wrapper("succeeded", "--result-json", "planner-7.json")

        with open(path) as f:
            result = json.load(f)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["prUrl"], "https://github.com/o/r/pull/9")
        self.assertEqual(os.listdir(self.repo), [".agent-cage", "planner-7.json"], "no temp files are left")

    def test_a_crashed_run_leaves_no_result_json(self):
        self.run_wrapper("crash", "--result-json", "planner-7.json")

        self.assertFalse(os.path.exists(os.path.join(self.repo, "planner-7.json")))


class LaunchTest(FakesTestCase):
    def setUp(self):
        super().setUp()
        os.environ["HERDR_WORKSPACE_ID"] = "wX"

    def launch(self, *args):
        with open(os.devnull, "w") as quiet:
            stdout, stderr, sys.stdout, sys.stderr = sys.stdout, sys.stderr, quiet, quiet
            try:
                return hi.cmd_launch(list(args))
            finally:
                sys.stdout, sys.stderr = stdout, stderr

    def herdr_commands(self):
        with open(self.log) as f:
            return [json.loads(line) for line in f]

    def test_it_runs_the_issue_in_the_cage_tab_and_waits_for_the_result(self):
        os.environ["FAKE_PANE_RESULT"] = json.dumps({"runId": "run-1", "status": "succeeded",
                                                     "prUrl": "https://github.com/o/r/pull/9"})
        path = os.path.join(self.repo, ".agent-cage", "runs", "planner-7.json")
        os.makedirs(os.path.dirname(path))
        with open(path, "w") as f:
            f.write('{"status": "failed"}')  # an earlier run's

        code = self.launch(URL, "--result-json", ".agent-cage/runs/planner-7.json")

        self.assertEqual(code, 0)
        commands = self.herdr_commands()
        self.assertIn(["tab", "create", "--workspace", "wX", "--label", "cage", "--cwd", os.getcwd(), "--no-focus"],
                      commands)
        run = next(c for c in commands if c[:2] == ["pane", "run"])
        self.assertEqual(run[2], "wX:p9")
        self.assertEqual(run[3], hi.start_run_command(URL, os.path.realpath(path)))
        wait = next(c for c in commands if c[:2] == ["pane", "wait-output"])
        self.assertEqual(wait[2:5], ["wX:p9", "--regex", hi.FINISHED_PATTERN])
        with open(path) as f:
            self.assertEqual(json.load(f)["status"], "succeeded")

    def test_a_failed_run_exits_1_with_its_result_in_place(self):
        os.environ["FAKE_PANE_RESULT"] = json.dumps({"runId": "run-1", "status": "failed",
                                                     "failureCode": "verify_failed"})

        self.assertEqual(self.launch(URL, "--result-json", "planner-7.json"), 1)
        with open(os.path.join(self.repo, "planner-7.json")) as f:
            self.assertEqual(json.load(f)["failureCode"], "verify_failed")

    def test_a_run_that_ends_without_a_result_exits_1(self):
        self.assertEqual(self.launch(URL, "--result-json", "planner-7.json"), 1)
        self.assertFalse(os.path.exists(os.path.join(self.repo, "planner-7.json")))

    def test_outside_herdr_it_runs_here(self):
        os.environ.pop("HERDR_ENV")
        os.environ["FAKE_OUTCOME"] = "succeeded"

        self.assertEqual(self.launch(URL, "--result-json", "planner-7.json"), 0)
        self.assertFalse(os.path.exists(self.log), "herdr is not called")
        self.assertEqual(self.cage_call()["execution"], "docker")
        with open(os.path.join(self.repo, "planner-7.json")) as f:
            self.assertEqual(json.load(f)["status"], "succeeded")

    def test_it_needs_a_result_file(self):
        self.assertEqual(self.launch(URL), 2)


class RunStatesTest(FakesTestCase):
    def test_each_issue_gets_the_latest_run_for_this_repo(self):
        os.environ["FAKE_RUNS"] = json.dumps([
            cage_run("run-4", "https://github.com/o/r/issues/7", "implementing"),
            cage_run("run-3", "https://github.com/o/r/issues/7", "failed", failureCode="verify_failed"),
            cage_run("run-2", "https://github.com/O/R/issues/8#top", "succeeded"),
            cage_run("run-1", "https://github.com/other/r/issues/9", "succeeded"),
            cage_run("run-0", "https://linear.app/team/issue/ENG-1/title", "succeeded"),
            "not a run",
        ])

        states = hi.run_states(self.repo, "o/r")

        self.assertEqual({number: run["id"] for number, run in states.items()}, {7: "run-4", 8: "run-2"})
        self.assertEqual(sorted(hi.run_states(self.repo)), [7, 8, 9], "without a repo, every GitHub issue")

    def test_without_a_working_runs_list_there_are_no_runs(self):
        os.environ["FAKE_RUNS_EXIT"] = "1"  # e.g. a agent-cage too old to have --json
        self.assertEqual(hi.run_states(self.repo, "o/r"), {})

        os.environ.update(FAKE_RUNS="not json", FAKE_RUNS_EXIT="0")
        self.assertEqual(hi.run_states(self.repo, "o/r"), {})

        hi.AGENT_CAGE = os.path.join(self.dir.name, "missing-agent-cage")
        self.assertEqual(hi.run_states(self.repo, "o/r"), {})

    def test_labels(self):
        url = "https://github.com/o/r/issues/7"
        cases = [
            (cage_run("r", url, "implementing"), ("◐", "implementing", 4), True),
            (cage_run("r", url, "creating_pr"), ("◐", "creating pr", 4), True),
            ({"status": "starting"}, ("◐", "starting", 4), True),
            (cage_run("r", url, "cloning", interrupted=True), ("■", "interrupted", 0), False),
            (cage_run("r", url, "succeeded"), ("✓", "PR opened", 1), False),
            (cage_run("r", url, "failed", failureCode="review_blocking"), ("✗", "review_blocking", 3), False),
            (cage_run("r", url, "guard_failed", failureCode="secret_guard_failed"),
             ("✗", "secret_guard_failed", 3), False),
            (cage_run("r", url, "aborted"), ("■", "aborted", 0), False),
            ({"status": "crashed", "exitCode": 3}, ("✗", "crashed", 3), False),
        ]
        for run, label, active in cases:
            self.assertEqual(hi.run_label(run), label, run)
            self.assertEqual(hi.run_active(run), active, run)
        self.assertFalse(hi.run_active(None))


class PendingRunTest(unittest.TestCase):
    def test_c_shows_starting_until_agent_cage_records_the_run(self):
        panel = hi.Panel("/nonexistent")
        pressed = 1000.0  # 1970-01-01T00:16:40Z
        earlier = {"status": "failed", "startedAt": "1970-01-01T00:16:39.000Z", "finishedAt": "x"}
        recorded = {"status": "cloning", "startedAt": "1970-01-01T00:16:41.000Z", "finishedAt": None}

        panel.pending = {7: pressed}
        self.assertEqual(panel.with_pending({7: earlier}, pressed + 5), {7: {"status": "starting"}},
                         "the issue's previous run does not count")
        self.assertEqual(panel.pending, {7: pressed})

        self.assertEqual(panel.with_pending({7: recorded, 8: earlier}, pressed + 5), {7: recorded, 8: earlier})
        self.assertEqual(panel.pending, {})

        panel.pending = {7: pressed}
        self.assertEqual(panel.with_pending({}, pressed + hi.PENDING_SECONDS + 1), {},
                         "a run agent-cage never records stops showing as starting")
        self.assertEqual(panel.pending, {})


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

    def test_launch_passes_the_result_file_on(self):
        command = hi.start_run_command(URL, "/repo/.agent-cage/runs/planner 7.json")

        self.assertTrue(command.endswith(" run %s --result-json '/repo/.agent-cage/runs/planner 7.json'; exit" % URL))

    def test_launch_waits_for_the_line_the_run_ends_with_and_not_the_typed_command(self):
        finished = hi.FINISHED_LINE % (7, "✓", "PR opened", "https://github.com/o/r/pull/9")

        self.assertRegex(finished, hi.FINISHED_PATTERN)
        self.assertNotRegex(hi.start_run_command(URL, "/repo/r.json"), hi.FINISHED_PATTERN)
        self.assertIsNone(re.search(hi.FINISHED_PATTERN, "herdr-issues: herdr status updates are off for this run"))


if __name__ == "__main__":
    unittest.main()
