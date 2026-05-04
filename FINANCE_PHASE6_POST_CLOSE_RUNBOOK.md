# Finance Phase-6 Post-Close Runbook

Date: 2026-05-01

## Purpose

This runbook exists only for the unresolved canonical finance phase-6 verification environment issue.

It should be reopened after the active finance and communication implementation phases are functionally closed. It is not a signal to keep spending retries on the temp-cluster path during the current wave.

## Current State Snapshot

- Targeted finance phase-6 grouped packs already passed earlier in the disposable test environment.
- `py_compile` passed for the changed finance and communication Python files in the current wave.
- The canonical full runner at `tools/run_finance_phase6_tests.ps1` is still unresolved as an accepted end-to-end verification path.
- The active implementation stream has moved on to communication `P4` foundation work instead of blocking on more phase-6 cluster retries.

## Known-Good Evidence To Preserve

Grouped finance packs that already passed:

- `school.test_phase6_architecture_guardrails`
- `school.test_phase6_finance_reference_activation_prep`
- `school.test_phase6_finance_receivables_activation_prep`
- `school.test_production_readiness_gate`

Grouped finance packs that also passed in the disposable environment:

- `school.test_phase6_finance_billing_activation_prep`
- `school.test_phase6_finance_report_activation_prep`
- `school.test_phase6_finance_governance_activation_prep`
- `school.test_phase6_finance_collection_ops_activation_prep`
- `school.test_phase6_finance_accounting_activation_prep`
- `school.test_phase6_finance_write_activation_prep`

Related helper/runtime files:

- `FINANCE_PHASE6_TEST_ENV.md`
- `tools/manage_phase6_test_postgres.ps1`
- `tools/run_finance_phase6_tests.ps1`

## Failure Pattern Seen So Far

The unresolved issue is environmental and repeatable enough to document:

- temp Postgres startup can fail through `pg_ctl`
- the helper then falls back to direct `postgres.exe` startup
- the direct-start cluster does not remain reliably usable across separate shell invocations
- combined start-and-test attempts can time out before the Django command finishes
- when the direct-start fallback path is used, `status` checks can later report `Running: no` and `Ready: no` even after startup output initially reported success

This is why the canonical runner is deferred instead of being treated as the gating proof for the current implementation batch.

## Artifacts To Inspect When Reopening

Start here before changing code again:

- `FINANCE_PHASE6_TEST_ENV.md`
- `tools/manage_phase6_test_postgres.ps1`
- `tools/run_finance_phase6_tests.ps1`
- `artifacts/temp_pg_phase6_tests.runtime.json`
- `artifacts/temp_pg_phase6_tests.server.log`
- `artifacts/temp_pg_phase6_tests.stdout.log`
- `artifacts/temp_pg_phase6_tests.stderr.log`
- `artifacts/finance_phase6_tests.stdout.log`
- `artifacts/finance_phase6_tests.stderr.log`

## Post-Close Recovery Procedure

Follow this order exactly.

1. Inspect the runtime and runner logs first.
2. Confirm whether the last failing attempt died during:
   - `pg_ctl` startup
   - direct `postgres.exe` fallback
   - cross-invocation persistence
   - Django test execution
3. Stop the disposable cluster if it is still partially running.
4. Reset the disposable cluster data directory.
5. Retry the canonical runner once:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_finance_phase6_tests.ps1
```

6. If the helper falls back to direct startup again, do not immediately keep tuning timings.
7. Instead, run the previously known grouped finance packs in a single shell invocation so the failure can be isolated between:
   - startup timing
   - cross-shell process persistence
   - readiness detection
   - actual Django regression
8. Only after that split is understood should `tools/manage_phase6_test_postgres.ps1` or `tools/run_finance_phase6_tests.ps1` be changed again.

## Root-Cause Buckets To Decide Between

When the issue is reopened, classify it into one of these buckets before editing scripts:

- Startup timing:
  - `pg_ctl` needs a different wait or readiness policy
- Cross-shell process persistence:
  - direct `postgres.exe` startup works only in the launching shell
- Readiness detection:
  - the cluster is usable but the helper decides it is not
- Django/runtime regression:
  - the database is fine and the actual failing part is the test process

Do not mix these into one generic “cluster failure” diagnosis.

## Closure Criteria

This runbook is only closed when one of these is true:

- the canonical full phase-6 runner completes end to end on the disposable cluster
- a replacement accepted verification path is formally adopted and the old runner is explicitly deprecated in repo docs

## Closeout Actions After Resolution

Once resolved:

1. Update `FINANCE_PHASE6_TEST_ENV.md` with the final accepted verification path.
2. Update `FINANCE_COMMUNICATION_ALIGNMENT_PLAN.md` to remove the deferred-runner note.
3. Record the final accepted command and evidence location.
4. Keep the final logs or evidence files referenced from the documentation so later reopenings do not lose the proof trail.
