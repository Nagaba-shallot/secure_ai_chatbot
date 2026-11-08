from collections import Counter
from datetime import datetime, timedelta, timezone

KINDS = (
    "input_blocked",  
    "input_masked",  
    "output_blocked",  
    "output_redacted",  
    "memory_rejected",  
    "rate_limited",  
    "login_failed", 
)
RULE_KINDS = ("input_blocked", "input_masked", "output_blocked", "output_redacted", "memory_rejected")


def build_stats(rows, days, now=None):
    now = now or datetime.now(timezone.utc)
    today = now.date()
    dates = [(today - timedelta(days=offset)).isoformat() for offset in range(days - 1, -1, -1)]
    position = {date: i for i, date in enumerate(dates)}

    daily = [{"date": date, **{kind: 0 for kind in KINDS}} for date in dates]
    totals = {kind: 0 for kind in KINDS}
    triggers = Counter()

    for row in rows:
        kind = row["kind"]
        i = position.get(row["created_at"][:10])
        if kind not in totals or i is None:
            continue
        daily[i][kind] += 1
        totals[kind] += 1
        if kind in RULE_KINDS:
            for rule in (part.strip() for part in row["detail"].split(",")):
                if rule:
                    triggers[(kind, rule)] += 1

    rules = [{"kind": kind, "rule": rule, "count": count} for (kind, rule), count in triggers.most_common(10)]
    return {"days": days, "totals": totals, "daily": daily, "rules": rules}