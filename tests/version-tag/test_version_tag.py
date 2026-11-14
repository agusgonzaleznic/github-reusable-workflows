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
PKG_PATHS = "pkg/\npyproject.toml\nREADME.md\nLICENSE\n"
RW_PATHS = ".github/workflows/\n"


class Fixture:
    def __init__(self, root):
        self.root = root
        (root / "home").mkdir()
        self.dir = root / "repo"
        self.dir.mkdir()
        self.env = {
            "PATH": "/opt/homebrew/bin:/usr/bin:/bin",
            "HOME": str(root / "home"),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        }
        self.git("init", "-q", "-b", "main")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.dir, env=self.env, check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self, files=None, move=None, msg="change"):
        for path, content in (files or {}).items():
            p = self.dir / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        if move:
            (self.dir / move[1]).parent.mkdir(parents=True, exist_ok=True)
            self.git("mv", move[0], move[1])
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", msg)
        return self.git("rev-parse", "HEAD")

    def tag(self, name, rev="HEAD"):
        self.git("tag", name, rev)


def base(root):
    fx = Fixture(root)
    fx.v100 = fx.commit({
        "pkg/__init__.py": '__version__ = "1.0.0"\n',
        "pkg/x.py": "x = 1\n",
        "tests/test_x.py": "pass\n",
        "README.md": "readme\n",
        "pyproject.toml": "[project]\n",
        ".github/workflows/ci.yml": "on: push\n",
        ".github/workflows/x.yml": "on: push\n",
    }, msg="first")
    fx.tag("v1.0.0")
    return fx


def run(fx, *, event, sha, version="", paths=PKG_PATHS, ref="refs/heads/main", trunk="main",
        pr_base="", pr_head="", pr_labels="null", workflow="release.yml", state=None, step=None):
    st = {"repo": REPO, "tip": sha, "releases": ["v1.0.0"]}
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
    env = dict(fx.env)
    env.update({
        "PATH": f"{bindir}:{fx.env['PATH']}",
        "FAKE_GH_STATE": str(state_file), "FAKE_GH_LOG": str(fx.root / "gh.log"),
        "GITHUB_OUTPUT": str(fx.root / "output"), "GITHUB_STEP_SUMMARY": str(fx.root / "summary"),
        "GH_TOKEN": "fake", "REPO": REPO, "EVENT": event, "REF": ref, "SHA": sha, "TRUNK": trunk,
        "PR_BASE": pr_base, "PR_HEAD": pr_head, "PR_LABELS": pr_labels, "VERSION": version,
        "RELEASE_PATHS": paths, "RELEASE_WORKFLOW": workflow,
    })
    r = subprocess.run([BASH, str(step)], cwd=fx.dir, env=env, capture_output=True, text=True, timeout=120)
    final = json.loads(state_file.read_text())
    return {
        "rc": r.returncode,
        "log": r.stdout + r.stderr,
        "created": [c["ref"] for c in final.get("created", [])],
        "created_on": [c["sha"] for c in final.get("created", [])],
        "dispatched": [d["ref"] for d in final.get("dispatched", [])],
        "run_details": [d["return_run_details"] for d in final.get("dispatched", [])],
        "output": (fx.root / "output").read_text(),
    }


SCENARIOS = []


def scenario(fn):
    SCENARIOS.append(fn)
    return fn


def expect(res, rc, created=(), dispatched=(), says=None):
    problems = []
    if res["rc"] != rc:
        problems.append(f"rc {res['rc']} != {rc}")
    if res["created"] != [f"refs/tags/{t}" for t in created]:
        problems.append(f"created {res['created']} != {list(created)}")
    if res["dispatched"] != list(dispatched):
        problems.append(f"dispatched {res['dispatched']} != {list(dispatched)}")
    if says and says not in res["log"]:
        problems.append(f"missing text {says!r}")
    if any(v is not True for v in res["run_details"]):
        problems.append("a dispatch without return_run_details=true")
    return problems


# ---- explicit version, push to main ----

@scenario
def e01_new_version_is_tagged_on_the_tip_and_released(root, step):
    fx = base(root)
    sha = fx.commit({"pkg/__init__.py": '__version__ = "1.0.1"\n'})
    res = run(fx, event="push", sha=sha, version="1.0.1", step=step)
    p = expect(res, 0, created=["v1.0.1"], dispatched=["v1.0.1"], says="Released v1.0.1")
    if res["created_on"] != [sha]:
        p.append(f"tag made on {res['created_on']}, not {sha}")
    if "tag=v1.0.1" not in res["output"]:
        p.append("no tag output")
    return p


