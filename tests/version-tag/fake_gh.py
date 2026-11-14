#!/usr/bin/env python3
"""A stand-in for `gh api`, driven by a JSON state file, for test_version_tag.py. It logs every
call and applies --jq with the real jq, so the workflow's jq expressions are exercised too.

State keys: repo, tip, releases (tags with a GitHub release), runs_by_tag ({tag: [{id, status,
conclusion}], newest first}), runs ({id: conclusion}), attempts ({id: n}), pr_labels ({sha: [names]
or null for no pull request}), run_conclusion (of dispatched runs), rerun_conclusion, rerun_lag
(reads of a re-run run that still show the old attempt), existing_refs, and error switches:
release_api_error, runs_list_error, dispatch_error, dispatch_empty, rerun_error, pulls_error.
Calls are recorded under created, dispatched and reruns.
"""
import json
import os
import subprocess
import sys

state_path = os.environ["FAKE_GH_STATE"]
log_path = os.environ["FAKE_GH_LOG"]
with open(state_path) as fh:
    state = json.load(fh)

args = sys.argv[1:]
with open(log_path, "a") as fh:
    fh.write(json.dumps(args) + "\n")

if not args or args[0] != "api":
    sys.stderr.write(f"fake gh: only 'api' is supported, got {args}\n")
    sys.exit(2)

method, jq_expr, fields, path = "GET", None, {}, None
i = 1
while i < len(args):
    a = args[i]
    if a == "--method":
        method = args[i + 1]; i += 2
    elif a == "--jq":
        jq_expr = args[i + 1]; i += 2
    elif a in ("-f", "-F"):
        k, _, v = args[i + 1].partition("=")
        fields[k] = (v == "true") if a == "-F" and v in ("true", "false") else v
        i += 2
    else:
        path = a; i += 1

repo = state["repo"]


def save():
    with open(state_path, "w") as fh:
        json.dump(state, fh)


def out(obj):
    text = json.dumps(obj)
    if jq_expr is not None:
        r = subprocess.run(["jq", "-r", jq_expr], input=text, capture_output=True, text=True)
        if r.returncode != 0:
            sys.stderr.write(r.stderr)
            sys.exit(r.returncode)
        sys.stdout.write(r.stdout)
    else:
        sys.stdout.write(text + "\n")
    sys.exit(0)


def err(code, msg):
    sys.stderr.write(f"gh: {msg} (HTTP {code})\n")
    sys.exit(1)


prefix = f"repos/{repo}/"
if not path or not path.startswith(prefix):
    err(404, f"Not Found: unexpected path {path}")
rest = path[len(prefix):]

if method == "GET" and rest.startswith("git/ref/heads/"):
    out({"object": {"sha": state["tip"]}})

if method == "GET" and rest.startswith("releases/tags/"):
    if state.get("release_api_error"):
        err(500, "Server Error")
    tag = rest[len("releases/tags/"):]
    if tag in state.get("releases", []):
        out({"tag_name": tag})
    err(404, "Not Found")

if method == "GET" and rest.startswith("actions/workflows/") and "/runs?" in rest:
    if state.get("runs_list_error"):
        err(500, "Server Error")
    params = dict(p.split("=", 1) for p in rest.split("?", 1)[1].split("&"))
    out({"workflow_runs": state.get("runs_by_tag", {}).get(params["branch"], [])})

if method == "POST" and rest.startswith("actions/workflows/") and rest.endswith("/dispatches"):
    if state.get("dispatch_error"):
        err(422, "Unprocessable Entity")
    run_id = 1000 + len(state.setdefault("dispatched", []))
    conclusion = state.get("run_conclusion", "success")
    state["dispatched"].append({"ref": fields.get("ref"), "return_run_details": fields.get("return_run_details"), "run": run_id})
    state.setdefault("runs", {})[str(run_id)] = conclusion
    state.setdefault("runs_by_tag", {}).setdefault(fields.get("ref"), []).insert(
        0, {"id": run_id, "status": "completed", "conclusion": conclusion})
    save()
    if state.get("dispatch_empty"):  # a 204 without a body, as without return_run_details
        sys.exit(0)
    out({"workflow_run_id": run_id, "run_url": f"https://api.github.com/{prefix}actions/runs/{run_id}",
         "html_url": f"https://github.com/{repo}/actions/runs/{run_id}"})

if method == "POST" and rest.startswith("actions/runs/") and rest.endswith("/rerun-failed-jobs"):
    if state.get("rerun_error"):
        err(403, "This workflow run cannot be re-run")
    run_id = rest[len("actions/runs/"):-len("/rerun-failed-jobs")]
    state.setdefault("reruns", []).append(int(run_id))
    state.setdefault("pending_reruns", {})[run_id] = state.get("rerun_lag", 0)
    save()
    sys.exit(0)  # 201 without a body

if method == "GET" and rest.startswith("actions/runs/"):
    run_id = rest[len("actions/runs/"):]
    attempts = state.setdefault("attempts", {})
    pending = state.setdefault("pending_reruns", {})
    if run_id in pending:
        if pending[run_id] > 0:  # the new attempt has not shown up yet: the old one still reads
            pending[run_id] -= 1
        else:
            del pending[run_id]
            attempts[run_id] = attempts.get(run_id, 1) + 1
            state.setdefault("runs", {})[run_id] = state.get("rerun_conclusion", "success")
        save()
    conclusion = state.get("runs", {}).get(run_id, state.get("run_conclusion", "success"))
    out({"status": "completed", "conclusion": conclusion, "run_attempt": attempts.get(run_id, 1)})

if method == "POST" and rest == "git/refs":
    ref = fields.get("ref", "")
    if ref in state.get("existing_refs", []):
        err(422, "Reference already exists")
    state.setdefault("created", []).append({"ref": ref, "sha": fields.get("sha")})
    save()
    out({"ref": ref, "object": {"sha": fields.get("sha"), "type": "commit"}})

if method == "GET" and rest.startswith("commits/") and rest.endswith("/pulls"):
    if state.get("pulls_error"):
        err(502, "Bad Gateway")
    sha = rest[len("commits/"):-len("/pulls")]
    labels = state.get("pr_labels", {}).get(sha, [])
    out([{"number": 1, "labels": [{"name": n} for n in labels]}] if labels is not None else [])

err(404, f"Not Found: no fake for {method} {path}")
