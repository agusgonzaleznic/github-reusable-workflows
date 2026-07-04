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
      node-version: '20'              # Optional, default: '20'
      install-command: 'npm ci'       # Optional, default: 'npm ci'
      lint-command: 'npm run lint'    # Optional, default: 'npm run lint'
      build-command: 'npm run build'  # Optional, default: 'npm run build'
      artifact-path: 'dist'           # Optional, default: 'dist'
      run-lint: true                  # Optional, default: true
```

**Inputs:**

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `node-version` | Node.js version to use | No | `'20'` |
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
      node-version: '20'              # Optional, default: '20'
      install-command: 'npm ci'       # Optional, default: 'npm ci'
      lint-command: 'npm run lint'    # Optional, default: 'npm run lint'
      build-command: 'npm run build'  # Optional, default: 'npm run build'
      artifact-path: 'dist'           # Optional, default: 'dist'
      verify-build-output: true       # Optional, default: true
```

**Inputs:**

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `node-version` | Node.js version to use | No | `'20'` |
| `install-command` | Command to install dependencies | No | `'npm ci'` |
| `lint-command` | Command to lint the project | No | `'npm run lint'` |
| `build-command` | Command to build the project | No | `'npm run build'` |
| `artifact-path` | Path to the build output directory | No | `'dist'` |
| `verify-build-output` | Whether to verify build output exists | No | `true` |

---

## General Notes

- All workflows use npm by default, but can be customized via inputs
- Workflows support Node.js caching for faster builds
- Both workflows are framework-agnostic and can work with any Vite-based project
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

The `install-command`, `lint-command`, and `build-command` inputs are **executed as shell commands** (`run: ${{ inputs.*-command }}`) — that is their purpose. They cannot be `env:`-quoted without breaking that contract. **Do not wire untrusted or event-derived data** (e.g. a PR title, branch name, or `github.event.*`) into these inputs, or into the calling workflow that forwards them — doing so is command injection inside the reusable workflow. Pass only static, trusted command strings.

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
