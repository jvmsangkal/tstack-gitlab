"""Offline tests for skills/babysit-pr/scripts/pr-wait.

A fake glab (tests/fake_glab/glab) sits first on PATH and answers from
fixtures, so these tests need no network, no GitLab account, and no token.
"""

import copy
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
SCRIPT = TESTS.parent / "skills" / "babysit-pr" / "scripts" / "pr-wait"
FAKE_GLAB_DIR = TESTS / "fake_glab"
FIXTURES = TESTS / "fixtures"

HOST = "gitlab.example.com"
PROJECT = "group/sub/project"
P = "projects/group%2Fsub%2Fproject"
MR = f"{P}/merge_requests/7"
URL = f"https://{HOST}/{PROJECT}/-/merge_requests/7"
SHA = "abc1234def567890abc1234def567890abc12345"
OLD_BASE = "b01b01b01b01b01b01b01b01b01b01b01b01b01b"
NEW_BASE = "c02c02c02c02c02c02c02c02c02c02c02c02c02c"
TOKEN = "glpat-SENTINEL-must-never-leak"


def load_pr_wait():
    # pr-wait has no .py suffix, so load it by path. Keep __pycache__ out of skills/.
    sys.dont_write_bytecode = True
    loader = importlib.machinery.SourceFileLoader("pr_wait", str(SCRIPT))
    spec = importlib.util.spec_from_loader("pr_wait", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules["pr_wait"] = module
    loader.exec_module(module)
    return module


pr_wait = load_pr_wait()


def fixture(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())


def ok(value):
    return {"stdout": value}


def http_error(status, text, exit_code=1):
    return {"stdout": {"message": f"{status} {text}"}, "stderr": f"glab: {status} {text} (HTTP {status})\n", "exit": exit_code}


def page(path):
    return f"api {path}?per_page=100&page=1"


def base_responses(mr=None, graphql=None, jobs=None, statuses=None):
    mr = mr or fixture("merge_request")
    return {
        f"api {P}": ok(fixture("project")),
        "api projects/:fullpath": ok(fixture("project")),
        f"api {MR}": ok(mr),
        f"api {MR}?include_diverged_commits_count=true": ok(mr),
        "api graphql": ok(graphql or fixture("graphql")),
        page("projects/42/pipelines/1001/jobs"): ok(fixture("jobs") if jobs is None else jobs),
        page("projects/42/pipelines/1001/bridges"): ok(fixture("bridges")),
        page(f"projects/42/repository/commits/{SHA}/statuses"): ok(fixture("statuses") if statuses is None else statuses),
        f"api {MR}/status_checks": http_error(404, "Not found"),
        f"api {P}/repository/branches/main": ok(fixture("branch")),
        page(f"{MR}/diffs"): ok(fixture("diffs")),
        f"api {P}/repository/compare?from={OLD_BASE}&to={NEW_BASE}": ok(fixture("compare")),
    }


def graphql_with(mutate):
    data = fixture("graphql")
    mutate(data["data"]["project"]["mergeRequest"])
    return data


def discussion(data, discussion_id):
    return next(d for d in data["discussions"]["nodes"] if d["id"].endswith(discussion_id))


def resolve_thread(mr_node):
    discussion(mr_node, "d4")["resolved"] = True


class StopPolling(Exception):
    pass


class PrWaitTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.log_dir = self.root / "log"
        self.log_dir.mkdir()
        self.state_dir = self.root / "state"
        self.state_dir.mkdir()
        self.scenario_file = self.root / "scenario.json"
        env = {
            "PATH": f"{FAKE_GLAB_DIR}{os.pathsep}{os.environ.get('PATH', '')}",
            "FAKE_GLAB_SCENARIO": str(self.scenario_file),
            "FAKE_GLAB_LOG": str(self.log_dir),
            "GITLAB_TOKEN": TOKEN,
        }
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("GITLAB_HOST", None)
        state_patcher = mock.patch.object(pr_wait, "STATE_DIR", self.state_dir)
        state_patcher.start()
        self.addCleanup(state_patcher.stop)
        self.scenario(base_responses())

    def scenario(self, responses, hosts=(HOST, "gitlab.com")):
        self.scenario_file.write_text(json.dumps({"responses": responses, "hosts": list(hosts)}))

    def calls(self):
        path = self.log_dir / "calls.jsonl"
        if not path.exists():
            return []
        return [json.loads(line)["argv"] for line in path.read_text().splitlines()]

    def run_quietly(self, fn):
        out, err = io.StringIO(), io.StringIO()
        code = None
        with redirect_stdout(out), redirect_stderr(err):
            try:
                result = fn()
            except SystemExit as exit_:
                code, result = exit_.code, None
        return code, out.getvalue(), err.getvalue(), result

    def watch(self, raw=URL, repo=None, until="ready", polls=3):
        """Run pr-wait in-process. Returns (exit code or None if it kept polling, stdout, stderr)."""
        sleeps = []

        def sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) >= polls:
                raise StopPolling

        def go():
            target = pr_wait.parse_target(raw, repo)
            pr_wait.Watcher(target, until, 5).run()

        with mock.patch.object(pr_wait.time, "sleep", sleep):
            try:
                code, out, err, _ = self.run_quietly(go)
            except StopPolling:
                code, out, err = None, "", ""
        return code, out, err

    def parse(self, raw, repo=None):
        code, out, _, target = self.run_quietly(lambda: pr_wait.parse_target(raw, repo))
        return code, out, target


