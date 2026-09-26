# comp-report

A scheduled job on [Insights Hub](https://github.com/KRISHNABR/insights-platform), owned by
**people-analytics**. Runs every Monday at 06:00 and reports salary spread by department.

It reads `hr.compensation` — **the most sensitive dataset the platform holds** — which makes it
the interesting example. None of the machinery that makes that safe appears in this repo.

---

## What we wrote, and what we got

| We wrote | |
|---|---|
| [`src/main.py`](src/main.py) — a `main()` that queries, aggregates, writes an output | ~40 lines |
| [`app.yaml`](app.yaml) — our contract, including the operational contract for the job | |

| We inherited | |
|---|---|
| The schedule. **We do not run cron** | |
| A service identity — a 06:00 run has no logged-in human | |
| Timeout, retries, concurrency control, catch-up suppression | |
| Data access, the owner's grant check, field masking | |
| Structured logs, metrics, an audit record per read | |
| The container image, and four pipelines across three environments | |

---

## Setup

```bash
mkdir insights-hub && cd insights-hub
for r in insights-platform insights-sdk insights-headcount-dashboard insights-comp-report; do
  git clone "https://github.com/KRISHNABR/$r.git"
done

cd insights-comp-report
uv run insights doctor      # checks our manifest AND that our grant exists
uv run insights run         # run the job now, exactly as the platform runs it
```

Needs Python 3.12 and [uv](https://docs.astral.sh/uv/). `insights run` seeds the local stub
warehouse if it is missing, so a fresh clone just works.

You should see an audit record with `"via_grant": true`, three `dept_summary` events, and a CSV
in `outputs/`.

---

## The operational contract — [`app.yaml`](app.yaml)

A job raises questions a web app does not. Each one is **declared**, not assumed:

```yaml
job:
  schedule: "0 6 * * MON"
  timezone: Europe/Dublin     # explicit. "UTC vs local" causes a real incident once per platform
  timeout: 30m                # SIGTERM at 30m, SIGKILL 30s later
  retries: 2                  # then on_failure pages our owners
  concurrency: forbid         # skip this run if the last one is still going
  catchup: false              # after an outage, do NOT fire a burst of missed runs
  on_failure: notify-owners

outputs:
  - name: weekly-equity-summary
    kind: file
    format: csv
    retention: 90d            # the platform expires it. We do not cron a cleanup
```

We name the artefact; the platform decides where it physically lives, who can read it, and when
it expires. Same "declare, don't wire" rule as data access, pointed the other way.

**In dev, `schedule_enabled: false`.** The job deploys but will not fire on its own — nobody
wants a half-finished report emailing people at 06:00.

---

## How a run works

```mermaid
flowchart TB
  S["platform scheduler<br/><i>06:00 Monday, Europe/Dublin</i>"] --> C["start our container"]
  C --> I["<b>service identity</b>: svc:comp-report<br/><i>there is no logged-in human at 06:00</i>"]
  I --> M["main() runs"]
  M --> Q["query('hr.compensation', sql)"]

  Q --> B1{"declared in our app.yaml?"}
  B1 -->|no| E1(["EntitlementError"])
  B1 -->|yes| B2{"<b>granted by the data owner?</b>"}
  B2 -->|no| E2(["EntitlementError — declaring is not enough"])
  B2 -->|yes| B3["arm the telemetry field assertion<br/><i>from the platform's list, not ours</i>"]
  B3 --> B4["execute with a short-lived credential"]
  B4 --> B5["mask fields this job was not granted"]
  B5 --> B6["audit: who · dataset · rows · masked count"]
  B6 --> A["aggregate in memory"]
  A --> O["output('weekly-equity-summary', summary)"]
  O --> L["log the SHAPE, never the rows"]
  L --> X(["exit 0"])
```

Exit codes are a contract: **0** succeeded · **1** the job broke · **2** the platform refused it.
The scheduler retries 1 and 2 differently, because a refusal will not fix itself.

---

## Why this example is the interesting one

### Declaring a restricted dataset is not enough

Two keys, and we hold only one:

| Key | Who holds it | Where |
|---|---|---|
| "we need this data" | **us** | `data:` in our `app.yaml` |
| "you may have it" | the **dataset owner** | a grant in the platform registry — in production, Unity Catalog |

The platform team cannot supply the second key. They do not own the data.

### Our unmasking role comes from the grant, not from us

This is the subtle one, and it was found by building rather than designing.

A scheduled job has no human, so *"may this caller see salaries?"* cannot be answered from
corporate groups. The tempting fix is to read `access.roles` from our own manifest — but that
file is in **our** repository, so we could unmask compensation by editing one line of our own
YAML.

So the roles a job acts with come from the **grant**, written by the data owner. Notice our
manifest has `roles: []`. Remove `roles: [comp-analyst]` from the grant and this same job gets
`base_salary: "***"` — with no change to anything we control.

### Our telemetry cannot leak compensation

```python
log.info("dept_summary", dept=dept, employees=len(salaries), spread_pct=9.4)   # ✅
log.info("debug", rows=rows)                                                    # ❌ RedactionError
```

The logger raises on anything that is not a scalar, **at the point of writing** — not scrubbed
later at the sink, because scrubbing at the sink fails open. And once this job reads
`hr.compensation`, the logger additionally refuses any record mentioning a *field name* from
that dataset. That list comes from the platform, so we cannot shorten it.

---

## Local vs production — AWS + Databricks

```mermaid
flowchart LR
  subgraph L["LOCAL"]
    direction TB
    L1["platform scheduler<br/><i>cron matching, in Python</i>"]
    L2["our container"]
    L3["service identity<br/><i>built by the scheduler</i>"]
    L4[("SQLite<br/><i>masking applied by the SDK</i>")]
    L5[("JSONL audit")]
    L1 --> L2 --> L3 --> L4
    L3 --> L5
  end

  subgraph P["PRODUCTION — two layers"]
    direction TB
    P1["<b>AWS</b> · EventBridge Scheduler<br/><i>timeout, retries, concurrency</i>"]
    P2["ECS Fargate task<br/><i>its own IAM task role</i>"]
    P3["workload identity federation<br/><b>no client secret exists</b>"]
    P4[("<b>Databricks</b> · Unity Catalog<br/><i>masks and row filters applied by UC,<br/>on every path including notebooks</i>")]
    P5[("UC system.access.audit<br/><i>authoritative</i>")]
    P1 --> P2 --> P3 --> P4
    P4 --> P5
  end

  L -.->|"same src/main.py"| P
```

| Concern | Local | Production | Changes in `src/` |
|---|---|---|---|
| Scheduling | Python cron matcher | EventBridge Scheduler → ECS RunTask | nothing |
| **M2M identity** | scheduler builds `svc:comp-report` | **workload identity federation** from the task role — OIDC, no stored secret | nothing |
| Data | SQLite | Databricks SQL Warehouse | nothing |
| **Masking** | the SDK applies it | **Unity Catalog** applies it, per principal | nothing |
| **The grant** | `grants.yaml` | a Unity Catalog `GRANT`, owned by People Analytics | nothing |
| Audit | JSONL file | UC audit + our correlation record | nothing |
| Outputs | a local directory | an S3 prefix scoped to this app, with a lifecycle rule from `retention` | nothing |

**The line to notice:** in production our masking code does not run at all. Unity Catalog does
it, for every reader on every path — a notebook gets the same masks this job does. The platform
stops owning a governance model beside the data platform's, which is both less code and a
stronger guarantee.

### What a compliance reviewer is handed

```bash
insights compliance-report --dataset hr.compensation
```

Who is entitled, who granted it and when, every read in the period with caller and row count,
every break-glass event with its approver and expiry, and the redaction assertion status.
Nothing in that output is asserted by the command — it is all read from the registry and the
audit trail.

---

*Start at the [platform README](https://github.com/KRISHNABR/insights-platform), then
[ONBOARDING.md](https://github.com/KRISHNABR/insights-platform/blob/main/ONBOARDING.md).*
