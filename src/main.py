"""Weekly compensation equity summary — a scheduled job on Insights Hub.

The second archetype. Same SDK, same broker, same rules. The differences are
`kind: job` in the manifest and `run_job` instead of `web_app`.

This reads the most sensitive dataset on the platform, and none of the machinery
that makes that safe appears here: the owner's grant, the masking rules, the
sensitive-field list and the audit record all live on the platform side. This
team writes the query and the arithmetic.
"""

from insights_sdk import get_logger, output, query, run_job

log = get_logger()


def main() -> None:
    rows = query(
        "hr.compensation",
        "SELECT dept, base_salary FROM hr.compensation",
    )

    # Individual rows never leave this function, and could not be logged if we
    # tried: the logger raises on a payload, and raises again on any mention of a
    # field name belonging to a restricted dataset.
    by_dept: dict[str, list[int]] = {}
    for row in rows:
        salary = row["base_salary"]
        if salary == "***":
            continue                    # this run was not granted the unmasking role
        by_dept.setdefault(row["dept"], []).append(salary)

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
