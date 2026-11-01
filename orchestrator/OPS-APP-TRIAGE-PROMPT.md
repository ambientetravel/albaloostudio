# Paste into the base44 builder (Albaloo Ops app) — triage + "data as of"

Paste everything below the line into the base44 chat for app `albaloo-ops-core`. It only adds fields and changes how existing screens show them. Do NOT change any entity's access rules (RLS), and do not delete or rename anything.

---

Make these changes to the Albaloo Ops app. Do not touch authentication, access rules, or any existing field.

**1. Review queue: priority.**
Add two fields to the `ArticleReview` entity:
- `priority_score` — number (0 to 100)
- `priority_reason` — text

On the Review queue screen:
- Sort drafts with status `to_review` by `priority_score`, highest first, as the default order. Keep the existing filters.
- Show the score as a small badge on each card (e.g. "87") with `priority_reason` as the line beneath the title.
- Put a "Start here" strip at the top with the three highest-scoring `to_review` drafts.
- Drafts that are not `to_review` have no score; do not show a badge on them.

**2. "Data as of" on every synced screen.**
Add a text field `data_as_of` to `AgentRun`, `HealthItem` and `Metric`, and a text field `coverage_as_of` plus a number field `coverage_age_days` to `Site`.

- Today tab: under the heading show "Health report generated <data_as_of from any AgentRun, formatted as e.g. 31 Oct 13:32 UTC>". If that is more than 26 hours before now, show it in amber with the words "report is late". If more than 50 hours, show it in red with "report is stale — the numbers below may be old".
- Sites tab: next to each site's coverage % show "as of <coverage_as_of>" in small grey text. If `coverage_age_days` is greater than 8, show it in amber with "stale". If a site has no `coverage_as_of`, show "no weekly report yet" instead of a percentage.

Show the dates in the viewer's local time where a time is present. Keep the existing look.
