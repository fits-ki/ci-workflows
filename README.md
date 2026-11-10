# CI Workflows

Generic, secret-free CI building blocks for the fits-ki repository fleet.

Application code, private repository inventories and credentials belong in
their own repositories, never here.

Development targets `develop`; releases to `main` require separate approval.
Consumers pin reviewed workflow commits. Creating this repository does not
enable automerge or change any application's deployment policy.

## Reusable workflows

Callers must pin the exact 40-character commit SHA of a reviewed commit:

```yaml
uses: fits-ki/ci-workflows/.github/workflows/<name>.yml@<full-40-char-sha>
```

### `.github/workflows/node-npm.yml` - Node/npm checks

Runs a package.json verification script on `runner` (default
`ubuntu-latest`) with a 15-minute timeout.

Inputs (all strings, all optional):

| Input | Default | Meaning |
|---|---|---|
| `node-version` | `"24"` | Node version for `actions/setup-node` |
| `php-version` | `""` | Optional PHP version via `shivammathur/setup-php`; empty skips PHP |
| `check-script` | `"verify"` | package.json script executed after install |

Behavior: checkout of the tested revision with `persist-credentials: false`,
`npm ci --no-audit --no-fund`, then the script name is passed through the
`CHECK_SCRIPT` environment variable - never interpolated into the shell -
and validated against `[a-zA-Z0-9:_-]` (no empty names, no leading dash)
before `npm run`. All actions are SHA-pinned. `contents: read` only; no
secrets are requested, inherited or used, and nothing is deployed.

### `.github/workflows/merge-gate.yml` - Merge gate

Aggregates job results into a single required check. The caller job must
declare `if: always()` so the gate also runs when dependencies fail.

Inputs (all strings):

| Input | Default | Meaning |
|---|---|---|
| `results-json` | required | `toJSON(needs)`: object of job ID to `{result, ...}` |
| `required-jobs-json` | required | Nonempty unique JSON array of job IDs that must be `success` |
| `conditional-jobs-json` | `"{}"` | Object of job ID to literal `"true"`/`"false"`; `"true"` requires `success`, `"false"` requires `skipped` |

Every expected job ID must appear exactly in `results-json`; required and
conditional sets must be disjoint; IDs must match `^[A-Za-z_][A-Za-z0-9_-]*$`.
Missing, extra, duplicate, null, malformed or unexpected results
(`failure`, `cancelled`, `skipped` where success required, unknown
results) fail the gate. No checkout, no external actions,
`contents: read` only.

Example caller:

```yaml
jobs:
  checks:
    ... # existing application checks
  gate:
    if: always()
    needs: [checks]
    uses: fits-ki/ci-workflows/.github/workflows/merge-gate.yml@<sha>
    with:
      results-json: ${{ toJSON(needs) }}
      required-jobs-json: '["checks"]'
```

### Runner selection

`quick-check.yml`, `full-check.yml`, `merge-gate.yml`, `node-npm.yml` and
`workflow-integrity.yml` take an optional `runner` input: a JSON string or
JSON array passed through `fromJSON`, default `"ubuntu-latest"`. Private
callers can select a self-hosted runner, for example with
`runner: '["self-hosted", "linux"]'`. Public repositories stay on
GitHub-hosted runners, and fork pull requests must never reach a
self-hosted runner.

### Quick check, full check, and desktop release

`quick-check.yml` runs checkout, toolchain setup with dependency cache,
then install, lint, typecheck, and test. An empty command is skipped.
`runner` is a JSON string or a JSON array and is passed through `fromJSON`;
the default is `"ubuntu-latest"`. Set the version input that matches
`stack`. A second version input installs that extra toolchain as well
(for example `stack: php` together with `node-version`). Node setup expects
an npm `package-lock.json`. PHP setup enables `sqlite3` and `pdo_sqlite`
and caches `vendor/` from `composer.lock`.

`full-check.yml` is the same sequence plus `build-cmd` and optional
`e2e-cmd`. It takes the same `runner` input (default `"ubuntu-latest"`). The default timeout is 30
minutes (quick check: 15).

`release-desktop.yml` builds the JSON `build-matrix` and uploads `dist/`.
Call it only from a workflow triggered by a `v*` tag. The build command is
bash and must write the release files into `dist/` at the repository root.
The uploaded artifact name is `<artifact-name>-<runner>`. When the build
needs signing material, the caller passes inherited secrets:

```yaml
on:
  pull_request:
    branches: [develop]
    types: [opened, synchronize, reopened, ready_for_review]
    paths-ignore:
      - "**/*.md"
      - "docs/**"
      - ".wiki/**"
      - ".agents/**"
permissions:
  contents: read
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
jobs:
  checks:
    if: github.event.pull_request.draft == false
    uses: fits-ki/ci-workflows/.github/workflows/quick-check.yml@<SHA>
    with:
      stack: node
      node-version: "22"
      install-cmd: npm ci --no-audit --no-fund
      lint-cmd: npm run lint
      typecheck-cmd: npm run typecheck
      test-cmd: npm test
      timeout: 15
```

```yaml
jobs:
  full:
    uses: fits-ki/ci-workflows/.github/workflows/full-check.yml@<SHA>
    with:
      stack: node
      node-version: "22"
      install-cmd: npm ci --no-audit --no-fund
      lint-cmd: npm run lint
      typecheck-cmd: npm run typecheck
      test-cmd: npm test
      build-cmd: npm run build
      e2e-cmd: npm run e2e
      timeout: 30
```

```yaml
on:
  push:
    tags: ["v*"]
jobs:
  desktop:
    uses: fits-ki/ci-workflows/.github/workflows/release-desktop.yml@<SHA>
    secrets: inherit
    with:
      build-matrix: '["ubuntu-24.04","windows-2022","macos-15"]'
      build-cmd: npm run build
      artifact-name: desktop
      timeout: 75
```

### `.github/workflows/workflow-integrity.yml` - Workflow integrity

Checks the caller repository after checkout. It does not read a receipt,
a pointer hash, or a script shipped by the caller. Missing legacy files
are not a failure.

Pass requires:

- `AGENTS.md` is a regular file and contains
  `<!-- agent-infra:shared:start -->` and
  `<!-- agent-infra:shared:end -->` exactly once, in that order, with
  non-empty text between the markers
- `openspec/config.yaml` is a non-empty regular file
- `openspec/specs/` and `openspec/changes/archive/` are real directories

Symlinks for those paths fail. No secrets, `contents: read` only,
`runner` input (default `ubuntu-latest`), 5-minute timeout.

```yaml
jobs:
  workflow-integrity:
    uses: fits-ki/ci-workflows/.github/workflows/workflow-integrity.yml@<SHA>
```

## Guarantees and limits

These workflows provide a single check that branch protection *can* be
pointed at; they do not themselves configure or guarantee branch
protection, reviews or automerge. Protection settings remain a per-
repository, separately approved step.

## Self-test

`checks.yml` runs `python3 -m unittest discover -s tests -v` on PRs to
`develop`/`main`. The tests execute the exact inline gate logic and the
literal script-validation block - no GitHub or network needed.
`actionlint.yml` lints the workflow files on non-draft pull requests and
stops after 5 minutes.
