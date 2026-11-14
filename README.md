<div align="center">

<img src="assets/emblem.svg" width="88" alt="github-reusable-workflows emblem: three connected steps, the last one the result">

# github-reusable-workflows

### One place for the CI/CD steps my repositories share.

**Eight reusable GitHub Actions workflows:** build and deploy a Vite site, build and test a Python
package, lint workflows and prove their action pins, check security alerts, and make the merge to
`main` the release. Callers pin a full commit SHA, and every input, output and permission is read
from the workflow files.

<br>

[![release](https://img.shields.io/github/v/release/agusgonzaleznic/github-reusable-workflows?style=for-the-badge&labelColor=1A1D23&color=555D6D&logo=github&logoColor=FAFAFA)](https://github.com/agusgonzaleznic/github-reusable-workflows/releases)
[![lint](https://img.shields.io/github/actions/workflow/status/agusgonzaleznic/github-reusable-workflows/lint.yml?branch=main&style=for-the-badge&labelColor=1A1D23&color=555D6D&label=lint)](https://github.com/agusgonzaleznic/github-reusable-workflows/actions/workflows/lint.yml)
<br>
[![runs on](https://img.shields.io/badge/runs_on-GitHub_Actions-555D6D?style=for-the-badge&labelColor=1A1D23&logo=githubactions&logoColor=FAFAFA)](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows)
[![pins](https://img.shields.io/badge/pins-full_commit_SHA-555D6D?style=for-the-badge&labelColor=1A1D23)](#-security)

**[Quick start](#-quick-start) · [Workflows](#-the-workflows) · [Releases](#-how-a-release-happens) · [Security](#-security) · [Troubleshooting](#-troubleshooting) · [Contributing](#-contributing) · [Support](#-support-this-project)**

</div>

---

## 🧭 What this is

Each file under `.github/workflows/` with `workflow_call` as its trigger is a reusable workflow.
A repository calls one with a short job and keeps nothing else of it. As of 14 November 2026 there
are eight, and the latest release is v1.10.0. Two more files here, `lint.yml` and `release.yml`, are
this repository's own gate and release, and they call the shared ones.

What it doesn't do:

- **No upload to PyPI**: the caller keeps one short publish job (see [Python Build](#python-build)).
- **The Vite cache is npm only.** The two Vite workflows always set up Node with `cache: 'npm'`. The
  install, lint and build commands are inputs.
- **No test of the Vite, Python and alert workflows until someone calls them.** Every pull request
  here runs actionlint, the action-pin check and the scenarios of `version-tag.yml`, and
  `github-release.yml` runs on every release.
- **No licence file yet** (see [Licence](#licence)).

## ⚡ Quick start

Call a workflow from a job, pinned to a full commit SHA with the release in a comment:

```yaml
# on: pull_request, branches: [main]
jobs:
  ci:
    uses: agusgonzaleznic/github-reusable-workflows/.github/workflows/vite-ci.yml@3f7c141f6c330d47a854111aabf2b48d827d2cd1  # v1.10.0
```

Every example below pins v1.10.0, the latest release as of 14 November 2026. Resolve the SHA of the
release you want with:

```bash
gh api repos/agusgonzaleznic/github-reusable-workflows/commits/v1.10.0 --jq .sha
```

A caller names a check `<calling job name> / <job name>`, so the job names below are part of the
contract, and a ruleset can require them. Each workflow file documents its inputs and outputs under
`on.workflow_call`, and the workflow's section below links to the file.

| Workflow | What it does | The caller grants | Its checks |
|---|---|---|---|
| [`vite-build-deploy.yml`](#vite-build-and-deploy) | Builds a Vite app and deploys it to GitHub Pages | `contents: read`, `pages: write`, `id-token: write` | `Build`, `Deploy` |
| [`vite-ci.yml`](#vite-ci) | Lints and builds a Vite app on pull requests | `contents: read` | `Lint and Build` |
| [`python-build.yml`](#python-build) | Builds the sdist and wheel with uv, uploads them as one artifact | `contents: read` | `Build sdist and wheel` |
| [`actions-lint.yml`](#lint-workflows-and-action-pins) | actionlint plus a proof of every action pin | `contents: read` | `actionlint`, `Verify action pins` |
| [`python-tests.yml`](#python-tests) | Runs the tests once per Python version, from hash-locked requirements | `contents: read` | `Python 3.12`, `Python 3.13` (one per version) |
| [`security-alerts.yml`](#security-alerts) | Lists open alerts of every repository an account owns, fails on any | nothing | `Open security alerts` |
| [`github-release.yml`](#github-release) | Publishes the GitHub release of a version tag, from the trunk only | `contents: write` | `Publish the release` |
| [`version-tag.yml`](#version-tag) | Makes the merge to the default branch the release | see [Version Tag](#version-tag) | `Check the version`, `Tag the version` |

## 📦 The workflows

### Vite Build and Deploy

[`vite-build-deploy.yml`](.github/workflows/vite-build-deploy.yml) builds a Vite application and
deploys it to GitHub Pages. The caller grants at least the permissions the jobs declare, and owns the
concurrency group (`pages`, with `cancel-in-progress: false`).

```yaml
jobs:
  build-and-deploy:
    uses: agusgonzaleznic/github-reusable-workflows/.github/workflows/vite-build-deploy.yml@3f7c141f6c330d47a854111aabf2b48d827d2cd1  # v1.10.0
    permissions:
      contents: read
      pages: write
      id-token: write
    with:
      artifact-path: 'dist'  # Optional, default: 'dist'
    secrets:
      build-env-vars: ${{ secrets.BUILD_ENV_VARS }}  # Optional, KEY=value lines
```

The other inputs (`node-version`, `install-command`, `lint-command`, `build-command`, `run-lint`) are
optional and have defaults.

The `build` job fails when `index.html` isn't in the artifact path. `build-env-vars` is appended to
`$GITHUB_ENV` as written, so every later step sees it, dependency build code included. Before that,
the workflow masks each value of 8 characters or more (empty lines, `#` lines and `KEY=` lines get no
mask). Don't put comments in the secret: the runner rejects a line without `=`. A shorter value isn't
masked, so don't print it. The repository must deploy from GitHub Actions (see
[Troubleshooting](#-troubleshooting)).

### Vite CI

[`vite-ci.yml`](.github/workflows/vite-ci.yml) lints and builds a Vite application, for pull requests.
It takes the same inputs as the deploy workflow, except `run-lint`, and no secrets. Its own input
`verify-build-output` (default `true`) fails the job unless `artifact-path` is a directory that holds
`index.html`. A call is in [Quick start](#-quick-start).

### Python Build

[`python-build.yml`](.github/workflows/python-build.yml) builds the sdist and wheel of a Python
project with uv and uploads them as one artifact, ready for a publish job in the calling workflow. On
a tag it fails when the built version differs from the tag (`v1.2.3` or `1.2.3`). The artifact is kept
for 7 days. Its output `version` is the version that was built.

The upload to PyPI can't live here. PyPI's Trusted Publishing only trusts a job defined in the
workflow file registered on PyPI, and a job from another repository's reusable workflow never matches
it ([pypi/warehouse#11096](https://github.com/pypi/warehouse/issues/11096), open as of 14 November
2026). So the caller keeps one short publish job, and no PyPI token is involved. Put the build and the
publish in the workflow that runs on the version tag (`release.yml` here), so PyPI registers one file
name. The same `build` job can feed [GitHub Release](#github-release).

```yaml
jobs:
  build:
    uses: agusgonzaleznic/github-reusable-workflows/.github/workflows/python-build.yml@3f7c141f6c330d47a854111aabf2b48d827d2cd1  # v1.10.0
    permissions:
      contents: read
    with:
      build-constraints: requirements/build.txt  # Optional, default: '' (no lock)

  publish:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url: https://pypi.org/project/<name>/${{ needs.build.outputs.version }}/
    permissions:
      id-token: write  # Trusted Publishing, nothing else
    steps:
      - uses: actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333  # v8.0.2
        with:
          name: python-dist
          path: dist/
      - uses: pypa/gh-action-pypi-publish@7245906fb61fa33a13554f9d5fb856fe61758086  # v1.14.3
```

On PyPI, the project's Publishing settings need a GitHub publisher with the owner, the repository, the
caller's workflow file name (`release.yml`, never `python-build.yml`) and the environment (`pypi`). On
GitHub, an environment of that name limited to `v*` tags keeps any other ref from publishing.

`uv build` fetches the project's build backend (hatchling, say) from PyPI at build time, and a
constraints file compiled with hashes pins it (`uv pip compile --universal --generate-hashes`, for the
oldest Python the project supports, leaving out releases younger than a week). The `uv-version` and
`python-version` defaults change only by hand here. Dependabot doesn't see them.

### Lint Workflows and Action Pins

[`actions-lint.yml`](.github/workflows/actions-lint.yml) lints the caller's workflows with actionlint
1.7.12 (the linux amd64 build, checksum-verified) and proves every action pin: a full commit SHA, a
`# vX.Y.Z` comment, and that tag resolving to exactly that commit upstream. A pattern or path that
matches nothing fails, so a typo can't pass. This repository's own `lint.yml` calls it too.

Call it from a job named `Lint` (its checks are `Lint / actionlint` and `Lint / Verify action pins`),
for example with `pin-paths: .github/workflows action.yml` (default `.github/workflows`). The file
also takes `actionlint-files`, `prepare-command` (before actionlint, for example rendering workflow
templates), `extra-pin-command` (after the pin check, with `GH_TOKEN` set) and `runs-on`, which must be
a Linux x64 runner.

### Python Tests

[`python-tests.yml`](.github/workflows/python-tests.yml) runs a Python project's tests once per Python
version, in a fresh venv that installs only hash-locked requirements
(`pip install --require-hashes --no-deps --only-binary :all:`). A project that needs only the standard
library sets `install-requirements: false`, and the venv stays empty. A ruleset requires, for example,
`Tests / Python 3.12`.

Call it from a job named `Tests` (its checks are `Tests / Python 3.12` and `Tests / Python 3.13`)
with `requirements: requirements/lock.txt requirements/test.txt`, and optionally `apt-packages`
(`ghostscript`, say) and `pythonpath` (`src`, say).

### Security Alerts

[`security-alerts.yml`](.github/workflows/security-alerts.yml) lists the open Dependabot, code
scanning and secret scanning alerts of every repository an account owns, and fails the run when any
alert is open or when any answer can't be trusted. Alerts created in the last 8 days are marked NEW,
and archived repositories are skipped. Call it from a **private** repository: the run summary names
repositories, packages and alert links, and anyone can read a public repository's runs.

It fails closed. Only three answers that mean "this scanner doesn't exist here" are accepted besides a
200: code scanning on a private Free-plan repository, secret scanning there, and a repository CodeQL
has nothing to analyse in. So an expired, revoked or under-scoped token turns the run red, and so does
a token that sees fewer than `min-repos` repositories, or an alert kind no repository answered for. A
run with `control: true` reads closed alerts instead and must fail, which proves the check can.

The caller runs it on a schedule (`cron: "17 6 * * 1"`, Mondays 06:17 UTC) and on
`workflow_dispatch` with a boolean `control` input, and `permissions: {}`:

```yaml
jobs:
  alerts:
    name: Alerts
    uses: agusgonzaleznic/github-reusable-workflows/.github/workflows/security-alerts.yml@3f7c141f6c330d47a854111aabf2b48d827d2cd1  # v1.10.0
    with:
      owner: agusgonzaleznic
      min-repos: 16
      control: ${{ inputs.control || false }}
    secrets:
      alerts-token: ${{ secrets.SECURITY_ALERTS_TOKEN }}
```

`owner` and `min-repos` are required, and so is the secret `alerts-token`, a read-only fine-grained
token (its scopes are in the workflow file). Pass it as a named secret, never `secrets: inherit`.
GitHub sends a failed scheduled run's notification to the account that created the workflow, or to
the last one that changed its cron line, so only the owner's account should edit it.

### GitHub Release

[`github-release.yml`](.github/workflows/github-release.yml) publishes the GitHub release of the
version tag the calling workflow runs on, from the trunk only. It fails on anything but a tag `vX.Y.Z`,
on a tag that no longer names the commit the run started from, and on a tag whose commit isn't on the
default branch. With [Version Tag](#version-tag) the merge makes the tag and starts the release on it,
so nobody pushes a tag by hand. The notes are generated from the pull requests merged since the
previous release. With `artifact-name` set, the files of that artifact are attached with a `SHA256SUMS`
file for them. gh keeps the release a draft until every file is uploaded and deletes the draft when an
upload fails. Its output `url` is the URL of the published release.

The caller's `release.yml` runs `on: push: tags: ['v[0-9]+.[0-9]+.[0-9]+']` and on `workflow_dispatch`,
which is how `version-tag.yml` starts it on the tag it made, with `permissions: {}` and
`concurrency: {group: release, cancel-in-progress: false}`. Its release job:

```yaml
jobs:
  # build: the python-build.yml job of Python Build above

  release:
    name: Release  # its check: "Release / Publish the release"
    needs: build
    uses: agusgonzaleznic/github-reusable-workflows/.github/workflows/github-release.yml@3f7c141f6c330d47a854111aabf2b48d827d2cd1  # v1.10.0
    permissions:
      contents: write  # creates the release and uploads its files, nothing else
    with:
      artifact-name: python-dist  # Optional, default: '' (attaches nothing)
```

To check a download, run `sha256sum -c SHA256SUMS` in the folder that holds the files
(`shasum -a 256 -c SHA256SUMS` on macOS). This repository's own `release.yml` calls the workflow for
every version tag, from the tagged commit.

### Version Tag

[`version-tag.yml`](.github/workflows/version-tag.yml) makes the merge to the default branch the
release, so nobody pushes a tag or publishes a release by hand. On a push to the default branch it
tags the commit with a new version `vX.Y.Z` (the table says when), starts the caller's release
workflow on that tag, waits for it and fails with it. On a pull request it says which version the merge releases
and, with `version` set, fails a change that ships under a version that is already out. The caller
picks one of two ways to choose the version:

| Input | For | On a pull request | On the default branch |
|---|---|---|---|
| `version`, from the code (`__version__`, say) | A package whose files carry their version | A change under `release-paths` needs a version newer than every version tag (`vX.Y.Z` or `X.Y.Z`) | A newer version is tagged and released. A change under `release-paths` with the version unchanged fails the run, because it would never ship |
| `version-from-tags: true` | A repository whose tags are its only version | A notice of the version the merge releases | When anything under `release-paths` changed since the newest tag: the next minor version, or the next major version when a pull request merged since that tag has the label `breaking`; `1.0.0` when there is no tag |

An empty `version` without `version-from-tags` fails, and so do both together, so a typo in the caller
can't fall through to the other way. `release-paths` is required: one path per line, a path ending in
`/` covering everything under it. `release-workflow` (default `release.yml`) names the workflow started
on a new tag, and it needs `workflow_dispatch`. The output `tag` is the tag whose release the run
started, re-ran or waited for; empty when there was none.

Only the run of the default branch's current tip tags anything, so a re-run of an older commit passes
with a notice. A release is finished when a run of the release workflow on its tag succeeded (or, for
a tag that no run ever released, when the tag has a GitHub release). A run with nothing newer to
release finishes the newest tag's release: it waits for a run that is still going, re-runs the failed
jobs of one that failed (the GitHub release may be out while an upload to PyPI failed), and starts the
release when the tag has neither. A newer version is tagged and released at once and replaces an
unfinished release, so the fix for a release that can't succeed can always ship. Versions compare as
numbers (`1.10.0` is newer than `1.9.0`). A tag without the `v`, such as a `1.0.0` made by hand before
the workflow, counts as a version and as released; new tags always get the `v`, and tags of any other
shape (`v2`, `v3.0.0-rc1`) are ignored. A lookup that fails stops the run rather than guess; only the
wait for a release run asks again, up to its deadline.

With the caller's concurrency group from the example below, a run on the default branch waits up to 50
minutes for its release run, and the next merge's run queues behind it. GitHub keeps one queued run per
concurrency group, so a newer merge replaces the queued run (it shows as cancelled) and the newer run
releases both changes. To retry a release, re-run the newest run on the default branch; a re-run of an
older one releases nothing and can replace the queued run of the tip.

The job tags with the caller's `GITHUB_TOKEN`, and GitHub starts no workflow for events that token
causes, except `workflow_dispatch` and `repository_dispatch` (and a few pull request events, which wait
for approval) ([GitHub's documentation](https://docs.github.com/en/actions/concepts/security/github_token)).
So the release workflow lists `workflow_dispatch` among its triggers: it runs with `github.ref` set to
the tag, as for a pushed tag. A tag ruleset that blocks updates and deletions of `v*` fits, but tag
creation must stay open to the workflow.

The caller's workflow runs on `pull_request` and on push to the default branch, with
`contents: read`. Its concurrency group never cancels a run on the default branch, because that run
may be waiting for its release. The jobs, with `package` as the job that outputs the version:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

jobs:
  check-version:
    name: Release  # its check: "Release / Check the version"
    if: github.event_name == 'pull_request'
    needs: package
    uses: agusgonzaleznic/github-reusable-workflows/.github/workflows/version-tag.yml@3f7c141f6c330d47a854111aabf2b48d827d2cd1  # v1.10.0
    permissions:
      contents: read
    with:
      version: ${{ needs.package.outputs.version }}  # or version-from-tags: true
      release-paths: |
        src/
        pyproject.toml

  release:
    name: Release  # its check: "Release / Tag the version"
    if: github.event_name == 'push'
    needs: [tests, package]
    uses: agusgonzaleznic/github-reusable-workflows/.github/workflows/version-tag.yml@3f7c141f6c330d47a854111aabf2b48d827d2cd1  # v1.10.0
    permissions:
      contents: write  # the tag
      actions: write   # starts release.yml on it, watches the run and re-runs its failed jobs
    with:
      version: ${{ needs.package.outputs.version }}
      release-paths: |
        src/
        pyproject.toml
```

The job declares no permissions and runs with what the caller grants: `contents: read` on a pull
request, and `contents: write` (the tag) with `actions: write` (the release run) on the default branch,
plus `pull-requests: read` with `version-from-tags`, for the labels. A ruleset should require
`Release / Check the version`, so a change that ships can't merge under a version that is already out.

## 🚢 How a release happens

This repository releases itself with `version-from-tags: true`, and nobody pushes a tag or publishes a
release by hand. `lint.yml` runs on every pull request and every push to `main`, and its release path is
`.github/workflows/`, so a change to a workflow releases and a change to `README.md` or `tests/` doesn't.

```mermaid
flowchart TD
    pr["Pull request changes<br/>a workflow"] --> check["Release / Check the version<br/>notice: the merge releases vX.Y.0"]
    check --> merge["Merge to main"]
    merge --> gate["Lint and Test version-tag.yml<br/>both pass"]
    gate --> shipped{"A workflow changed<br/>since the newest tag?"}
    shipped -- no --> finish["Finish the newest tag's release<br/>if it is unfinished"]
    shipped -- yes --> breaking{"A merged pull request<br/>has the label breaking?"}
    breaking -- yes --> major["Tag the next major version"]
    breaking -- no --> minor["Tag the next minor version"]
    major --> dispatch["Start release.yml on the tag<br/>with workflow_dispatch"]
    minor --> dispatch
    dispatch --> publish["github-release.yml<br/>publishes the GitHub release"]
    publish --> out["vX.Y.Z is released"]

    classDef default fill:#FFFFFF,stroke:#89909F,color:#1A1D23
    classDef decide fill:#E9EAED,stroke:#555D6D,color:#1A1D23
    classDef outcome fill:#FFFFFF,stroke:#DE3412,stroke-width:2px,color:#1A1D23
    class shipped,breaking decide
    class out outcome
```

`release.yml` publishes the release from the tagged commit, so every release runs the workflow it
ships, and it attaches no files. The tag is made through the API, and the tag ruleset (see
[Security](#-security)) stops anyone moving or deleting it.

## 🔒 Security

Callers pin to commit SHAs of this repository, so its integrity is the root of their trust.

- **Every action is pinned to a full commit SHA**, with the version in a comment, never a mutable tag.
  A tag such as `@v6` can be repointed by anyone who compromises the action's repository, as happened
  with `tj-actions/changed-files` in March 2025
  ([CVE-2025-30066](https://github.com/advisories/GHSA-mrrh-fwg8-r2c3)). `actions-lint.yml` proves
  each pin in this repository on every pull request.
- **Least-privilege `GITHUB_TOKEN`.** Each workflow declares the minimum it needs: `pages: write` and
  `id-token: write` only on the deploy job, `contents: write` only to publish a release, nothing at all
  for `security-alerts.yml`, and `version-tag.yml` runs with what the caller grants. None of them sets a
  `concurrency` group: that belongs to the caller, or the two can deadlock.
- **`persist-credentials: false`** on every checkout, so the token isn't written to `.git/config`, and
  **data inputs go through `env:`** and are quoted in `run:` blocks (`artifact-path`, for example),
  which removes that shell-injection class.
- **Dependabot** (`.github/dependabot.yml`) opens a weekly pull request that bumps the pinned SHAs and
  their version comments together. Each one is reviewed before it merges; nothing auto-merges.
- **Caller responsibilities.** `install-command`, `lint-command`, `build-command`, `prepare-command`,
  `extra-pin-command` and `test-command` are executed as shell commands, which is their purpose, so
  they can't be quoted through `env:`. Don't wire untrusted or event-derived data (a pull request
  title, a branch name, `github.event.*`) into them, or into a calling workflow that forwards them:
  that's command injection inside the reusable workflow. Pass static, trusted strings only.
- **Pin this repository too.** Pinning the actions inside these workflows protects half the chain: a
  caller on `@main` runs a compromise here at once, with its own secrets.

**How this repository is protected, as of 14 November 2026** (read from its rulesets)

- **`main`:** no deletion or force push, linear history, signed commits, a pull request with one
  approval and a code owner review (`.github/CODEOWNERS`), and the checks `Lint / actionlint` and
  `Lint / Verify action pins` on an up-to-date branch.
- **`Protect version tags (v*)`:** no deletion, no update, no force push, and no bypass actor.

Three gaps remain: a repository admin can bypass the `main` ruleset, and neither `Test version-tag.yml`
nor `Release / Check the version` is a required check yet.

## 🩺 Troubleshooting

- **"Jekyll is building my site", or the workflow succeeds and the site is broken.** With **Deploy from
  a branch**, GitHub builds the branch with Jekyll and ignores the artifact. Set **Settings**,
  **Pages**, **Build and deployment**, **Source** to **GitHub Actions** and re-run.
- **"Deadlock was detected for concurrency group 'pages'".** Both the calling workflow and the reusable
  one define the same concurrency group. Define `concurrency` in the caller only.
- **The Pages artifact is wrong, or 404 on deployment.** `index.html` must sit at the root of the
  artifact, not in a subdirectory, so the artifact holds `index.html` and `assets/`, not `dist/index.html`.
  The build job's "Verify build output" step lists exactly what will be uploaded. Write
  `artifact-path: 'dist'` without `./`, and check that the build command writes into that directory.
- **Assets don't load.** Set `base` in `vite.config.ts`: `'/'` for a user or organisation site
  (`username.github.io`), `'/repo/'` for a project site (`username.github.io/repo`).

## 🤝 Contributing

I review every change myself (`.github/CODEOWNERS`). Open a pull request from a branch. When you add a
reusable workflow:

1. Use `workflow_call` as the trigger.
2. Give every input a sensible default, unless it can't have one.
3. Give every input and output a `description` in the workflow file, add the workflow to the table
   in [Quick start](#-quick-start), and pin the example to the release that ships it once it is out.
4. Never rename a job. Its name is half of every caller's required checks (`<calling job> / <job>`).
5. Leave `concurrency` to the caller.
6. Never push a tag or publish a release by hand. The merge of a pull request that changes a workflow
   releases the next minor version, and the label `breaking` on it makes the next major version (see
   [How a release happens](#-how-a-release-happens)).

The scenarios in `tests/version-tag/test_version_tag.py` run the script through the cases of
[Version Tag](#version-tag) against throwaway git repositories and a stand-in for `gh`.

## 💛 Support this project

It's free to read and to call, and there's nothing to upsell. Three things help, in ascending order of
effort:

- **Star the repo.** It's how the next person who needs the same steps finds them.
- **Open an issue** at [github.com/agusgonzaleznic/github-reusable-workflows/issues](https://github.com/agusgonzaleznic/github-reusable-workflows/issues/new)
  when an input, a default or a permission here doesn't match what the workflow does. A link to the
  line is the most useful report.
- **Drop a coffee on Ko-fi, or sponsor on GitHub.** Ko-fi is a one-off, and GitHub Sponsors can be
  monthly or one-time, with a custom amount. Keeping pinned actions current is the slow, recurring
  part of a project like this.

<div align="center">

[![Ko-fi](https://img.shields.io/badge/Ko--fi-one--off-555D6D?style=for-the-badge&labelColor=1A1D23&logo=kofi&logoColor=FAFAFA)](https://ko-fi.com/agusgonzaleznic)
[![GitHub Sponsors](https://img.shields.io/badge/GitHub_Sponsors-monthly-555D6D?style=for-the-badge&labelColor=1A1D23&logo=githubsponsors&logoColor=FAFAFA)](https://github.com/sponsors/agusgonzaleznic)
<br>
[![website](https://img.shields.io/badge/website-agusgonzaleznic.com-555D6D?style=for-the-badge&labelColor=1A1D23)](https://agusgonzaleznic.com)
[![GitHub](https://img.shields.io/badge/GitHub-agusgonzaleznic-555D6D?style=for-the-badge&labelColor=1A1D23&logo=github&logoColor=FAFAFA)](https://github.com/agusgonzaleznic)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-agusgonzaleznic-555D6D?style=for-the-badge&labelColor=1A1D23)](https://www.linkedin.com/in/agusgonzaleznic)

<sub>Built in Berlin by <b>Agustin Gonzalez Nicolini</b>. I work on engineering leadership and write
about it at <a href="https://agusgonzaleznic.com">agusgonzaleznic.com</a>.</sub>

</div>

---

<a id="licence"></a>

## ⚖️ Licence

This repository has no licence file yet, and GitHub reports none as of 14 November 2026. Until I add
one, no licence is granted for reuse beyond GitHub's own terms for public repositories.