@scenario
def e02_same_version_and_nothing_shipped_does_nothing(root, step):
    fx = base(root)
    sha = fx.commit({".github/workflows/ci.yml": "on: [push]\n", "tests/test_x.py": "pass  # more\n"})
    return expect(run(fx, event="push", sha=sha, version="1.0.0", step=step), 0, says="Nothing to release")


@scenario
def e03_same_version_with_a_shipped_change_turns_main_red(root, step):
    fx = base(root)
    sha = fx.commit({"README.md": "new readme\n"})
    return expect(run(fx, event="push", sha=sha, version="1.0.0", step=step), 1, says="Raise the version in a pull request")


@scenario
def e04_older_version_fails(root, step):
    fx = base(root)
    sha = fx.commit({"pkg/__init__.py": '__version__ = "0.9.0"\n'})
    return expect(run(fx, event="push", sha=sha, version="0.9.0", step=step), 1, says="older than the newest release")


@scenario
def e05_a_commit_that_is_not_the_tip_never_tags(root, step):
    fx = base(root)
    sha = fx.commit({"pkg/__init__.py": '__version__ = "1.0.1"\n'})
    res = run(fx, event="push", sha=sha, version="1.0.1", state={"tip": "f" * 40}, step=step)
    return expect(res, 0, says="has moved on")


@scenario
def e06_a_tag_without_release_is_released_again(root, step):
    fx = base(root)
    sha = fx.commit({"pkg/__init__.py": '__version__ = "1.0.1"\n'})
    fx.tag("v1.0.1")
    res = run(fx, event="push", sha=sha, version="1.0.1", step=step)
    return expect(res, 0, dispatched=["v1.0.1"], says="starting its release again")


@scenario
def e07_a_running_release_is_waited_for_not_started_twice(root, step):
    fx = base(root)
    sha = fx.commit({"pkg/__init__.py": '__version__ = "1.0.1"\n'})
    fx.tag("v1.0.1")
    res = run(fx, event="push", sha=sha, version="1.0.1",
              state={"active_runs": {"v1.0.1": [{"id": 77, "status": "in_progress"}]}, "runs": {"77": "success"}}, step=step)
    return expect(res, 0, says="still going: waiting")


@scenario
def e08_a_failed_release_run_fails_the_job(root, step):
    fx = base(root)
    sha = fx.commit({"pkg/__init__.py": '__version__ = "1.0.1"\n'})
    res = run(fx, event="push", sha=sha, version="1.0.1", state={"run_conclusion": "failure"}, step=step)
    return expect(res, 1, created=["v1.0.1"], dispatched=["v1.0.1"], says="ended 'failure'")


@scenario
def e09_a_version_with_a_suffix_is_refused_before_anything(root, step):
    fx = base(root)
    sha = fx.commit({"pkg/__init__.py": '__version__ = "1.0.1rc1"\n'})
    return expect(run(fx, event="push", sha=sha, version="1.0.1rc1", step=step), 1, says="is not X.Y.Z")


@scenario
def e10_a_push_to_another_branch_is_refused(root, step):
    fx = base(root)
    sha = fx.commit({"pkg/__init__.py": '__version__ = "1.0.1"\n'})
    return expect(run(fx, event="push", sha=sha, version="1.0.1", ref="refs/heads/feature", step=step), 1,
                  says="only from a push to the default branch")


@scenario
def e11_a_release_workflow_that_is_not_a_file_name_is_refused(root, step):
    fx = base(root)
    sha = fx.commit({"pkg/__init__.py": '__version__ = "1.0.1"\n'})
    return expect(run(fx, event="push", sha=sha, version="1.0.1", workflow="../x.yml", step=step), 1,
                  says="is not a workflow file name")


@scenario
def e12_a_failed_dispatch_fails_after_the_tag(root, step):
    fx = base(root)
    sha = fx.commit({"pkg/__init__.py": '__version__ = "1.0.1"\n'})
    res = run(fx, event="push", sha=sha, version="1.0.1", state={"dispatch_error": True}, step=step)
    return expect(res, 1, created=["v1.0.1"], says="Could not start release.yml")


@scenario
def e13_an_unclear_release_lookup_fails_closed(root, step):
    fx = base(root)
    sha = fx.commit({"pkg/__init__.py": '__version__ = "1.0.1"\n'})
    res = run(fx, event="push", sha=sha, version="1.0.1", state={"release_api_error": True}, step=step)
    return expect(res, 1, says="Cannot tell whether v1.0.0 has a release")


