"""
IT service desk performance diagnostic
Data: UCI Incident management process enriched event log (ServiceNow export)

Run:  python analysis.py
Needs: pandas, matplotlib  (pip install pandas matplotlib)
Input: data/incident event log.csv
Output: output/*.csv tables, charts/*.png, output/summary.txt
"""
import re
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "output"
CH = ROOT / "charts"
OUT.mkdir(exist_ok=True)
CH.mkdir(exist_ok=True)
lines = []


def spaced(name):
    """hoursToResolve or hours_to_resolve becomes 'hours to resolve'."""
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(name))
    return name.replace(chr(95), " ").lower()


def save(df, filename, index=True):
    out = df.copy()
    out.columns = [spaced(c) for c in out.columns]
    if index:
        out.index.name = spaced(out.index.name) if out.index.name else None
    out.to_csv(OUT / filename, index=index)


def say(text):
    print(text)
    lines.append(text)


# STEP 1  Load. Missing values in this file are written as "?"
ev = pd.read_csv(ROOT / "data" / "incident event log.csv", na_values="?", low_memory=False)
say(f"Event rows: {len(ev):,}   Incidents: {ev['number'].nunique():,}")

for col in ["opened_at", "resolved_at", "closed_at", "sys_updated_at"]:
    ev[col] = pd.to_datetime(ev[col], format="%d/%m/%Y %H:%M", errors="coerce")

# STEP 2  Reassignment loops from the event history.
# A loop = a ticket goes back to a group that already had it (A to B to A).
ev = ev.sort_values(["number", "sys_mod_count", "sys_updated_at"])


def pingPong(groups):
    seq = [g for g in groups.dropna()]
    path = [g for i, g in enumerate(seq) if i == 0 or g != seq[i - 1]]
    seen, loops = set(), 0
    for g in path:
        if g in seen:
            loops += 1
        seen.add(g)
    return loops


loops = ev.groupby("number")["assignment_group"].apply(pingPong).rename("groupLoops")

# STEP 3  One row per incident: keep the latest event
inc = ev.groupby("number").tail(1).set_index("number").join(loops)

# Keep incidents that were resolved, with a valid timeline
inc["hoursToResolve"] = (inc["resolved_at"] - inc["opened_at"]).dt.total_seconds() / 3600
res = inc[inc["resolved_at"].notna() & (inc["hoursToResolve"] >= 0)].copy()
dropped = len(inc) - len(res)
say(f"Resolved incidents with a valid timeline: {len(res):,} (excluded {dropped:,} open or bad dates)")

res["breached"] = ~res["made_sla"].astype(bool)
# Clean labels: "3 - Moderate" becomes "3 Moderate"
res["priority"] = res["priority"].str.replace(" - ", " ", regex=False)
say(f"Tickets opened between {res['opened_at'].min():%d %b %Y} and {res['opened_at'].max():%d %b %Y}; "
    f"{(res['opened_at'] < '2016-06-01').mean():.1%} were opened March to May 2016")
res["reassignedTwicePlus"] = res["reassignment_count"] >= 2

# STEP 4  Headline KPIs
say("")
say("HEADLINE KPIs")
say(f"Median hours to resolve: {res['hoursToResolve'].median():.1f}")
say(f"Mean hours to resolve: {res['hoursToResolve'].mean():.1f}")
say(f"SLA breach rate: {res['breached'].mean():.1%}  ({res['breached'].sum():,} breaches)")
say(f"Share reassigned 2+ times: {res['reassignedTwicePlus'].mean():.1%}")
say(f"Share with a group ping pong loop: {(res['groupLoops'] > 0).mean():.1%}")
say(f"Share reopened at least once: {(res['reopen_count'] > 0).mean():.1%}")

# STEP 5  By priority
pri = res.groupby("priority").agg(
    incidents=("breached", "size"),
    breachRate=("breached", "mean"),
    medianHours=("hoursToResolve", "median"),
).round(3)
save(pri, "by priority.csv")
say("")
say("BY PRIORITY")
say(pri.to_string())

# STEP 6  By reassignment count
res["reassignBand"] = pd.cut(res["reassignment_count"], [-1, 0, 1, 2, 4, 100],
                              labels=["0", "1", "2", "3 to 4", "5 plus"])
rb = res.groupby("reassignBand", observed=True).agg(
    incidents=("breached", "size"),
    breachRate=("breached", "mean"),
    medianHours=("hoursToResolve", "median"),
).round(3)
save(rb, "by reassignment.csv")
say("")
say("BY REASSIGNMENT COUNT")
say(rb.to_string())

# STEP 7  Categories causing most breaches
cat = res.groupby("category").agg(
    incidents=("breached", "size"),
    breaches=("breached", "sum"),
    breachRate=("breached", "mean"),
    medianHours=("hoursToResolve", "median"),
).sort_values("breaches", ascending=False)
cat["shareOfAllBreaches"] = cat["breaches"] / cat["breaches"].sum()
cat["cumulativeShare"] = cat["shareOfAllBreaches"].cumsum()
save(cat.round(3), "breaches by category.csv")
top5 = cat.head(5)
say("")
say("TOP 5 CATEGORIES BY BREACH COUNT")
say(top5.round(3).to_string())
say(f"Top 5 categories hold {top5['shareOfAllBreaches'].sum():.1%} of all breaches "
    f"from {top5['incidents'].sum() / len(res):.1%} of incidents")

