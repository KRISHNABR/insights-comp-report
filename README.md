# comp-report

A scheduled job on [Insights Hub](https://github.com/KRISHNABR/insights-platform/blob/main/README.md). Owned by **people-analytics**.

Runs every Monday at 06:00 and reports salary spread by department.

| | |
|---|---|
| What we wrote | [`src/main.py`](src/main.py) (~40 lines) and [`app.yaml`](app.yaml) |
| What we inherited | identity, data access, logging, scheduling, retries, the base image |
| Data | `hr.compensation` — **restricted**. Granted by People Analytics on 2026-09-20 |

We do not run a scheduler. We declared `schedule: "0 6 * * MON"` and the platform runs us.

Because our dataset is restricted, three extra things are true and none of them are in
our code: the platform team cannot read our rows without break-glass, our telemetry is
checked at emit for compensation field names, and every read we do is audited with the
caller and row count. See [ADR-002](https://github.com/KRISHNABR/insights-platform/blob/main/docs/adr/ADR-002-shared-data-and-isolation.md).

---

*New to the platform? Start at the [platform README](https://github.com/KRISHNABR/insights-platform/blob/main/README.md), which maps everything, then [ONBOARDING.md](https://github.com/KRISHNABR/insights-platform/blob/main/ONBOARDING.md).*