@scenario
def e14_versions_compare_as_numbers(root, step):
    fx = base(root)
    fx.commit({"pkg/__init__.py": '__version__ = "1.9.0"\n'})
    fx.tag("v1.9.0")
    fx.commit({"pkg/__init__.py": '__version__ = "1.10.0"\n'})
    fx.tag("v1.10.0")
    sha = fx.commit({"pkg/__init__.py": '__version__ = "1.10.1"\n'})
    res = run(fx, event="push", sha=sha, version="1.10.1",
              state={"releases": ["v1.0.0", "v1.9.0", "v1.10.0"]}, step=step)
    return expect(res, 0, created=["v1.10.1"], dispatched=["v1.10.1"])


@scenario
def e15_tags_of_another_shape_are_ignored(root, step):
    fx = base(root)
    fx.tag("v2")
    fx.tag("v3.0.0-rc1")
    fx.tag("v04.0.0")
    sha = fx.commit({"pkg/__init__.py": '__version__ = "1.0.1"\n'})
    return expect(run(fx, event="push", sha=sha, version="1.0.1", step=step), 0,
                  created=["v1.0.1"], dispatched=["v1.0.1"])


@scenario
def e16_first_release_without_any_tag(root, step):
    fx = Fixture(root)
    sha = fx.commit({"pkg/__init__.py": '__version__ = "1.0.0"\n'})
    return expect(run(fx, event="push", sha=sha, version="1.0.0", state={"releases": []}, step=step), 0,
                  created=["v1.0.0"], dispatched=["v1.0.0"])


@scenario
def e17_a_failed_run_list_is_reported_not_swallowed(root, step):
    fx = base(root)
    sha = fx.commit({"pkg/__init__.py": '__version__ = "1.0.1"\n'})
    fx.tag("v1.0.1")
    res = run(fx, event="push", sha=sha, version="1.0.1", state={"runs_list_error": True}, step=step)
    return expect(res, 1, says="::error::Cannot list the runs of release.yml for v1.0.1")


@scenario
def e18_a_dispatch_answer_without_a_run_fails(root, step):
    fx = base(root)
    sha = fx.commit({"pkg/__init__.py": '__version__ = "1.0.1"\n'})
    res = run(fx, event="push", sha=sha, version="1.0.1", state={"dispatch_empty": True}, step=step)
    return expect(res, 1, created=["v1.0.1"], dispatched=["v1.0.1"], says="the answer names no run")


# ---- explicit version, pull request ----

def pr(fx, files=None, move=None):
    base_sha = fx.git("rev-parse", "HEAD")
    fx.git("checkout", "-q", "-b", "topic")
    head = fx.commit(files, move=move)
    return base_sha, head


@scenario
def p01_a_shipped_change_without_a_new_version_fails(root, step):
    fx = base(root)
    b, h = pr(fx, {"README.md": "better\n"})
    return expect(run(fx, event="pull_request", sha=h, version="1.0.0", pr_base=b, pr_head=h,
                      ref="refs/pull/1/merge", step=step), 1, says="Raise the version")


@scenario
def p02_a_shipped_change_with_a_new_version_passes(root, step):
    fx = base(root)
    b, h = pr(fx, {"README.md": "better\n", "pkg/__init__.py": '__version__ = "1.0.1"\n'})
    return expect(run(fx, event="pull_request", sha=h, version="1.0.1", pr_base=b, pr_head=h,
                      ref="refs/pull/1/merge", step=step), 0, says="The merge releases v1.0.1")


@scenario
def p03_a_change_that_does_not_ship_needs_no_version(root, step):
    fx = base(root)
    b, h = pr(fx, {".github/workflows/ci.yml": "on: [push]\n", "tests/test_x.py": "pass  # more\n"})
    return expect(run(fx, event="pull_request", sha=h, version="1.0.0", pr_base=b, pr_head=h,
                      ref="refs/pull/1/merge", step=step), 0, says="needs no new version")


@scenario
def p04_moving_a_file_out_of_a_release_path_counts(root, step):
    fx = base(root)
    b, h = pr(fx, move=("pkg/x.py", "elsewhere/x.py"))
    return expect(run(fx, event="pull_request", sha=h, version="1.0.0", pr_base=b, pr_head=h,
                      ref="refs/pull/1/merge", step=step), 1, says="pkg/x.py")


@scenario
def p05_a_file_under_a_directory_path_counts(root, step):
    fx = base(root)
    b, h = pr(fx, {"pkg/deep/y.py": "y = 2\n"})
    return expect(run(fx, event="pull_request", sha=h, version="1.0.0", pr_base=b, pr_head=h,
                      ref="refs/pull/1/merge", step=step), 1, says="pkg/deep/y.py")


