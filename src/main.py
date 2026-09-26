"""Weekly compensation equity summary — a scheduled job on Insights Hub.

The second archetype: `kind: job` in the manifest, `run_job` instead of `web_app`.

We read compensation data we already have access to. People Analytics granted it to
this app's service identity in the data platform — not on this platform, which owns
no data and grants nothing. What we inherit here is the connector, a credential we
never see the value of, the schedule, and telemetry.

Note what the platform does NOT see: the SQL below, or a single row it returns. It
records that a query ran on `hr-warehouse`, how long it took and how many rows came
back. The numbers are ours.
"""

from insights_sdk import connect, get_logger, output, run_job

log = get_logger()


def main() -> None:
    # Our connection, declared in app.yaml. The credential is resolved from the
    # secret store using this app's own identity; it never appears in this file, in
    # the manifest, or in any log line.
    warehouse = connect("hr-warehouse")

    rows = warehouse.query(
        "SELECT dept, base_salary FROM hr_compensation",
    )

    # Individual rows never leave this function, and could not be logged if we
    # tried: the logger raises on a payload.
    by_dept: dict[str, list[int]] = {}
    for row in rows:
        by_dept.setdefault(row["dept"], []).append(row["base_salary"])

    summary = [
        {
            "dept": dept,
            "employees": len(salaries),
            "spread_pct": round(100 * (max(salaries) - min(salaries)) / max(salaries), 1),
        }
        for dept, salaries in sorted(by_dept.items())
    ]

    # A declared output. We name the artefact; the platform decides where it lives,
    # who may read it, and when it expires (90 days, per app.yaml).
    output("weekly-equity-summary", summary)

    log.info("report_complete", departments=len(summary), rows=len(rows))


if __name__ == "__main__":
    raise SystemExit(run_job(main))
