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
hash-locked requirements (`pip install --require-hashes --no-deps --only-binary :all:`).

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
| `apt-packages` | Space-separated apt packages the tests need | No | `''` |
| `pythonpath` | `PYTHONPATH` for the test command | No | `''` |
| `test-command` | Command that runs the tests | No | `'.venv/bin/python -m pytest -q'` |
| `runs-on` | Runner label | No | `'ubuntu-latest'` |

**Required checks:** GitHub names a check from a reusable workflow `<calling job name> / <job name>`,
so a ruleset requires, for example, `Tests / Python 3.12`. The job names here are part of every
caller's contract.

---

## General Notes

- The Vite workflows use npm by default, but can be customized via inputs
- The Vite workflows support Node.js caching for faster builds
- Both Vite workflows are framework-agnostic and can work with any Vite-based project
- **Security**: pin the reusable workflow to a full commit SHA, never `@main` (see [Supply chain hardening](#supply-chain-hardening))
- **Important**: Use relative paths without `./` prefix for `artifact-path` (e.g., `'dist'` not `'./dist'`) to ensure proper artifact upload with GitHub Actions
- **Reusable Workflow Pattern**: The reusable workflows do NOT define their own `concurrency` groups — those must be defined in the calling workflow to avoid deadlock conflicts. They DO declare minimal least-privilege `permissions` per job; the caller must grant at least those scopes.

## Supply chain hardening

These workflows follow GitHub Actions supply-chain best practices:

- **All actions are pinned to full commit SHAs** (with the version in a comment), not mutable tags. A mutable tag such as `@v6` can be silently repointed by anyone who compromises the action's repository — as happened in the `tj-actions/changed-files` incident (March 2025). A commit SHA is immutable.
- **Least-privilege `GITHUB_TOKEN`**: each job declares the minimum `permissions` it needs (`contents: read` to build; `pages: write` + `id-token: write` only on the deploy job).
- **`persist-credentials: false`** on checkout so the token is not written to `.git/config`, where a malicious dependency in a later step could read it.
- **Data inputs are passed via `env:` and quoted**: values used as *data* in `run:` blocks (e.g. `artifact-path`) go through `env:` rather than being interpolated directly, removing that shell-injection class.
- **Dependabot** (`.github/dependabot.yml`) opens weekly PRs to bump the pinned SHAs when upstream ships patches.

### Caller responsibilities

The `install-command`, `lint-command`, and `build-command` inputs are **executed as shell commands** (`run: ${{ inputs.*-command }}`) — that is their purpose. They cannot be `env:`-quoted without breaking that contract. **Do not wire untrusted or event-derived data** (e.g. a PR title, branch name, or `github.event.*`) into these inputs, or into the calling workflow that forwards them — doing so is command injection inside the reusable workflow. Pass only static, trusted command strings. The same holds for `prepare-command`,
`extra-pin-command` (actions-lint.yml) and `test-command` (python-tests.yml).

The `build-env-vars` secret is appended verbatim to `$GITHUB_ENV` and is available to every later step (including dependency build code). GitHub masks the exact full secret string in logs, but **not** each individual `KEY=value` line within a multiline secret — avoid `echo`-ing those values in your build.

### Maintainer controls (root of trust)

Consumers pin to commit SHAs of *this* repository, so this repo's integrity is the root of their trust. Pair SHA pinning with:

- **Branch protection** on `main`: require a PR, a CODEOWNER approval (see `.github/CODEOWNERS`), and passing status checks before merge.
- **Tag protection** (or immutable releases) so a published version tag can't be silently repointed.
- Reviewing Dependabot PRs before merge rather than auto-merging.

### Consumers must pin this repo too

Pinning the actions *inside* these workflows only protects half the chain. Any workflow that *calls* these reusable workflows must itself pin to a **full commit SHA** of this repository — referencing `@main` means a compromise of this repo would immediately execute in the caller with the caller's secrets.

```yaml
# ❌ Not safe — tracks a mutable branch
uses: agusgonzaleznic/github-reusable-workflows/.github/workflows/vite-ci.yml@main

# ✅ Safe — immutable commit, human-readable version in the comment
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
