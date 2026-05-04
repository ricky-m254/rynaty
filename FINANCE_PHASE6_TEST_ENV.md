# Finance Phase-6 Local Test Environment

## Purpose

The finance phase-6 Django regression pack is not expected to run against the checked-in `sms-backend/.env` Postgres settings.

That file is kept as the default app/dev configuration and currently points at `localhost:5432`. The finance phase-6 pack should instead run against a repo-local disposable Postgres cluster so test execution is repeatable and does not depend on the machine-global database state.

## Canonical Command

Run the full finance phase-6 pack with:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_finance_phase6_tests.ps1
```

That runner:

- starts the repo-local temp Postgres cluster if needed
- resets the disposable cluster and retries startup once if a stale data dir fails to boot cleanly
- points Django at `postgresql://postgres@127.0.0.1:55437/test_sms_school_db`
- runs the full finance phase-6 pack with `--keepdb --noinput`
- writes stdout/stderr logs to repo-root `artifacts/`

To stop the cluster after the test run:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_finance_phase6_tests.ps1 -StopAfter
```

## Temp Cluster Location

- data dir: `artifacts/temp_pg_phase6_tests`
- host: `127.0.0.1`
- port: `55437`
- user: `postgres`
- auth: `trust`
- base DB: `test_sms_school_db`

This cluster is disposable and repo-local. It is not the application default and should not be treated as a production-like service.

## Cluster Management

Start the cluster:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\manage_phase6_test_postgres.ps1 -Action start
```

Check status:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\manage_phase6_test_postgres.ps1 -Action status
```

Stop the cluster:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\manage_phase6_test_postgres.ps1 -Action stop
```

Reset the cluster:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\manage_phase6_test_postgres.ps1 -Action reset
```

## Why Plain `manage.py test` Is Not The Accepted Path

Plain `manage.py test` inherits the checked-in `.env`, which currently resolves Postgres from:

- `POSTGRES_HOST=localhost`
- `POSTGRES_PORT=5432`
- `POSTGRES_USER=postgres`
- `POSTGRES_PASSWORD=change-me`

That is acceptable for local app/dev defaults, but it is not a stable acceptance path for the finance phase-6 regression pack. Use the dedicated runner whenever the goal is finance phase-6 verification.
