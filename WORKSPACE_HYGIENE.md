# Workspace Hygiene

Last updated: 2026-04-26

## Purpose

Local browser runs and temporary Postgres sandboxes can leave noise under the repo-root `artifacts/` folder. This doc keeps cleanup repeatable without touching tracked implementation files.

## Auto-Ignored Runtime Clutter

The repo now ignores these root-level artifact patterns:

- `artifacts/temp_pg_*/`
- `artifacts/cdp-*/`
- `artifacts/chrome-*/`
- `artifacts/*.log`
- `artifacts/*.zip`

These ignore rules do not affect tracked files under `sms-backend/artifacts/`.

## Cleanup Helper

Use the scoped PowerShell helper:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\cleanup_local_artifacts.ps1
```

That runs in preview mode and only lists what would be removed.

To actually delete the runtime clutter:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\cleanup_local_artifacts.ps1 -Apply
```

## Safety Rules

- cleanup is restricted to the repo-root `artifacts/` directory
- the helper verifies every removal target stays inside that directory
- it only targets temp Postgres folders, browser runtime folders, logs, and zip outputs
- it does not touch working docs such as `CRITIQUE_AND_ACTIONS.md`
- it does not touch manually kept scripts such as `artifacts/run_local_demo_server.ps1`
