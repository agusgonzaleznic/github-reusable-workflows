# github-reusable-workflows

Reusable GitHub Actions workflows for common CI/CD tasks.

## Available Workflows

### 1. Vite Build and Deploy (`vite-build-deploy.yml`)

Builds a Vite application and deploys it to GitHub Pages.

**Usage:**

```yaml
name: Deploy to GitHub Pages

on:
  push:
    branches:
      - main
  workflow_dispatch:

# IMPORTANT: Define permissions and concurrency at the workflow level
# The reusable workflow inherits these settings
permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  build-and-deploy:
    # SECURITY: pin to a full commit SHA, not @main (see "Supply chain hardening" below).
    # Resolve the SHA for a release with:
    #   gh api repos/agusgonzaleznic/github-reusable-workflows/commits/v1.0.0 --jq .sha
    uses: agusgonzaleznic/github-reusable-workflows/.github/workflows/vite-build-deploy.yml@<full-commit-sha>  # v1.0.0
    # Pass permissions to the job
    permissions:
      contents: read
      pages: write
      id-token: write
    with:
      node-version: '22'              # Optional, default: '22'
      install-command: 'npm ci'       # Optional, default: 'npm ci'
      lint-command: 'npm run lint'    # Optional, default: 'npm run lint'
      build-command: 'npm run build'  # Optional, default: 'npm run build'
      artifact-path: 'dist'           # Optional, default: 'dist'
      run-lint: true                  # Optional, default: true
```

**Inputs:**

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `node-version` | Node.js version to use | No | `'22'` |
| `install-command` | Command to install dependencies | No | `'npm ci'` |
| `lint-command` | Command to lint the project | No | `'npm run lint'` |
| `build-command` | Command to build the project | No | `'npm run build'` |
| `artifact-path` | Path to the build output directory (relative path without `./`) | No | `'dist'` |
| `run-lint` | Whether to run linting | No | `true` |

**Required Repository Settings:**

⚠️ **CRITICAL**: Your repository MUST be configured to use GitHub Actions for deployment:

1. Go to **Repository** → **Settings** → **Pages**
2. Under **"Build and deployment"** section:
   - **Source** dropdown: Select **"GitHub Actions"**
   - Do NOT use "Deploy from a branch" (this will use Jekyll and ignore your workflow)
3. Click **Save**

**Why this matters**: If set to "Deploy from a branch", GitHub will try to build your site with Jekyll from the branch, completely ignoring your pre-built artifact. Your workflow will appear to succeed, but the deployed site will be incorrect or broken.

---

### 2. Vite CI (`vite-ci.yml`)

Runs linting and build checks for pull requests on Vite applications.

**Usage:**

```yaml
name: CI

on:
  pull_request:
    branches:
      - main
  workflow_dispatch:

jobs:
  ci:
    # SECURITY: pin to a full commit SHA, not @main (see "Supply chain hardening" below).
    # Resolve the SHA for a release with:
    #   gh api repos/agusgonzaleznic/github-reusable-workflows/commits/v1.0.0 --jq .sha
    uses: agusgonzaleznic/github-reusable-workflows/.github/workflows/vite-ci.yml@<full-commit-sha>  # v1.0.0
    with:
      node-version: '22'              # Optional, default: '22'
      install-command: 'npm ci'       # Optional, default: 'npm ci'
      lint-command: 'npm run lint'    # Optional, default: 'npm run lint'
      build-command: 'npm run build'  # Optional, default: 'npm run build'
      artifact-path: 'dist'           # Optional, default: 'dist'
      verify-build-output: true       # Optional, default: true
```

**Inputs:**

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `node-version` | Node.js version to use | No | `'22'` |
| `install-command` | Command to install dependencies | No | `'npm ci'` |
| `lint-command` | Command to lint the project | No | `'npm run lint'` |
| `build-command` | Command to build the project | No | `'npm run build'` |
| `artifact-path` | Path to the build output directory | No | `'dist'` |
| `verify-build-output` | Whether to verify build output exists | No | `true` |

---

### 3. Python Build (`python-build.yml`)

Builds the sdist and wheel of a Python project with uv and uploads them as one artifact, ready for a
publish job in the calling workflow. On a tag (a release) it fails when the built version differs
from the tag (`v1.2.3` or `1.2.3`).