class TargetParsingTest(PrWaitTestCase):
    def test_self_hosted_nested_group_url_sets_hostname(self):
        code, out, target = self.parse(URL)
        self.assertIsNone(code, out)
        self.assertEqual((target.host, target.project, target.iid), (HOST, PROJECT, 7))
        self.assertEqual(target.host_args, ["--hostname", HOST])
        self.assertIn(["api", "--hostname", HOST, MR], self.calls())

    def test_gitlab_com_url(self):
        code, out, target = self.parse(f"https://gitlab.com/{PROJECT}/-/merge_requests/7/diffs?view=inline")
        self.assertIsNone(code, out)
        self.assertEqual(target.host_args, ["--hostname", "gitlab.com"])
        self.assertEqual(target.project, PROJECT)

    def test_bang_iid_with_repo_uses_glab_default_host(self):
        code, out, target = self.parse("!7", repo=PROJECT)
        self.assertIsNone(code, out)
        self.assertEqual(target.host_args, [])
        self.assertEqual(target.host, HOST)  # from the MR's web_url, for state keys
        self.assertNotIn("auth", [c[0] for c in self.calls()])

    def test_cross_project_reference(self):
        code, out, target = self.parse(f"{PROJECT}!7")
        self.assertIsNone(code, out)
        self.assertEqual((target.project, target.iid), (PROJECT, 7))

    def test_repo_given_as_project_url(self):
        code, out, target = self.parse("7", repo=f"https://{HOST}/{PROJECT}.git")
        self.assertIsNone(code, out)
        self.assertEqual((target.host, target.project), (HOST, PROJECT))
        self.assertEqual(target.host_args, ["--hostname", HOST])

    def test_current_checkout_uses_fullpath(self):
        code, out, target = self.parse("#7")
        self.assertIsNone(code, out)
        self.assertEqual(target.project, PROJECT)
        self.assertIn(["api", "projects/:fullpath"], self.calls())

    def test_url_names_the_project_without_fullpath(self):
        self.parse(URL)
        self.assertFalse(any(":fullpath" in arg for call in self.calls() for arg in call))

    def test_gitlab_host_routes_without_hostname_flag(self):
        os.environ["GITLAB_HOST"] = f"https://{HOST}/"
        code, out, target = self.parse("!7", repo=PROJECT)
        self.assertIsNone(code, out)
        self.assertEqual((target.host, target.host_args), (HOST, []))
        self.assertFalse(any("--hostname" in call for call in self.calls()))

    def test_url_with_port_on_gitlab_host(self):
        os.environ["GITLAB_HOST"] = "https://gitlab.example.com:8443"
        code, out, target = self.parse(f"https://{HOST}:8443/{PROJECT}/-/merge_requests/7")
        self.assertIsNone(code, out)
        self.assertEqual((target.host, target.host_args), (f"{HOST}:8443", []))
        self.assertFalse(any("--hostname" in call for call in self.calls()))

    def test_url_with_port_needs_gitlab_host(self):
        code, out, _ = self.parse(f"https://{HOST}:8443/{PROJECT}/-/merge_requests/7")
        self.assertEqual(code, 2)
        self.assertIn(f"GITLAB_HOST=https://{HOST}:8443", out)
        self.assertEqual(self.calls(), [])

    def test_host_without_glab_login_fails_before_any_api_call(self):
        code, out, _ = self.parse(f"https://gitlab.other.org/{PROJECT}/-/merge_requests/7")
        self.assertEqual(code, 2)
        self.assertIn("glab auth login --hostname gitlab.other.org", out)
        self.assertIn("GITLAB_HOST=https://gitlab.other.org", out)
        self.assertEqual([c[:2] for c in self.calls()], [["auth", "status"]])

    def test_bad_input(self):
        for raw in ("", "abc", "0", "group/sub/project7x", f"https://github.com/{PROJECT}/pull/7"):
            with self.subTest(raw=raw):
                code, _, _ = self.parse(raw)
                self.assertEqual(code, 2)

    def test_unknown_mr(self):
        responses = base_responses()
        responses[f"api {MR}"] = http_error(404, "Not found")
        self.scenario(responses)
        code, out, _ = self.parse(URL)
        self.assertEqual(code, 2)
        self.assertIn(f"cannot read {PROJECT}!7", out)

    def test_lock_blocks_a_second_watcher(self):
        _, _, target = self.parse(URL)
        handle = pr_wait.lock(target)
        self.addCleanup(handle.close)
        self.assertTrue((self.state_dir / f"{HOST}__group__sub__project__7.lock").exists())
        code, out, _, _ = self.run_quietly(lambda: pr_wait.lock(target))
        self.assertEqual(code, 2)
        self.assertIn("already watches", out)