@scenario
def p06_a_lookalike_name_outside_the_paths_does_not_count(root, step):
    fx = base(root)
    b, h = pr(fx, {"pkg-extra/z.py": "z\n", "docs/README.md": "d\n", "README.md.bak": "b\n"})
    return expect(run(fx, event="pull_request", sha=h, version="1.0.0", pr_base=b, pr_head=h,
                      ref="refs/pull/1/merge", step=step), 0, says="needs no new version")


# ---- version empty (tags only), as the reusable workflows repository uses it ----

@scenario
def a01_a_shipped_change_releases_the_next_minor(root, step):
    fx = base(root)
    sha = fx.commit({".github/workflows/new.yml": "on: push\n"})
    res = run(fx, event="push", sha=sha, paths=RW_PATHS, step=step)
    return expect(res, 0, created=["v1.1.0"], dispatched=["v1.1.0"], says="Released v1.1.0")


@scenario
def a02_the_label_breaking_releases_the_next_major(root, step):
    fx = base(root)
    sha = fx.commit({".github/workflows/new.yml": "on: push\n"})
    res = run(fx, event="push", sha=sha, paths=RW_PATHS, state={"pr_labels": {sha: ["documentation", "breaking"]}}, step=step)
    return expect(res, 0, created=["v2.0.0"], dispatched=["v2.0.0"])


@scenario
def a03_a_label_on_an_earlier_unreleased_merge_counts(root, step):
    fx = base(root)
    first = fx.commit({".github/workflows/new.yml": "on: push\n"})
    sha = fx.commit({"README.md": "docs\n"})
    res = run(fx, event="push", sha=sha, paths=RW_PATHS, state={"pr_labels": {first: ["breaking"]}}, step=step)
    return expect(res, 0, created=["v2.0.0"], dispatched=["v2.0.0"])


@scenario
def a04_nothing_shipped_releases_nothing(root, step):
    fx = base(root)
    sha = fx.commit({"README.md": "docs\n"})
    return expect(run(fx, event="push", sha=sha, paths=RW_PATHS, step=step), 0, says="nothing to release")


@scenario
def a05_no_tag_yet_releases_1_0_0(root, step):
    fx = Fixture(root)
    sha = fx.commit({".github/workflows/x.yml": "on: push\n"})
    res = run(fx, event="push", sha=sha, paths=RW_PATHS, state={"releases": []}, step=step)
    return expect(res, 0, created=["v1.0.0"], dispatched=["v1.0.0"])


@scenario
def a06_a_failed_label_lookup_fails_closed_before_any_tag(root, step):
    fx = base(root)
    sha = fx.commit({".github/workflows/new.yml": "on: push\n"})
    res = run(fx, event="push", sha=sha, paths=RW_PATHS, state={"pulls_error": True}, step=step)
    return expect(res, 1, says="Cannot read the pull requests")


@scenario
def a07_pull_request_says_what_the_merge_releases(root, step):
    fx = base(root)
    b, h = pr(fx, {".github/workflows/new.yml": "on: push\n"})
    plain = run(fx, event="pull_request", sha=h, paths=RW_PATHS, pr_base=b, pr_head=h, pr_labels="[]",
                ref="refs/pull/1/merge", step=step)
    major = run(fx, event="pull_request", sha=h, paths=RW_PATHS, pr_base=b, pr_head=h, pr_labels='["breaking"]',
                ref="refs/pull/1/merge", step=step)
    return expect(plain, 0, says="The merge releases v1.1.0") + expect(major, 0, says="The merge releases v2.0.0")


@scenario
def a08_tag_without_release_is_finished_before_the_next(root, step):
    fx = base(root)
    fx.commit({".github/workflows/new.yml": "on: push\n"})
    fx.tag("v1.1.0")
    sha = fx.commit({".github/workflows/newer.yml": "on: push\n"})
    res = run(fx, event="push", sha=sha, paths=RW_PATHS, step=step)
    return expect(res, 0, created=["v1.2.0"], dispatched=["v1.1.0", "v1.2.0"])


@scenario
def x01_an_unknown_event_is_refused(root, step):
    fx = base(root)
    sha = fx.git("rev-parse", "HEAD")
    return expect(run(fx, event="schedule", sha=sha, version="1.0.0", step=step), 1, says="pull_request and push events only")


@scenario
def x02_a_parent_path_is_refused(root, step):
    fx = base(root)
    sha = fx.git("rev-parse", "HEAD")
    return expect(run(fx, event="push", sha=sha, version="1.0.0", paths="../outside/\n", step=step), 1,
                  says="must be relative")


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
            status = "ok  " if not problems else "FAIL"
            failed += bool(problems)
            print(f"{status} {fn.__name__}" + ("" if not problems else "  <- " + "; ".join(problems)))
    print(f"{len(SCENARIOS) - failed} of {len(SCENARIOS)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
