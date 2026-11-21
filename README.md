# IT service desk performance diagnostic

**Question.** Why does this IT service desk miss its service level agreement on more than a third of tickets, and what would fix it?

**Answer in one line.** Ticket bouncing is the main driver: a ticket solved by the first team has a 23% breach rate and a median resolution time under an hour, while a ticket passed around five or more times breaches 86% of the time. Routing half of the multi hop tickets right first time would avoid about 990 breaches, roughly 11% of the total.

## Approach

* **Data.** 141,712 event log rows exported from a real ServiceNow instance, covering 24,918 incidents. 98.9% of tickets were opened between March and May 2016.
* **Cleaning in Python (pandas).** Treated "?" as missing, parsed dates, ordered each ticket's events, and kept the final state of each ticket. Kept the 23,362 resolved tickets with a valid timeline and dropped 1,556 that were never resolved or had bad dates.
* **Metrics.** Hours to resolve (opened to resolved), SLA breach rate (the final made SLA flag on each ticket), reassignments, ping pong loops (a ticket returning to a group that already had it), weekly open backlog by priority, and breaches by category.
* **Output.** Five charts, CSV tables, and a Power BI report built in the Power BI service on the cleaned ticket table.
* **Power BI report.** One page: four KPI cards (SLA breach rate 38.2%, median 22.1 hours to resolve, 22.0% of tickets reassigned twice or more, 23,362 resolved tickets), breach rate by number of reassignments, breach rate by priority, and tickets opened per day. The data comes straight from `powerbi/incidents for power bi.csv` in this repo, so the report refreshes from GitHub.

## Key findings

* **38.2% of resolved tickets breached SLA** (8,930 tickets). Median time to resolve is 22.1 hours, but the mean is 178.2 hours because a long tail of tickets stays open for weeks.
* **Every reassignment raises the breach rate.**

| Reassignments | Tickets | Breach rate | Median hours to resolve |
|---|---|---|---|
| 0 | 12,003 | 22.9% | 0.7 |
| 1 | 6,228 | 42.9% | 42.1 |
| 2 | 2,283 | 60.1% | 103.0 |
| 3 to 4 | 1,929 | 69.9% | 163.1 |
| 5 or more | 919 | 85.7% | 292.1 |

  22.0% of tickets were reassigned two or more times, and 11.3% went back to a team that had already handled them.
* **Critical and high priority tickets almost always breach.** 671 of 678 (98% to 99.5%) missed SLA, against 37.0% for moderate and 18.2% for low. Either the targets for these priorities are unrealistic or urgent work is not being fast tracked. Both are worth checking with the process owner.
* **Breaches spread across categories.** The five worst categories hold 49.0% of breaches but also 52.1% of tickets, so no single category is the root cause. Category 46 stands out with a 52.5% breach rate and 13.8% of all breaches.
* **Backlog built fast.** Open tickets rose from 956 in the first week of March to a peak of 1,756 in the week of 20 March 2016, and were still at 1,222 at the end of May.
* **Reopened tickets are rare but costly.** Only 274 tickets (1.2%) were reopened, but 75.9% of them breached and their median time to resolve was 237 hours against 21 hours for the rest.

![SLA breach rate by number of reassignments](charts/breach%20rate%20by%20reassignment.png)

## Process improvement plan

All figures below come from this dataset. The adoption rates (25% and 50%) are **assumptions** for planning, not results.

| # | Action | Sizing | Estimated effect |
|---|---|---|---|
| 1 | **Route right first time.** Tighten assignment rules on the categories and symptoms that most often bounce, add a short triage checklist at the first line, and require a reason code on every reassignment. | 5,131 tickets were reassigned two or more times; their breach rate was 68.4% against 29.7% for tickets with at most one reassignment, and their median resolution time was 158 hours longer. | If 25% are routed right first time: about 500 breaches avoided and about 203,000 hours less waiting for users. At 50%: about 990 breaches and 406,000 hours. |
| 2 | **Fix the urgent ticket path.** Review SLA targets for critical and high priority and set up a swarm or on call rota so these tickets skip the normal queue. | 671 breaches sit in critical and high priority. | Up to 7.5% of all breaches, plus the reputational cost of failing on the tickets users care about most. |
| 3 | **Target the five worst categories** with knowledge articles and dedicated resolver groups, starting with Category 46. | These five hold 4,370 breaches. | Cutting their breach rate by a quarter avoids about 1,090 breaches, 12.2% of the total. |

Caveats. Hours saved are elapsed hours a user waits, not agent working hours, which the log does not record. The link between reassignment and breach is a correlation: harder tickets get passed around more, so not every avoided hop would avoid a breach. The plan uses the 25% case as the base for that reason.

## Files

```
ServiceDeskDiagnostic/
  README.md                       this summary
  Build Guide.md                  step by step instructions, plus Power BI steps
  powerbi/incidents for power bi.csv   one row per resolved ticket with helper columns (reassign band, breach pct)
  powerbi/weekly backlog by priority.csv   weekly open backlog, March to May 2016
  analysis.py                     all cleaning, metrics, sizing and charts
  output/
    summary.txt                   every number in this README
    by priority.csv
    by reassignment.csv
    breaches by category.csv
    weekly backlog by priority.csv
    incidents clean.csv           one row per resolved ticket for Power BI (created when you run the script)
  charts/                         five PNG charts
  data/                           put the UCI CSV here (not committed)
```

## Tools

Python (pandas, matplotlib), Power BI service (Power Query web connector, report editor), ServiceNow incident data model. The charts in `charts/` are the Python chart pack; the Build Guide has the steps and DAX measures to build the same view in Power BI from `incidents clean.csv`.

## How to run

1. Download the dataset from the [UCI Machine Learning Repository: Incident management process enriched event log](https://archive.ics.uci.edu/dataset/498/incident+management+process+enriched+event+log) (Download button, about 2.4 MB zipped). Unzip it into `data/` and rename the CSV to `incident event log.csv`.
2. Run:

```
pip install pandas matplotlib
python analysis.py
```

It finishes in under 30 seconds and writes everything to `output/` and `charts/`.

Data: Amaral, C., Fantinato, M., and Peres, S. (2018). Incident management process enriched event log. UCI Machine Learning Repository. CC BY 4.0.