class GlabTest(PrWaitTestCase):
    def test_http_error_with_exit_zero_is_an_error(self):
        # Older glab exits 0 after an HTTP error and prints an update notice.
        error = http_error(404, "Project Not Found", exit_code=0)
        error["stderr"] += "A new version of glab has been released: v1.36.0 -> v1.126.0\nhttps://gitlab.com/gitlab-org/cli/-/releases/v1.126.0\n"
        self.scenario({"api projects/x%2Fy": error})
        with self.assertRaises(pr_wait.GlabError) as caught:
            pr_wait.api([], "projects/x%2Fy")
        self.assertEqual(caught.exception.status, 404)
        self.assertFalse(caught.exception.transient)
        self.assertEqual(str(caught.exception), "glab: 404 Project Not Found (HTTP 404)")

    def test_429_is_retried(self):
        self.scenario({"api projects/x%2Fy": [http_error(429, "Too Many Requests"), ok({"id": 1})]})
        with mock.patch.object(pr_wait.time, "sleep") as sleep, redirect_stderr(io.StringIO()):
            self.assertEqual(pr_wait.api([], "projects/x%2Fy"), {"id": 1})
        sleep.assert_called_once_with(2)

    def test_5xx_gives_up_as_transient(self):
        self.scenario({"api projects/x%2Fy": http_error(502, "Bad Gateway")})
        with mock.patch.object(pr_wait.time, "sleep"), redirect_stderr(io.StringIO()):
            with self.assertRaises(pr_wait.GlabError) as caught:
                pr_wait.api([], "projects/x%2Fy")
        self.assertTrue(caught.exception.transient)
        self.assertEqual(len(self.calls()), 5)

    def test_pages_until_a_short_page(self):
        full = [{"id": n} for n in range(100)]
        self.scenario({
            "api things?per_page=100&page=1": ok(full),
            "api things?per_page=100&page=2": ok([{"id": 100}]),
        })
        self.assertEqual(len(pr_wait.pages([], "things")), 101)


class BucketTest(unittest.TestCase):
    def test_job_states_map_to_buckets(self):
        cases = {
            ("success", False): ("pass", True),
            ("failed", False): ("fail", True),
            ("failed", True): ("pass", False),
            ("canceled", False): ("cancel", True),
            ("skipped", False): ("skipping", True),
            ("manual", False): ("skipping", False),
            ("running", False): ("pending", True),
            ("waiting_for_resource", False): ("pending", True),
            ("created", True): ("pending", False),
        }
        for (status, allow_failure), expected in cases.items():
            with self.subTest(status=status, allow_failure=allow_failure):
                row = pr_wait.check("job", status, None, None, allow_failure)
                self.assertEqual((row["bucket"], row["gates"]), expected)


