# Genuine development incident log

## INC-001 - Docker registry bootstrap failure - 27 October 2026

- **Observed impact:** first `docker compose up --build -d` exited with code 1;
  the monitoring image pull could not resolve and the application did not start.
- **Actual evidence:** `failed to resolve reference docker.io/jaegertracing/all-in-one:1.63.0`;
  `http: server gave HTTP response to HTTPS client`.
- **Detection:** command output from the real initial startup attempt, not a
  simulated incident.
- **Diagnosis:** Docker Desktop had just been started. `docker info` initially
  failed before startup, then reported an active engine. The error occurred on
  the registry transport; there was no application runtime yet. A persistent
  root cause was not established, so no proxy misconfiguration is asserted.
- **Recovery performed:** pulled `python:3.12-slim` successfully and retried the
  Compose command. All seven long-running services then reached healthy status.
  No global Docker proxy/TLS setting or unrelated project was modified.
- **Prevention/action:** documented engine and registry checks in the runbook;
  bundle the public corpus so boot requires image/dependency downloads only,
  rather than a second network dependency on FSSAI.

## INC-002 - Browser verification runtime lacked Chromium - 27 October 2026

- **Observed impact:** the first Playwright acceptance command exited before
  launching a browser: the bundled Playwright package expected a headless-shell
  executable that was not installed on this machine.
- **Actual evidence:** `Executable doesn't exist ... chromium_headless_shell-1234`.
- **Recovery performed:** selected the installed Microsoft Edge channel through
  `LG_BROWSER_CHANNEL=msedge`. The actual browser flow subsequently passed,
  including submission, polling, evidence display, activity and mobile layout.
- **Prevention/action:** the browser script now accepts a runtime browser channel;
  no machine-specific executable path is hardcoded in project code.

The provider-outage and candidate-tampering exercises in `output/verification/`
are deliberate fault-injection tests. They are kept separate from these genuine
development failures.
