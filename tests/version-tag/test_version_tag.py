#!/usr/bin/env python3
"""Runs the script of version-tag.yml against throwaway git repositories and fake_gh.py.

Usage: test_version_tag.py [WORKFLOW]   (default: .github/workflows/version-tag.yml)
       test_version_tag.py --step SCRIPT (an already extracted script, for a deliberately broken copy)

Needs git, jq, yq (mikefarah) and bash 4.4 or newer. Nothing talks to GitHub: every gh call goes to
fake_gh.py. The repositories live in a temporary folder with their own empty HOME and no system git
config, so no local git setting (signing, hooks, aliases) applies to them.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
FAKE = HERE / "fake_gh.py"
WORKFLOW = HERE.parents[1] / ".github" / "workflows" / "version-tag.yml"
REPO = "owner/repo"
BASH = os.environ.get("TEST_BASH") or shutil.which("bash", path="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin")
PKG = "pkg/\npyproject.toml\nREADME.md\nLICENSE\n"  # a package whose code carries its version
WF = ".github/workflows/\n"  # a repository whose tags are its only version
DONE = {"id": 1, "status": "completed", "conclusion": "success"}
STUCK = {"v1.0.1": [{"id": 5, "status": "completed", "conclusion": "failure"}]}  # its release run failed


class Fixture:
    def __init__(self, root):
        self.root = root
        (root / "home").mkdir()
        self.dir = root / "repo"
        self.dir.mkdir()
        self.env = {
            "PATH": "/opt/homebrew/bin:/usr/bin:/bin", "HOME": str(root / "home"), "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        }
        self.git("init", "-q", "-b", "main")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.dir, env=self.env, check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self, files=None, move=None):
        for path, content in (files or {}).items():
            p = self.dir / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        if move:
            (self.dir / move[1]).parent.mkdir(parents=True, exist_ok=True)
            self.git("mv", move[0], move[1])
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", "change")
        return self.git("rev-parse", "HEAD")

    def bump(self, version, files=None):
        return self.commit({"pkg/__init__.py": f'__version__ = "{version}"\n', **(files or {})})

    def tag(self, name):
        self.git("tag", name)

    def topic(self, files=None, move=None):
        """A pull request branch: (base, head)."""
        base = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "-b", "topic")
        return base, self.commit(files, move=move)


def base(root):
    fx = Fixture(root)
    fx.commit({"pkg/__init__.py": '__version__ = "1.0.0"\n', "pkg/x.py": "x = 1\n", "tests/test_x.py": "pass\n",
               "README.md": "readme\n", "pyproject.toml": "[project]\n", ".github/workflows/ci.yml": "on: push\n"})
    fx.tag("v1.0.0")
    return fx


def run(fx, step, *, event="push", version="", tags=False, paths=PKG, ref="refs/heads/main", pr=None,
        labels="null", workflow="release.yml", state=None, env=None):
    sha = pr[1] if pr else fx.git("rev-parse", "HEAD")
    st = {"repo": REPO, "tip": sha, "releases": ["v1.0.0"], "runs_by_tag": {"v1.0.0": [DONE]}, "runs": {"1": "success"}}
    st.update(state or {})
    state_file = fx.root / "state.json"
    state_file.write_text(json.dumps(st))
    for name in ("gh.log", "output", "summary"):
        (fx.root / name).write_text("")
    bindir = fx.root / "bin"
    bindir.mkdir(exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(f'#!/bin/sh\nexec "{sys.executable}" -I "{FAKE}" "$@"\n')
    gh.chmod(0o755)
    step_env = dict(fx.env, PATH=f"{bindir}:{fx.env['PATH']}", FAKE_GH_STATE=str(state_file),
                    FAKE_GH_LOG=str(fx.root / "gh.log"), GITHUB_OUTPUT=str(fx.root / "output"),
                    GITHUB_STEP_SUMMARY=str(fx.root / "summary"), GH_TOKEN="fake", REPO=REPO, EVENT=event, REF=ref,
                    SHA=sha, TRUNK="main", PR_BASE=pr[0] if pr else "", PR_HEAD=pr[1] if pr else "",
                    PR_LABELS=labels, VERSION=version, VERSION_FROM_TAGS="true" if tags else "false",
                    RELEASE_PATHS=paths, RELEASE_WORKFLOW=workflow)
    step_env.update(env or {})
    r = subprocess.run([BASH, str(step)], cwd=fx.dir, env=step_env, capture_output=True, text=True, timeout=120)
    final = json.loads(state_file.read_text())
    return {"rc": r.returncode, "log": r.stdout + r.stderr, "sha": sha,
            "created": [c["ref"].removeprefix("refs/tags/") for c in final.get("created", [])],
            "created_on": [c["sha"] for c in final.get("created", [])],
            "dispatched": [d["ref"] for d in final.get("dispatched", [])],
            "details": [d["return_run_details"] for d in final.get("dispatched", [])],
            "reruns": final.get("reruns", []), "output": (fx.root / "output").read_text()}


def pr_run(fx, step, files=None, move=None, **kw):
    return run(fx, step, event="pull_request", ref="refs/pull/1/merge", pr=fx.topic(files, move), **kw)


def expect(res, rc, created=(), dispatched=(), says=(), reruns=()):
    problems = []
    if res["rc"] != rc:
        problems.append(f"rc {res['rc']} != {rc}")
    for key, want in (("created", created), ("dispatched", dispatched), ("reruns", reruns)):
        if res[key] != list(want):
            problems.append(f"{key} {res[key]} != {list(want)}")
    for text in (says,) if isinstance(says, str) else says:
        if text not in res["log"]:
            problems.append(f"missing text {text!r}")
    if any(v is not True for v in res["details"]):
        problems.append("a dispatch without return_run_details=true")
    if created and any(s != res["sha"] for s in res["created_on"]):
        problems.append(f"tagged {res['created_on']}, not {res['sha']}")
    return problems


SCENARIOS = []


def scenario(fn):
    SCENARIOS.append(fn)
    return fn


# ---- version set, push to main ----

@scenario
def e01_a_new_version_is_tagged_on_the_tip_and_released(root, step):
    fx = base(root)
    fx.bump("1.0.1")
    res = run(fx, step, version="1.0.1")
    p = expect(res, 0, created=["v1.0.1"], dispatched=["v1.0.1"], says="Released v1.0.1")
    return p + ([] if "tag=v1.0.1" in res["output"] else ["no tag output"])


@scenario
def e02_the_same_version_with_nothing_shipped_does_nothing(root, step):
    fx = base(root)
    fx.commit({".github/workflows/ci.yml": "on: [push]\n", "tests/test_x.py": "pass  # more\n"})
    # v1.0.0 has a GitHub release and no run: it was released before this workflow
    return expect(run(fx, step, version="1.0.0", state={"runs_by_tag": {}}), 0, says="Nothing to release")


@scenario
def e03_the_same_version_with_a_shipped_change_turns_main_red(root, step):
    fx = base(root)
    fx.commit({"README.md": "new readme\n"})
    return expect(run(fx, step, version="1.0.0"), 1, says="Raise the version in a pull request")


@scenario
def e04_an_older_version_fails(root, step):
    fx = base(root)
    fx.bump("0.9.0")
    return expect(run(fx, step, version="0.9.0"), 1, says="older than the newest release")


@scenario
def e05_a_commit_that_is_not_the_tip_never_tags(root, step):
    fx = base(root)
    fx.bump("1.0.1")
    return expect(run(fx, step, version="1.0.1", state={"tip": "f" * 40}), 0, says="has moved on")


@scenario
def e06_a_tag_without_release_or_run_is_released_again(root, step):
    fx = base(root)
    fx.bump("1.0.1")
    fx.tag("v1.0.1")
    return expect(run(fx, step, version="1.0.1"), 0, dispatched=["v1.0.1"], says="starting its release again")


@scenario
def e07_a_running_release_is_waited_for_not_started_twice(root, step):
    fx = base(root)
    fx.bump("1.0.1")
    fx.tag("v1.0.1")
    state = {"runs_by_tag": {"v1.0.1": [{"id": 77, "status": "in_progress", "conclusion": None}]}, "runs": {"77": "success"}}
    return expect(run(fx, step, version="1.0.1", state=state), 0, says=("still going: waiting", "Released v1.0.1"))


@scenario
def e08_a_failed_release_run_fails_the_job(root, step):
    fx = base(root)
    fx.bump("1.0.1")
    res = run(fx, step, version="1.0.1", state={"run_conclusion": "failure"})
    return expect(res, 1, created=["v1.0.1"], dispatched=["v1.0.1"], says=("ended 'failure'", "replaces v1.0.1"))


@scenario
def e09_a_failed_dispatch_fails_after_the_tag(root, step):
    fx = base(root)
    fx.bump("1.0.1")
    res = run(fx, step, version="1.0.1", state={"dispatch_error": True})
    return expect(res, 1, created=["v1.0.1"], says="Could not start release.yml")


@scenario
def e10_a_dispatch_answer_without_a_run_fails(root, step):
    fx = base(root)
    fx.bump("1.0.1")
    res = run(fx, step, version="1.0.1", state={"dispatch_empty": True})
    return expect(res, 1, created=["v1.0.1"], dispatched=["v1.0.1"], says="the answer names no run")


@scenario
def e11_an_unclear_release_lookup_fails_closed(root, step):
    fx = base(root)
    return expect(run(fx, step, version="1.0.0", state={"runs_by_tag": {}, "release_api_error": True}), 1,
                  says="Cannot tell whether v1.0.0 has a release")


@scenario
def e12_a_failed_run_list_is_reported_not_swallowed(root, step):
    fx = base(root)
    fx.bump("1.0.1")
    fx.tag("v1.0.1")
    return expect(run(fx, step, version="1.0.1", state={"runs_list_error": True}), 1,
                  says="::error::Cannot list the runs of release.yml for v1.0.1")


@scenario
def e13_a_tip_that_is_not_a_commit_fails(root, step):
    fx = base(root)
    fx.bump("1.0.1")
    return expect(run(fx, step, version="1.0.1", state={"tip": "null"}), 1, says="Cannot read the tip of main")


@scenario
def e14_versions_compare_as_numbers(root, step):
    fx = base(root)
    for v in ("1.9.0", "1.10.0"):
        fx.bump(v)
        fx.tag(f"v{v}")
    fx.bump("1.10.1")
    res = run(fx, step, version="1.10.1", state={"releases": ["v1.0.0", "v1.9.0", "v1.10.0"]})
    return expect(res, 0, created=["v1.10.1"], dispatched=["v1.10.1"])


@scenario
def e15_tags_of_another_shape_are_ignored(root, step):
    fx = base(root)
    for t in ("v2", "v3.0.0-rc1", "v04.0.0"):
        fx.tag(t)
    fx.bump("1.0.1")
    return expect(run(fx, step, version="1.0.1"), 0, created=["v1.0.1"], dispatched=["v1.0.1"])


@scenario
def e16_the_first_release_without_any_tag(root, step):
    fx = Fixture(root)
    fx.bump("1.0.0")
    res = run(fx, step, version="1.0.0", state={"releases": [], "runs_by_tag": {}})
    return expect(res, 0, created=["v1.0.0"], dispatched=["v1.0.0"])


# ---- finishing a release whose run failed, after its GitHub release (an upload to PyPI, say) ----

def stuck(root, **state):
    fx = base(root)
    fx.bump("1.0.1")
    fx.tag("v1.0.1")
    return fx, dict({"releases": ["v1.0.0", "v1.0.1"], "runs_by_tag": STUCK, "runs": {"5": "failure"}}, **state)


@scenario
def f01_the_failed_jobs_of_a_release_run_are_re_run(root, step):
    fx, state = stuck(root)
    return expect(run(fx, step, version="1.0.1", state=state), 0, reruns=[5],
                  says=("re-running its failed jobs", "Released v1.0.1"))


@scenario
def f02_a_re_run_that_fails_again_turns_main_red(root, step):
    fx, state = stuck(root, rerun_conclusion="failure")
    return expect(run(fx, step, version="1.0.1", state=state), 1, reruns=[5], says="ended 'failure'")


@scenario
def f03_a_successful_run_finishes_the_release_without_a_github_release(root, step):
    fx, state = stuck(root, releases=["v1.0.0"])
    state["runs_by_tag"] = {"v1.0.1": [STUCK["v1.0.1"][0], dict(DONE, id=4)]}
    return expect(run(fx, step, version="1.0.1", state=state), 0, says="Nothing to release")


@scenario
def f04_the_re_run_is_watched_once_its_new_attempt_started(root, step):
    # Two reads after the re-run still show the old attempt, so the wait has to poll more than once
    fx, state = stuck(root, rerun_lag=2)
    return expect(run(fx, step, version="1.0.1", state=state), 0, reruns=[5], says="Released v1.0.1")


@scenario
def f05_a_refused_re_run_fails(root, step):
    fx, state = stuck(root, rerun_error=True)
    return expect(run(fx, step, version="1.0.1", state=state), 1, says="Could not re-run the failed jobs")


@scenario
def s01_a_newer_version_replaces_a_stuck_tag(root, step):
    fx, state = stuck(root, releases=["v1.0.0"])
    fx.bump("1.0.2")
    return expect(run(fx, step, version="1.0.2", state=state), 0, created=["v1.0.2"], dispatched=["v1.0.2"])


@scenario
def s02_a_newer_tag_replaces_a_stuck_tag_in_tags_mode(root, step):
    fx = base(root)
    fx.commit({".github/workflows/new.yml": "on: push\n"})
    fx.tag("v1.1.0")
    fx.commit({".github/workflows/newer.yml": "on: push\n"})
    res = run(fx, step, tags=True, paths=WF, state={"runs_by_tag": {"v1.1.0": STUCK["v1.0.1"]}})
    return expect(res, 0, created=["v1.2.0"], dispatched=["v1.2.0"])


# ---- input mistakes ----

@scenario
def x01_each_input_mistake_stops_the_job(root, step):
    fx = base(root)
    fx.bump("1.0.1")
    cases = [
        ({"version": ""}, "The version is empty"),
        ({"tags": True}, "not both"),
        ({"version": "1.0.1rc1"}, "is not X.Y.Z"),
        ({"paths": "../outside/\n"}, "must be relative"),
        ({"paths": "pkg\nREADME.md\n"}, "is a directory: write 'pkg/'"),
        ({"ref": "refs/heads/feature"}, "only from a push to the default branch"),
        ({"workflow": "../x.yml"}, "is not a workflow file name"),
        ({"event": "schedule"}, "pull_request and push events only"),
        ({"env": {"GIT_DIR": str(root / "missing")}}, "Cannot list the tags"),
    ]
    return [f"{says!r}: {p}" for kw, says in cases
            for p in expect(run(fx, step, **{"version": "1.0.1", **kw}), 1, says=says)]


@scenario
def x02_an_empty_version_fails_the_pull_request(root, step):
    return expect(pr_run(base(root), step, {"README.md": "better\n"}), 1, says="The version is empty")


# ---- version set, pull request ----

@scenario
def p01_a_shipped_change_without_a_new_version_fails(root, step):
    return expect(pr_run(base(root), step, {"README.md": "better\n"}, version="1.0.0"), 1, says="Raise the version")


@scenario
def p02_a_shipped_change_with_a_new_version_passes(root, step):
    files = {"README.md": "better\n", "pkg/__init__.py": '__version__ = "1.0.1"\n'}
    return expect(pr_run(base(root), step, files, version="1.0.1"), 0, says="The merge releases v1.0.1")


@scenario
def p03_a_change_that_does_not_ship_needs_no_version(root, step):
    files = {".github/workflows/ci.yml": "on: [push]\n", "tests/test_x.py": "pass  # more\n"}
    return expect(pr_run(base(root), step, files, version="1.0.0"), 0, says="needs no new version")


@scenario
def p04_moving_a_file_out_of_a_release_path_counts(root, step):
    return expect(pr_run(base(root), step, move=("pkg/x.py", "elsewhere/x.py"), version="1.0.0"), 1, says="pkg/x.py")


@scenario
def p05_a_file_under_a_directory_path_counts(root, step):
    return expect(pr_run(base(root), step, {"pkg/deep/y.py": "y = 2\n"}, version="1.0.0"), 1, says="pkg/deep/y.py")


@scenario
def p06_a_lookalike_name_outside_the_paths_does_not_count(root, step):
    files = {"pkg-extra/z.py": "z\n", "docs/README.md": "d\n", "README.md.bak": "b\n"}
    return expect(pr_run(base(root), step, files, version="1.0.0"), 0, says="needs no new version")


# ---- version from the tags, as the reusable workflows repository uses it ----

@scenario
def a01_a_shipped_change_releases_the_next_minor(root, step):
    fx = base(root)
    fx.commit({".github/workflows/new.yml": "on: push\n"})
    return expect(run(fx, step, tags=True, paths=WF), 0, created=["v1.1.0"], dispatched=["v1.1.0"], says="Released v1.1.0")


@scenario
def a02_the_label_breaking_releases_the_next_major(root, step):
    fx = base(root)
    sha = fx.commit({".github/workflows/new.yml": "on: push\n"})
    res = run(fx, step, tags=True, paths=WF, state={"pr_labels": {sha: ["documentation", "breaking"]}})
    return expect(res, 0, created=["v2.0.0"], dispatched=["v2.0.0"])


@scenario
def a03_a_label_on_an_earlier_unreleased_merge_counts(root, step):
    fx = base(root)
    first = fx.commit({".github/workflows/new.yml": "on: push\n"})
    fx.commit({"README.md": "docs\n"})
    res = run(fx, step, tags=True, paths=WF, state={"pr_labels": {first: ["breaking"]}})
    return expect(res, 0, created=["v2.0.0"], dispatched=["v2.0.0"])


@scenario
def a04_nothing_shipped_releases_nothing(root, step):
    fx = base(root)
    fx.commit({"README.md": "docs\n"})
    return expect(run(fx, step, tags=True, paths=WF), 0, says="Nothing to release")


@scenario
def a05_no_tag_yet_releases_1_0_0(root, step):
    fx = Fixture(root)
    fx.commit({".github/workflows/x.yml": "on: push\n"})
    res = run(fx, step, tags=True, paths=WF, state={"releases": [], "runs_by_tag": {}})
    return expect(res, 0, created=["v1.0.0"], dispatched=["v1.0.0"])


@scenario
def a06_a_failed_label_lookup_fails_closed_before_any_tag(root, step):
    fx = base(root)
    fx.commit({".github/workflows/new.yml": "on: push\n"})
    return expect(run(fx, step, tags=True, paths=WF, state={"pulls_error": True}), 1, says="Cannot read the pull requests")


@scenario
def a07_the_pull_request_says_what_the_merge_releases(root, step):
    fx = base(root)
    pr = fx.topic({".github/workflows/new.yml": "on: push\n"})
    common = dict(event="pull_request", ref="refs/pull/1/merge", pr=pr, tags=True, paths=WF)
    return (expect(run(fx, step, labels="[]", **common), 0, says="The merge releases v1.1.0")
            + expect(run(fx, step, labels='["breaking"]', **common), 0, says="The merge releases v2.0.0"))


@scenario
def a08_a_commit_without_a_pull_request_gets_a_warning(root, step):
    fx = base(root)
    sha = fx.commit({".github/workflows/new.yml": "on: push\n"})
    res = run(fx, step, tags=True, paths=WF, state={"pr_labels": {sha: None}})
    return expect(res, 0, created=["v1.1.0"], dispatched=["v1.1.0"], says="::warning::")


# ---- tags without the v (X.Y.Z, made by hand before this workflow) ----

def bare(root, files):
    """A repository whose only tag is 1.0.0, without the v, with no run and no GitHub release known."""
    fx = Fixture(root)
    fx.commit(files)
    fx.tag("1.0.0")
    return fx


BARE = {"releases": [], "runs_by_tag": {}}


@scenario
def b01_a_bare_newest_tag_with_nothing_shipped_starts_no_release(root, step):
    fx = bare(root, {".github/workflows/x.yml": "on: push\n"})
    fx.commit({"README.md": "docs\n"})
    return expect(run(fx, step, tags=True, paths=WF, state=BARE), 0, says="Nothing to release: 1.0.0 is out")


@scenario
def b02_a_bare_newest_tag_counts_for_the_next_version(root, step):
    fx = bare(root, {".github/workflows/x.yml": "on: push\n"})
    fx.commit({".github/workflows/y.yml": "on: push\n"})
    return expect(run(fx, step, tags=True, paths=WF, state=BARE), 0, created=["v1.1.0"], dispatched=["v1.1.0"],
                  says="Released v1.1.0")


@scenario
def b03_the_v_tag_wins_when_both_name_the_newest_version(root, step):
    fx = base(root)
    fx.tag("1.0.0")  # git lists 1.0.0 before v1.0.0: the tie needs its own rule
    fx.commit({"README.md": "docs\n"})
    # v1.0.0 has neither a run nor a release, so finishing it starts its release; the bare tag would not
    return expect(run(fx, step, tags=True, paths=WF, state=BARE), 0, dispatched=["v1.0.0"], says="starting its release again")


@scenario
def b04_a_bare_tag_older_than_a_v_tag_is_not_the_newest(root, step):
    fx = bare(root, {".github/workflows/x.yml": "on: push\n"})
    fx.commit({".github/workflows/y.yml": "on: push\n"})
    fx.tag("v1.1.0")
    fx.commit({".github/workflows/z.yml": "on: push\n"})
    res = run(fx, step, tags=True, paths=WF, state={"releases": [], "runs_by_tag": {"v1.1.0": [DONE]}})
    return expect(res, 0, created=["v1.2.0"], dispatched=["v1.2.0"])


@scenario
def b05_a_bare_newest_tag_in_version_mode(root, step):
    files = {"pkg/__init__.py": '__version__ = "1.0.0"\n', "README.md": "readme\n"}
    fx = bare(root, files)
    fx.commit({"tests/test_x.py": "pass\n"})
    problems = expect(run(fx, step, version="1.0.0", state=BARE), 0, says="Nothing to release: 1.0.0 is out")
    fx.commit({"README.md": "better\n"})
    problems += expect(run(fx, step, version="1.0.0", state=BARE), 1, says="changed since 1.0.0")
    fx.bump("1.0.1")
    return problems + expect(run(fx, step, version="1.0.1", state=BARE), 0, created=["v1.0.1"], dispatched=["v1.0.1"])


@scenario
def b06_pull_requests_read_a_bare_newest_tag(root, step):
    fx = bare(root, {"pkg/__init__.py": '__version__ = "1.0.0"\n', ".github/workflows/x.yml": "on: push\n"})
    pr = fx.topic({"pkg/__init__.py": '__version__ = "1.0.0"\n# more\n', ".github/workflows/y.yml": "on: push\n"})
    common = dict(event="pull_request", ref="refs/pull/1/merge", pr=pr, state=BARE)
    return (expect(run(fx, step, version="1.0.0", **common), 1, says="and 1.0.0 is already out")
            + expect(run(fx, step, tags=True, paths=WF, labels="[]", **common), 0, says="The merge releases v1.1.0"))


@scenario
def b07_bare_tags_of_another_shape_are_ignored(root, step):
    fx = base(root)
    for t in ("2", "3.0.0-rc1", "04.0.0", "1.5"):
        fx.tag(t)
    fx.commit({".github/workflows/new.yml": "on: push\n"})
    return expect(run(fx, step, tags=True, paths=WF), 0, created=["v1.1.0"], dispatched=["v1.1.0"])


def extract(workflow, dest):
    """Writes the run script of the step with id "version" to dest."""
    script = subprocess.run(["yq", "-r", '.jobs.version.steps[] | select(.id == "version") | .run', str(workflow)],
                            check=True, capture_output=True, text=True).stdout
    if "set -euo pipefail" not in script:
        sys.exit(f"No script found in the step with id 'version' of {workflow}")
    dest.write_text(script)
    return dest


def main():
    if not BASH or subprocess.run([BASH, "-c", "shopt -s inherit_errexit"]).returncode != 0:
        sys.exit(f"Needs bash 4.4 or newer, found {BASH}")
    failed = 0
    with tempfile.TemporaryDirectory(prefix="vt-step-") as scratch:
        if sys.argv[1:2] == ["--step"]:
            step = pathlib.Path(sys.argv[2]).resolve()
        else:
            step = extract(pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else WORKFLOW, pathlib.Path(scratch) / "step.sh")
        for fn in SCENARIOS:
            with tempfile.TemporaryDirectory(prefix="vt-") as tmp:
                try:
                    problems = fn(pathlib.Path(tmp), step)
                except Exception as exc:  # a harness error counts as a failure
                    problems = [f"harness error: {exc!r}"]
            failed += bool(problems)
            print(f"{'FAIL' if problems else 'ok  '} {fn.__name__}" + ("  <- " + "; ".join(problems) if problems else ""))
    print(f"{len(SCENARIOS) - failed} of {len(SCENARIOS)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
