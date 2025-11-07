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

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  build-and-deploy:
    uses: agusgonzaleznic/github-reusable-workflows/.github/workflows/vite-build-deploy.yml@main
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

1. Go to Repository → Settings → Pages
2. Set Source to "GitHub Actions"
3. Save changes

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
    uses: agusgonzaleznic/github-reusable-workflows/.github/workflows/vite-ci.yml@main
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
- Use `@main` branch for stable versions, or pin to a specific commit SHA for reproducibility
- **Important**: Use relative paths without `./` prefix for `artifact-path` (e.g., `'dist'` not `'./dist'`) to ensure proper artifact upload with GitHub Actions

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