class WatchTest(PrWaitTestCase):
    def test_green_gates_on_required_jobs_only(self):
        code, out, err = self.watch(until="green")
        self.assertEqual(code, 0, out + err)
        line = out.strip().splitlines()[-1]
        self.assertTrue(line.startswith("!7 green on abc1234: "), line)
        # build, test, downstream, and vercel gate; lint may fail; deploy is manual.
        self.assertIn("required 4/4 green", line)
        self.assertIn("5 pass, 1 skipping", line)
        self.assertIn("0 commits behind main", line)
        self.assertIn("pipeline must succeed: yes", err)

    def test_required_job_failure_exits_1(self):
        jobs = fixture("jobs")
        jobs[1]["status"] = "failed"
        self.scenario(base_responses(jobs=jobs))
        code, out, _ = self.watch(until="green")
        self.assertEqual(code, 1)
        self.assertIn("!7 required check failed: test https://gitlab.example.com/group/sub/project/-/jobs/5002", out)

    def test_failed_external_status_exits_1(self):
        statuses = fixture("statuses")
        statuses[1]["status"] = "failed"
        self.scenario(base_responses(statuses=statuses))
        code, out, _ = self.watch(until="green")
        self.assertEqual(code, 1)
        self.assertIn("required check failed: vercel https://vercel.com/acme/widget/abc1234", out)

    def test_pending_job_keeps_waiting(self):
        jobs = fixture("jobs")
        jobs[1]["status"] = "running"
        self.scenario(base_responses(jobs=jobs))
        code, out, _ = self.watch(until="green", polls=3)
        self.assertIsNone(code, out)

    def test_ready_is_blocked_by_an_unresolved_thread(self):
        code, out, _ = self.watch()
        self.assertEqual(code, 1)
        self.assertIn("!7 blocked by 1 unresolved threads on abc1234: ", out)
        self.assertIn("#note_104", out)

    def test_ready_once_the_thread_is_resolved(self):
        self.scenario(base_responses(graphql=graphql_with(resolve_thread)))
        code, out, _ = self.watch()
        self.assertEqual(code, 0, out)
        self.assertIn("!7 ready on abc1234: ", out)
        self.assertIn("greptile done", out)

    def test_ready_waits_for_greptile_on_the_head(self):
        def stale_summary(mr_node):
            resolve_thread(mr_node)
            discussion(mr_node, "d2")["notes"]["nodes"][0]["body"] = "Greptile Summary\nReviewed 0ld0ld0."

        self.scenario(base_responses(graphql=graphql_with(stale_summary)))
        code, out, _ = self.watch(polls=3)
        self.assertIsNone(code, out)

    def test_new_comment_is_an_event_and_system_notes_are_not(self):
        def more_notes(mr_node):
            mr_node["discussions"]["nodes"] += [
                {"id": "gid://gitlab/Discussion/d5", "resolvable": False, "resolved": False, "notes": {"nodes": [
                    {"id": "gid://gitlab/Note/105", "url": f"{URL}#note_105", "body": "approved this merge request",
                     "system": True, "author": {"username": "frank", "name": "Frank", "bot": False}, "position": None},
                ]}},
                {"id": "gid://gitlab/Discussion/d6", "resolvable": False, "resolved": False, "notes": {"nodes": [
                    {"id": "gid://gitlab/Note/106", "url": f"{URL}#note_106", "body": "Can you add a test?",
                     "system": False, "author": {"username": "frank", "name": "Frank", "bot": False}, "position": None},
                ]}},
                {"id": "gid://gitlab/Discussion/d7", "resolvable": False, "resolved": False, "notes": {"nodes": [
                    {"id": "gid://gitlab/Note/107", "url": f"{URL}#note_107", "body": "Preview deployed",
                     "system": False, "author": {"username": "project_42_bot_vercel", "name": "vercel", "bot": True}, "position": None},
                ]}},
            ]

        responses = base_responses()
        responses["api graphql"] = [ok(fixture("graphql")), ok(graphql_with(more_notes))]
        self.scenario(responses)
        code, out, _ = self.watch(until="any-change")
        self.assertEqual(code, 0, out)
        self.assertEqual(out.strip().splitlines(), [f"!7 comment from frank: Can you add a test? {URL}#note_106"])

    def test_thread_reply_on_a_diff_line(self):
        def reply(mr_node):
            discussion(mr_node, "d4")["notes"]["nodes"].append(
                {"id": "gid://gitlab/DiffNote/108", "url": f"{URL}#note_108", "body": "Good catch, it should.",
                 "system": False, "author": {"username": "gina", "name": "Gina", "bot": False}, "position": None}
            )

        responses = base_responses()
        responses["api graphql"] = [ok(fixture("graphql")), ok(graphql_with(reply))]
        self.scenario(responses)
        code, out, _ = self.watch(until="any-change")
        self.assertEqual(code, 0, out)
        self.assertIn(f"!7 thread reply from gina on src/app.py:12: Good catch, it should. {URL}#note_108", out)

    def test_approval_and_change_request_are_events(self):
        def reviews(mr_node):
            mr_node["approvedBy"]["nodes"] = [{"username": "bob", "bot": False}]
            mr_node["reviewers"]["nodes"][0]["mergeRequestInteraction"]["reviewState"] = "REQUESTED_CHANGES"

        responses = base_responses()
        responses["api graphql"] = [ok(fixture("graphql")), ok(graphql_with(reviews))]
        self.scenario(responses)
        code, out, _ = self.watch(until="any-change")
        self.assertEqual(code, 0, out)
        self.assertIn(f"!7 review from bob (approved) {URL}", out)
        self.assertIn(f"!7 review from carol (changes requested) {URL}", out)

    def test_missing_graphql_fields_are_dropped(self):
        missing = {"errors": [{"message": "Field 'reviewState' doesn't exist on type 'UserMergeRequestInteraction'"}]}
        responses = base_responses(graphql=graphql_with(resolve_thread))
        responses["api graphql"] = [{"stdout": missing, "exit": 1}, responses["api graphql"]]
        self.scenario(responses)
        code, out, err = self.watch()
        self.assertEqual(code, 0, out + err)
        self.assertIn("no reviewers in GraphQL", err)
        queries = [c[c.index("-f") + 1] for c in self.calls() if "graphql" in c]
        self.assertIn("reviewState", queries[0])
        self.assertNotIn("reviewState", queries[1])
        self.assertIn("approvedBy", queries[1])

    def test_conflict_exits_1(self):
        mr = fixture("merge_request")
        mr.update(detailed_merge_status="conflict", has_conflicts=True)
        self.scenario(base_responses(mr=mr))
        code, out, _ = self.watch(until="green")
        self.assertEqual(code, 1)
        self.assertIn("!7 merge state is DIRTY (conflict): the branch conflicts with main, rebase it", out)

    def test_need_rebase_blocks_ready(self):
        mr = fixture("merge_request")
        mr.update(detailed_merge_status="need_rebase", diverged_commits_count=3)
        self.scenario(base_responses(mr=mr, graphql=graphql_with(resolve_thread)))
        code, out, _ = self.watch()
        self.assertEqual(code, 1)
        self.assertIn("!7 merge state is BEHIND (need_rebase): rebase the branch onto main before merging", out)

    def test_target_branch_moving_over_mr_files_is_an_event(self):
        moved = copy.deepcopy(fixture("branch"))
        moved["commit"]["id"] = NEW_BASE
        responses = base_responses()
        responses[f"api {P}/repository/branches/main"] = [ok(fixture("branch")), ok(moved)]
        self.scenario(responses)
        code, out, _ = self.watch(until="any-change")
        self.assertEqual(code, 0, out)
        self.assertIn("!7 main moved to c02c02c and touches files in this MR: src/app.py", out)

    def test_merged_exits_0(self):
        mr = fixture("merge_request")
        mr["state"] = "merged"
        self.scenario(base_responses(mr=mr))
        code, out, _ = self.watch()
        self.assertEqual((code, out.strip()), (0, f"!7 merged: {URL}"))

    def test_closed_exits_1(self):
        mr = fixture("merge_request")
        mr["state"] = "closed"
        self.scenario(base_responses(mr=mr))
        code, out, _ = self.watch()
        self.assertEqual((code, out.strip()), (1, f"!7 closed without merging: {URL}"))

    def test_unauthorized_names_the_fix(self):
        responses = base_responses()
        responses["api graphql"] = http_error(401, "Unauthorized")
        self.scenario(responses)
        code, out, _ = self.watch()
        self.assertEqual(code, 1)
        self.assertIn(f"glab auth login --hostname {HOST}", out)

    def test_token_never_reaches_argv_or_state(self):
        self.watch(until="green")
        self.assertTrue(self.calls())
        self.assertFalse(any(TOKEN in arg for call in self.calls() for arg in call))
        for path in self.state_dir.iterdir():
            self.assertNotIn(TOKEN, path.read_text())


class CommandLineTest(PrWaitTestCase):
    def test_help_does_not_call_glab(self):
        proc = subprocess.run([str(SCRIPT), "--help"], capture_output=True, text=True, env=os.environ.copy())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("GitLab merge request", proc.stdout)
        self.assertEqual(self.calls(), [])

    def test_script_is_executable_python(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK))
        self.assertEqual(SCRIPT.read_text().splitlines()[0], "#!/usr/bin/env python3")


if __name__ == "__main__":
    unittest.main()
