# CI Workflows

Generic, secret-free CI building blocks for the fits-ki repository fleet.

Application code, private repository inventories and credentials belong in
their own repositories, never here.

Development targets `develop`; releases to `main` require separate approval.
Consumers pin reviewed workflow commits. Creating this repository does not
enable automerge or change any application's deployment policy.

## Reusable workflows

The two building blocks are `workflow_call` reusables. Callers must pin the exact
40-character commit SHA of a reviewed commit:

```yaml
uses: fits-ki/ci-workflows/.github/workflows/<name>.yml@<full-40-char-sha>
```

### `.github/workflows/node-npm.yml` - Node/npm checks

Runs a package.json verification script on Ubuntu with a 15-minute timeout.

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

## Guarantees and limits

These workflows provide a single check that branch protection *can* be
pointed at; they do not themselves configure or guarantee branch
protection, reviews or automerge. Protection settings remain a per-
repository, separately approved step.

## Self-test

`checks.yml` runs `python3 -m unittest discover -s tests -v` on PRs to
`develop`/`main`. The tests execute the exact inline gate logic and the
literal script-validation block - no GitHub or network needed.