The upload to PyPI cannot live in this repository: PyPI's Trusted Publishing only trusts a job
defined in the workflow file registered on PyPI, and a job from another repository's reusable
workflow never matches it ([pypi/warehouse#11096](https://github.com/pypi/warehouse/issues/11096)).
So the caller keeps one short publish job, and the workflow needs no PyPI token.

**Usage** (`.github/workflows/publish.yml` in the package's repository):

```yaml
name: Publish

on:
  release:
    types: [published]

permissions: {}

concurrency:
  group: publish
  cancel-in-progress: false

jobs:
  build:
    uses: agusgonzaleznic/github-reusable-workflows/.github/workflows/python-build.yml@<full-commit-sha>  # v1.4.0
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
      - uses: actions/download-artifact@<full-commit-sha>  # v8.0.2
        with:
          name: python-dist
          path: dist/
      - uses: pypa/gh-action-pypi-publish@<full-commit-sha>  # v1.14.3
```

**Inputs:**

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `python-version` | Python version uv builds with | No | `'3.13'` |
| `uv-version` | uv version to install (setup-uv verifies its checksum) | No | `'0.13.4'` |
| `build-constraints` | Hash-locked constraints file for the build backend, relative to the repo root | No | `''` |
| `artifact-name` | Name of the artifact that holds `dist/` | No | `'python-dist'` |

**Outputs:** `version`, the version that was built.

**On PyPI:** the project's Publishing settings need a GitHub publisher with the owner, the
repository, the caller's workflow file name (`publish.yml` above, never `python-build.yml`) and the
environment (`pypi`). On GitHub, an environment of that name limited to `v*` tags keeps any other
ref from publishing.

**Lock the build backend:** `uv build` fetches the project's build backend (for example hatchling)
from PyPI at build time. A constraints file compiled with hashes pins it. `build.in` lists the
project's `[build-system] requires`; compile it for the oldest Python the project supports, and
leave out releases younger than a week, as the Dependabot cooldown does for actions:

```bash
uv pip compile requirements/build.in --universal --generate-hashes --python-version 3.12 \
  --exclude-newer <the date a week ago> -o requirements/build.txt
```

The `uv-version` and `python-version` defaults change only by hand here; Dependabot does not see them.

---

### 4. Lint Workflows and Action Pins (`actions-lint.yml`)

Lints the caller's workflows with actionlint 1.7.12 (checksum-verified) and proves every action pin:
a full commit SHA, a `# vX.Y.Z` comment, and that tag resolving to exactly that commit upstream. A
pattern or path that matches nothing fails, so a typo cannot pass. This repository's own `lint.yml`
calls it too.

**Usage:**

```yaml
name: Lint

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    name: Lint  # its checks: "Lint / actionlint", "Lint / Verify action pins"
    uses: agusgonzaleznic/github-reusable-workflows/.github/workflows/actions-lint.yml@<full-commit-sha>  # v1.5.0
    with:
      pin-paths: .github/workflows action.yml  # Optional, default: .github/workflows
```

**Inputs:**

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `actionlint-files` | Space-separated files or globs for actionlint; each must match a file | No | `'.github/workflows/*.yml'` |
| `pin-paths` | Space-separated files or folders whose pins are verified; each must exist | No | `'.github/workflows'` |
| `prepare-command` | Shell command run before actionlint, for example rendering workflow templates | No | `''` |
| `extra-pin-command` | Shell command run after the pin check, with `GH_TOKEN` set | No | `''` |
| `runs-on` | Runner label | No | `'ubuntu-latest'` |

---

### 5. Python Tests (`python-tests.yml`)

Runs a Python project's tests once per Python version, in a fresh venv that installs only
hash-locked requirements (`pip install --require-hashes --no-deps --only-binary :all:`). A project
that needs only the standard library sets `install-requirements: false`, and the venv stays empty.

**Usage:**

```yaml
jobs:
  tests:
    name: Tests  # its checks: "Tests / Python 3.12", "Tests / Python 3.13"
    uses: agusgonzaleznic/github-reusable-workflows/.github/workflows/python-tests.yml@<full-commit-sha>  # v1.5.0
    with:
      requirements: requirements/lock.txt requirements/test.txt
      apt-packages: ghostscript  # Optional
      pythonpath: src            # Optional
```

**Inputs:**

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `python-versions` | JSON list of Python versions, one job each | No | `'["3.12", "3.13"]'` |
| `requirements` | Space-separated hash-locked requirement files | No | `'requirements.txt'` |
| `install-requirements` | `false` installs nothing and ignores `requirements`, for a project that needs only the standard library | No | `true` |
| `apt-packages` | Space-separated apt packages the tests need | No | `''` |
| `pythonpath` | `PYTHONPATH` for the test command | No | `''` |
| `test-command` | Command that runs the tests | No | `'.venv/bin/python -m pytest -q'` |
| `runs-on` | Runner label | No | `'ubuntu-latest'` |

**Required checks:** GitHub names a check from a reusable workflow `<calling job name> / <job name>`,
so a ruleset requires, for example, `Tests / Python 3.12`. The job names here are part of every
caller's contract.

---

### 6. Security Alerts (`security-alerts.yml`)

Lists the open Dependabot, code scanning and secret scanning alerts of every repository an account
owns, and fails the run when any alert is open or when any answer cannot be trusted. Alerts created
in the last 8 days are marked NEW. Call it from a **private** repository: the run summary names
repositories, packages and alert links, and anyone can read a public repository's runs.

It fails closed: only the three answers that mean "this scanner does not exist here" (code scanning
on a private Free-plan repository, secret scanning there, and a repository CodeQL has nothing to
analyse in) are accepted besides a 200, so an expired, revoked or under-scoped token turns the run
red instead of reading as no alerts. So does a token that sees fewer than `min-repos` repositories,
and an alert kind no repository answered for. A run with `control: true` reads closed alerts
instead and must fail, which proves the check can.

**Usage:**

```yaml
name: Security alerts

on:
  schedule:
    - cron: "17 6 * * 1"  # Mondays 06:17 UTC
  workflow_dispatch:
    inputs:
      control:
        description: 'Read closed alerts instead of open ones; the run must fail'
        type: boolean
        default: false

permissions: {}

jobs:
  alerts:
    name: Alerts
    uses: agusgonzaleznic/github-reusable-workflows/.github/workflows/security-alerts.yml@<full-commit-sha>  # v1.6.0
    with:
      owner: agusgonzaleznic
      min-repos: 16
      control: ${{ inputs.control || false }}
    secrets:
      alerts-token: ${{ secrets.SECURITY_ALERTS_TOKEN }}
```

**Inputs and secret:**

| Name | Description | Required | Default |
|------|-------------|----------|---------|
| `owner` | Account whose repositories are checked | Yes | |
| `min-repos` | Fewest repositories the token must see; raise it when one is created | Yes | |
| `control` | Read closed alerts instead of open ones; the run must fail | No | `false` |
| `runs-on` | Runner label | No | `'ubuntu-latest'` |
| `alerts-token` (secret) | Fine-grained token, read-only: Dependabot alerts, Code scanning alerts, Secret scanning alerts and Metadata, on all repositories | Yes | |

Pass the token as a named secret, never `secrets: inherit`. GitHub sends a failed scheduled run's
notification to the account that created the workflow, or to the last one that changed its cron
line, so only the owner's account should edit it.

---

### 7. GitHub Release (`github-release.yml`)

Publishes the GitHub release of the version tag the calling workflow runs on, from the trunk
only: it fails on anything but a tag `vX.Y.Z`, on a tag that no longer names the commit the run
started from, and on a tag whose commit is not on the default branch. With section 8 the merge makes
the tag and starts the release on it, so nobody pushes a tag by hand. The notes are generated from
the pull requests merged since the previous release. With `artifact-name` set, the files of that
artifact are attached with a `SHA256SUMS` file for them; gh keeps the release a draft until every
file is uploaded and deletes the draft when an upload fails.

**Usage** (`.github/workflows/release.yml`, with the build from section 3):

```yaml
name: Release

on:
  push:
    tags:
      - 'v[0-9]+.[0-9]+.[0-9]+'
  workflow_dispatch:  # how version-tag.yml (section 8) starts it on the tag it made

permissions: {}

concurrency:
  group: release
  cancel-in-progress: false

jobs:
  build:
    name: Package build
    uses: agusgonzaleznic/github-reusable-workflows/.github/workflows/python-build.yml@<full-commit-sha>  # v1.7.0
    permissions:
      contents: read

  release:
    name: Release  # its check: "Release / Publish the release"
    needs: build
    uses: agusgonzaleznic/github-reusable-workflows/.github/workflows/github-release.yml@<full-commit-sha>  # v1.8.0
    permissions:
      contents: write  # creates the release and uploads its files, nothing else
    with:
      artifact-name: python-dist  # Optional, default: '' (attaches nothing)
```

**Inputs:**

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `artifact-name` | Artifact whose files are attached, with a `SHA256SUMS` file; empty attaches nothing | No | `''` |
| `runs-on` | Runner label | No | `'ubuntu-latest'` |

**Outputs:** `url`, the URL of the published release.

**Check a download:** in the folder that holds the downloaded files, `sha256sum -c SHA256SUMS`
(`shasum -a 256 -c SHA256SUMS` on macOS).

This repository's own `release.yml` calls it for every version tag, from the tagged commit, and
`lint.yml` makes the tags (section 8).

---

### 8. Version Tag (`version-tag.yml`)

Makes the merge to the default branch the release, so nobody pushes a tag or publishes a release by
hand. On a push to the default branch it tags the commit `vX.Y.Z` when something that ships changed,
starts the caller's release workflow on that tag, waits for it and fails with it. On a pull request
it says which version the merge releases and, with `version` set, fails a change that ships under a
version that is already out.

The caller picks one of two ways to choose the version:

| Input | For | On a pull request | On the default branch |
|-------|-----|-------------------|-----------------------|
| `version`, from the code (`__version__`, say) | A package whose files carry their version | A change under `release-paths` needs a version newer than every `vX.Y.Z` tag | A newer version is tagged and released. A change under `release-paths` with the version unchanged fails the run, because it would never ship |
| `version-from-tags: true` | A repository whose tags are its only version | A notice of the version the merge releases | When anything under `release-paths` changed since the newest tag: the next minor version, or the next major version when a pull request merged since that tag has the label `breaking`; `1.0.0` when there is no tag |

An empty `version` without `version-from-tags` fails, and so do both together, so a typo in the
caller cannot fall through to the other way.

Only the run of the default branch's current tip tags anything, so a re-run of an older commit
passes with a notice. A release is finished when a run of the release workflow on its tag succeeded
(or, for a tag that no run ever released, when the tag has a GitHub release). A run there with
nothing newer to release finishes the newest tag's release: it waits for a release run that is still
going, re-runs the failed jobs of one that failed (the GitHub release may be out while an upload to
PyPI failed), and starts the release when the tag has neither a run nor a GitHub release (a run
stopped between the tag and the release). A newer version is tagged and released at once and
replaces an unfinished release, so the fix for a release that cannot succeed can always ship.
Versions compare as numbers (`1.10.0` is newer than `1.9.0`), and tags of any other shape, such as
`v2` or `v3.0.0-rc1`, are ignored. A lookup that fails stops the run rather than guess.

A run on the default branch waits up to 50 minutes for its release run, and the next merge's run
queues behind it, because runs there never cancel each other. GitHub keeps one queued run per
concurrency group: a newer merge replaces the queued run, which then shows as cancelled, and the
newer run releases both changes. To retry a release, re-run the newest run on the default branch.
A re-run of an older one releases nothing and can replace the queued run of the tip.

The job tags with the caller's `GITHUB_TOKEN`, and GitHub starts no workflow for events that token
causes except `workflow_dispatch`. So the release workflow lists `workflow_dispatch` among its
triggers (see section 7): it runs with `github.ref` set to the tag, as for a pushed tag. A tag
ruleset that blocks updates and deletions of `v*` fits; tag creation must stay open to the workflow.

**Usage** (in the CI workflow, with the build from section 3):

```yaml
on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

# Runs on main never cancel a running one: it may be waiting for its release.
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

jobs:
  # tests and package jobs here; package has the output version

  check-version:
    name: Release  # its check: "Release / Check the version"
    if: github.event_name == 'pull_request'
    needs: package
    uses: agusgonzaleznic/github-reusable-workflows/.github/workflows/version-tag.yml@<full-commit-sha>  # v1.9.0
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
    uses: agusgonzaleznic/github-reusable-workflows/.github/workflows/version-tag.yml@<full-commit-sha>  # v1.9.0
    permissions:
      contents: write  # the tag
      actions: write   # starts release.yml on it, watches the run and re-runs its failed jobs
    with:
      version: ${{ needs.package.outputs.version }}
      release-paths: |
        src/
        pyproject.toml
```

With `version-from-tags: true`, the `release` job also needs `pull-requests: read`, for the labels.

**Inputs:**

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `version` | The version the commit ships, `X.Y.Z`; required unless `version-from-tags` is true | No | `''` |
| `version-from-tags` | Take the next version from the tags instead: the minor version up, the major version with the label `breaking` | No | `false` |
| `release-paths` | Paths that ship, one per line: a path ending in `/` covers everything under it, any other path one file | Yes | |
| `release-workflow` | File name of the workflow, in `.github/workflows`, started on a new tag; it needs `workflow_dispatch` | No | `'release.yml'` |
| `runs-on` | Runner label | No | `'ubuntu-latest'` |

**Outputs:** `tag`, the tag whose release the run started, re-ran or waited for; empty when there
was none.

**Permissions:** the job declares none and runs with what the caller grants, because a pull request
and the default branch need different ones: `contents: read` on a pull request, and `contents: write`
(the tag) with `actions: write` (the release run) on the default branch, plus `pull-requests: read`
with `version-from-tags`.

**Required checks:** require `Release / Check the version`, so a change that ships cannot merge under
a version that is already out.

This repository releases itself this way, with `version-from-tags: true`: `lint.yml` tags the next
minor version when a merge changes a workflow, the label `breaking` makes it a major version, and
`release.yml` publishes it.
`tests/version-tag/test_version_tag.py` runs the script through every case above against throwaway
git repositories and a stand-in for `gh`, on every pull request and before each release.

---

## General Notes

- The Vite workflows use npm by default, but can be customized via inputs
- The Vite workflows support Node.js caching for faster builds
- Both Vite workflows are framework-agnostic and can work with any Vite-based project
- **Security**: pin the reusable workflow to a full commit SHA, never `@main` (see [Supply chain hardening](#supply-chain-hardening))
- **Important**: Use relative paths without `./` prefix for `artifact-path` (e.g., `'dist'` not `'./dist'`) to ensure proper artifact upload with GitHub Actions
- **Reusable Workflow Pattern**: The reusable workflows do NOT define their own `concurrency` groups; those must be defined in the calling workflow to avoid deadlock conflicts. They DO declare minimal least-privilege `permissions` per job, and the caller must grant at least those scopes. The exception is `version-tag.yml`, which declares none and runs with what the caller grants (see section 8).

## Supply chain hardening

These workflows follow GitHub Actions supply-chain best practices:

- **All actions are pinned to full commit SHAs** (with the version in a comment), not mutable tags. A mutable tag such as `@v6` can be silently repointed by anyone who compromises the action's repository, as happened in the `tj-actions/changed-files` incident (March 2025). A commit SHA is immutable.
- **Least-privilege `GITHUB_TOKEN`**: each job declares the minimum `permissions` it needs (`contents: read` to build; `pages: write` + `id-token: write` only on the deploy job).
- **`persist-credentials: false`** on checkout so the token is not written to `.git/config`, where a malicious dependency in a later step could read it.
- **Data inputs are passed via `env:` and quoted**: values used as *data* in `run:` blocks (e.g. `artifact-path`) go through `env:` rather than being interpolated directly, removing that shell-injection class.
- **Dependabot** (`.github/dependabot.yml`) opens weekly PRs to bump the pinned SHAs when upstream ships patches.

### Caller responsibilities

The `install-command`, `lint-command`, and `build-command` inputs are **executed as shell commands** (`run: ${{ inputs.*-command }}`); that is their purpose. They cannot be `env:`-quoted without breaking that contract. **Do not wire untrusted or event-derived data** (e.g. a PR title, branch name, or `github.event.*`) into these inputs, or into the calling workflow that forwards them. Doing so is command injection inside the reusable workflow. Pass only static, trusted command strings. The same holds for `prepare-command`,
`extra-pin-command` (actions-lint.yml) and `test-command` (python-tests.yml).

The `build-env-vars` secret is appended verbatim to `$GITHUB_ENV` and is available to every later step (including dependency build code). GitHub masks the exact full secret string in logs, but **not** each individual `KEY=value` line within a multiline secret, so avoid `echo`-ing those values in your build.

### Maintainer controls (root of trust)

Consumers pin to commit SHAs of *this* repository, so this repo's integrity is the root of their trust. Pair SHA pinning with:

- **Branch protection** on `main`: require a PR, a CODEOWNER approval (see `.github/CODEOWNERS`), and passing status checks before merge.
- **Tag protection** (or immutable releases) so a published version tag can't be silently repointed. Only the merge makes a tag here (section 8), never a person.
- Reviewing Dependabot PRs before merge rather than auto-merging.

### Consumers must pin this repo too

Pinning the actions *inside* these workflows only protects half the chain. Any workflow that *calls* these reusable workflows must itself pin to a **full commit SHA** of this repository. Referencing `@main` means a compromise of this repo would immediately execute in the caller with the caller's secrets.

```yaml
# ❌ Not safe: tracks a mutable branch
uses: agusgonzaleznic/github-reusable-workflows/.github/workflows/vite-ci.yml@main

# ✅ Safe: immutable commit, human-readable version in the comment
uses: agusgonzaleznic/github-reusable-workflows/.github/workflows/vite-ci.yml@<full-commit-sha>  # v1.0.0
```

Resolve the SHA for a release tag with:

```bash
gh api repos/agusgonzaleznic/github-reusable-workflows/commits/v1.0.0 --jq .sha
```

## Troubleshooting

### Artifact Upload Issues

If the GitHub Pages artifact isn't uploading correctly:

1. **Check the workflow logs** - The build verification step shows exactly what will be uploaded
2. **Verify artifact structure** - The artifact should contain your site files at the root, not in a subdirectory
3. **Expected artifact contents**:
   ```
   index.html          (at root)
   assets/
   favicon.ico
   ...other files...
   ```
4. **NOT** this structure:
   ```
   dist/              (don't want this!)
     index.html
     assets/
   ```

5. **Path format**: Use `artifact-path: 'dist'` without `./` prefix
6. **Verify build output**: Check that `npm run build` creates files in the expected directory
7. **Review workflow logs**: Look for the "Build Output Verification" section

### Common Issues

- **"Jekyll is building my site" or "Workflow succeeds but site is broken"**
  - **Cause**: Repository is set to "Deploy from a branch" instead of "GitHub Actions"
  - **Solution**:
    1. Go to Repository → Settings → Pages
    2. Change Source from "Deploy from a branch" to **"GitHub Actions"**
    3. Re-run the workflow
  - **Why**: When set to "Deploy from a branch", GitHub ignores your artifact and tries to build with Jekyll from the branch
  - **Verification**: Check your workflow logs - if you see Jekyll-related output, your settings are wrong

- **"Deadlock was detected for concurrency group 'pages'"**
  - This happens when both the calling workflow and reusable workflow define the same concurrency group
  - **Solution**: Only define `concurrency` in the calling workflow, not in the reusable workflow
  - The reusable workflow now correctly inherits concurrency settings from the caller

- **404 on deployment**: Check that `index.html` is at the root of the artifact, not in a subdirectory

- **Assets not loading**: Verify your `vite.config.ts` has the correct `base` path
  - User/org pages (`username.github.io`): `base: '/'`
  - Project pages (`username.github.io/repo`): `base: '/repo/'`

## Contributing

When adding new reusable workflows, ensure:
1. Use `workflow_call` as the trigger
2. Provide sensible default values for all inputs
3. Document all inputs and outputs
4. Include usage examples in this README
5. Never rename a job: its name is half of every caller's required checks (`<calling job> / <job>`)
6. Leave `concurrency` to the caller; a reusable workflow that sets it can deadlock (see Troubleshooting)
7. Never push a tag or publish a release by hand: the merge of a pull request that changes a workflow releases the next minor version, and the label `breaking` on it makes the next major version (section 8)
