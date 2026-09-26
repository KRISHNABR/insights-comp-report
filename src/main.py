"""Weekly compensation equity report - a scheduled job on Insights Hub.

The second archetype. Same SDK, same data broker, same telemetry rules; the only
differences are `kind: job` in the manifest and `run_job` instead of `web_app`.

This app reads the most sensitive dataset on the platform, and the code shows none of
the machinery that makes that safe: the grant, the masking rules, the sensitive-field
list and the audit record all live on the platform side. This team writes the query.
"""

from insights_sdk import get_logger, query, run_job

log = get_logger()


def main() -> None:
    rows = query(
        "hr.compensation",
        "SELECT dept, base_salary, bonus_pct FROM hr.compensation",
    )

    # Aggregate in memory. The individual rows never leave this function, and could not
    # be logged if we tried - the SDK raises on a payload, and raises again on any
    # mention of a restricted field name.
    by_dept: dict[str, list[int]] = {}
    for row in rows:
        salary = row["base_salary"]
        if salary == "***":
            continue                    # this run was not authorised to see the figures
        by_dept.setdefault(row["dept"], []).append(salary)

    for dept, salaries in sorted(by_dept.items()):
        log.info(
            "dept_summary",
            dept=dept,
            employees=len(salaries),
            spread_pct=round(100 * (max(salaries) - min(salaries)) / max(salaries), 1),
        )

    log.info("report_complete", departments=len(by_dept), rows=len(rows))


if __name__ == "__main__":
    raise SystemExit(run_job(main))
