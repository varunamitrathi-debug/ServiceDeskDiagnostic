# Build guide: IT service desk performance diagnostic

Two or three evenings. Evening 1 is Python, evening 2 is Power BI, evening 3 is the write up.

## Evening 1: Python analysis

**1. Get the data**

* Open the [UCI page for the incident management event log](https://archive.ics.uci.edu/dataset/498/incident+management+process+enriched+event+log) and click Download.
* Unzip, put the CSV in `data/` and rename it `incident event log.csv`.

**2. Understand one thing first: this is an event log**

Each ticket appears many times, once per update. Ticket INC0000045 has a row when it was created, another when it was resolved, another when it was closed. So step one is always to collapse the log to one row per ticket, otherwise every count is inflated.

**3. Run the script**

```
pip install pandas matplotlib
python analysis.py
```

`analysis.py` is split into numbered steps. Read it alongside this list:

* **Step 1 Load.** The missing values setting turns the dataset's "?" placeholders into proper missing values. Dates are in day/month/year format, so the format is given explicitly.
* **Step 2 Ping pong loops.** For each ticket, list the assignment groups in order, drop repeats in a row, then count how often a group shows up again later. A to B to A counts as one loop.
* **Step 3 One row per ticket.** `groupby("number").tail(1)` keeps the latest event. Hours to resolve = resolved time minus opened time. Tickets never resolved, or with a resolve time before the open time, are dropped and the count is printed so you can report it.
* **Step 4 Headline KPIs.** Median and mean hours to resolve, breach rate, share reassigned twice or more, share with a loop, share reopened.
* **Step 5 and 6.** The same KPIs split by priority and by number of reassignments, using `groupby` and `agg`.
* **Step 7 Categories.** Breaches per category, sorted, with a running share. This is a Pareto table.
* **Step 8 Backlog.** For each Sunday from March to May 2016, count tickets opened before that date and resolved after it. The window stops at May because almost no new tickets were logged after that, so a later backlog would just shrink and mislead.
* **Step 9 Sizing.** Compares tickets with two or more reassignments to the rest and scales the gap by an adoption rate of 25% and 50%. Those two rates are planning assumptions; say so whenever you quote the result.
* **Step 10 Charts and export.** Saves five charts and `output/incidents clean.csv` for Power BI.

Check your run against `output/summary.txt`: 23,362 resolved tickets, 38.2% breach rate, 22.1 median hours.

## Evening 2: Power BI dashboard

**1. Load.** Home, Get data, Text/CSV, pick `output/incidents clean.csv`, Load. Check in the Data view that `opened at` and `resolved at` are Date/Time, `breached` is True/False and `hours to resolve` is a decimal number.

**2. Add a date table** (Modeling, New table):

```
Calendar = CALENDAR(DATE(2016,2,1), DATE(2017,3,1))
```

Add a column `Opened date = DATEVALUE(incidents[opened at])`, then relate `Calendar[Date]` to it.

**3. Add a reassignment band column** (Modeling, New column):

```
Reassign band =
SWITCH(TRUE(),
    incidents[reassignment count] = 0, "0",
    incidents[reassignment count] = 1, "1",
    incidents[reassignment count] = 2, "2",
    incidents[reassignment count] <= 4, "3 to 4",
    "5 or more")
```

**4. Measures** (Modeling, New measure, one at a time):

```
Tickets = COUNTROWS(incidents)
Breaches = CALCULATE([Tickets], incidents[breached] = TRUE())
Breach rate = DIVIDE([Breaches], [Tickets])
Median hours = MEDIAN(incidents[hours to resolve])
Share reassigned 2 plus = DIVIDE(CALCULATE([Tickets], incidents[reassignment count] >= 2), [Tickets])
Share with loop = DIVIDE(CALCULATE([Tickets], incidents[group loops] > 0), [Tickets])
```

Format Breach rate and the two share measures as percentages.

**5. One page layout**

* Top row, four cards: Tickets, Breach rate, Median hours, Share reassigned 2 plus.
* Left middle: clustered column chart, axis Reassign band, value Breach rate. This is the headline visual.
* Right middle: clustered column chart, axis priority, value Breach rate.
* Bottom left: bar chart of Breaches by category, Top N filter set to 10.
* Bottom right: line chart of Tickets by week of opened date, legend priority.
* Slicers: priority, contact type, assignment group.

Keep it black, white and grey with one accent colour for breaches. Title the page with the finding, for example "Each reassignment raises the breach rate", not "Dashboard".

**6. Save** as `Service Desk Dashboard.pbix` in the repo and export a PNG screenshot to `charts/` so people can see it without Power BI.

## Evening 3: write up

* Fill the README findings from `output/summary.txt`, not from memory.
* Structure the improvement plan as action, sizing, effect, and state the caveats (elapsed hours, correlation not causation).
* Commit everything except the raw CSV in `data/`.