# STEP 8  Backlog: open incidents at each week end, by priority.
# Almost all tickets were opened March to May 2016, so the backlog is only
# meaningful while new tickets were still arriving. Stop at 31 May 2016.
weeks = pd.date_range("2016-03-06", "2016-05-29", freq="W")
rows = []
for w in weeks:
    openNow = res[(res["opened_at"] <= w) & (res["resolved_at"] > w)]
    row = openNow["priority"].value_counts().to_dict()
    row["week"] = w
    rows.append(row)
backlog = pd.DataFrame(rows).set_index("week").fillna(0).astype(int)
backlog = backlog[sorted(backlog.columns)]
save(backlog, "weekly backlog by priority.csv")
say("")
say(f"Open backlog at {backlog.index[0]:%d %b}: {backlog.iloc[0].sum():,}; at {backlog.index[-1]:%d %b}: {backlog.iloc[-1].sum():,}")
say(f"Peak weekly open backlog: {backlog.sum(axis=1).max():,} incidents "
    f"(week of {backlog.sum(axis=1).idxmax():%d %b %Y})")

# STEP 9  Sizing the improvement plan (estimates, built only from this data)
say("")
say("IMPROVEMENT SIZING (estimates from this data)")
base = res[res["reassignment_count"] <= 1]
multi = res[res["reassignment_count"] >= 2]
gapRate = multi["breached"].mean() - base["breached"].mean()
gapHours = multi["hoursToResolve"].median() - base["hoursToResolve"].median()
say(f"Incidents reassigned 2+ times: {len(multi):,}, breach rate {multi['breached'].mean():.1%} "
    f"vs {base['breached'].mean():.1%} for 0 or 1 reassignment")
for share in [0.25, 0.5]:
    n = len(multi) * share
    say(f"If {share:.0%} of 2+ reassignment tickets were routed right first time: "
        f"about {n * gapRate:,.0f} breaches avoided and "
        f"{n * gapHours:,.0f} ticket hours of waiting removed (median gap {gapHours:.0f} h per ticket)")

topCatBreaches = top5["breaches"].sum()
say(f"Cutting the breach rate in the top 5 categories by a quarter would avoid about "
    f"{topCatBreaches * 0.25:,.0f} breaches ({topCatBreaches * 0.25 / res['breached'].sum():.1%} of all)")

reopened = res[res["reopen_count"] > 0]
say(f"Reopened incidents: {len(reopened):,}, breach rate {reopened['breached'].mean():.1%}, "
    f"median {reopened['hoursToResolve'].median():.0f} h vs {res[res['reopen_count'] == 0]['hoursToResolve'].median():.0f} h")

# STEP 10  Charts
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

ax = rb["breachRate"].plot(kind="bar", color="#333333", figsize=(7, 4))
ax.set_title("SLA breach rate rises with every reassignment")
ax.set_xlabel("Number of reassignments"); ax.set_ylabel("Breach rate")
ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
plt.xticks(rotation=0); plt.tight_layout(); plt.savefig(CH / "breach rate by reassignment.png", dpi=150); plt.close()

ax = rb["medianHours"].plot(kind="bar", color="#777777", figsize=(7, 4))
ax.set_title("Median hours to resolve by number of reassignments")
ax.set_xlabel("Number of reassignments"); ax.set_ylabel("Hours")
plt.xticks(rotation=0); plt.tight_layout(); plt.savefig(CH / "hours to resolve by reassignment.png", dpi=150); plt.close()

t10 = cat.head(10)
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.bar(t10.index, t10["breaches"], color="#333333")
ax2 = ax.twinx(); ax2.plot(t10.index, t10["cumulativeShare"], color="#999999", marker="o")
ax2.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0)); ax2.set_ylim(0, 1)
ax.set_title("Ten categories by SLA breaches (bars) and cumulative share (line)")
ax.set_ylabel("Breaches"); plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
plt.tight_layout(); plt.savefig(CH / "breaches by category.png", dpi=150); plt.close()

ax = backlog.plot(kind="area", stacked=True, figsize=(9, 4), colormap="Greys")
ax.set_title("Open backlog at each week end, by priority (March to May 2016)"); ax.set_ylabel("Open incidents"); ax.set_xlabel("")
plt.tight_layout(); plt.savefig(CH / "weekly backlog.png", dpi=150); plt.close()

ax = pri["breachRate"].plot(kind="bar", color="#333333", figsize=(7, 4))
ax.set_title("SLA breach rate by priority"); ax.set_xlabel(""); ax.set_ylabel("Breach rate")
ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
plt.xticks(rotation=0); plt.tight_layout(); plt.savefig(CH / "breach rate by priority.png", dpi=150); plt.close()

# Clean incident table for Power BI, with headers written without underscores
clean = res.reset_index()[["number", "priority", "category", "assignment_group", "contact_type",
                   "opened_at", "resolved_at", "hoursToResolve", "breached",
                   "reassignment_count", "groupLoops", "reopen_count"]]
save(clean, "incidents clean.csv", index=False)

(OUT / "summary.txt").write_text("\n".join(lines))
print("\nDone. Tables in output, charts in charts.")
