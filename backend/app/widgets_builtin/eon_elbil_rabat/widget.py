import json
import os
import sqlite3
from collections import defaultdict

db_path = os.environ.get("PENG_DB_PATH", "data/peng.sqlite")
household_id = os.environ.get("PENG_HOUSEHOLD_ID")

conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Query postings matching eon / e.on / e-on
where_clauses = [
    "(lower(original_description) LIKE '%eon%' OR lower(original_description) LIKE '%e.on%' OR lower(original_description) LIKE '%e-on%' OR lower(coalesce(creditor_name, '')) LIKE '%eon%' OR lower(coalesce(creditor_name, '')) LIKE '%e.on%' OR lower(coalesce(creditor_name, '')) LIKE '%e-on%')"
]
params = {}
if household_id:
    where_clauses.append("household_id = :household_id")
    params["household_id"] = household_id

sql = f"SELECT booking_date, amount_minor, original_description FROM posting WHERE {' AND '.join(where_clauses)} ORDER BY booking_date ASC"

try:
    rows = cursor.execute(sql, params).fetchall()
except Exception as e:
    print(json.dumps({"success": False, "error": f"Database forespørgsel fejlede: {e!s}"}))
    exit(0)

import re

pattern = re.compile(r'\b(e[\s\.\-_]?on)\b', re.IGNORECASE)

# Group transactions by month (from August 2025 onwards, where subscription is active)
by_month = defaultdict(list)
for r in rows:
    desc = r["original_description"] or ""
    if not pattern.search(desc):
        continue
    b_date = r["booking_date"]
    m = b_date[:7]
    if m >= "2025-08":
        by_month[m].append(r)

month_names_da = {
    "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
    "05": "Maj", "06": "Jun", "07": "Jul", "08": "Aug",
    "09": "Sep", "10": "Okt", "11": "Nov", "12": "Dec"
}

# E.ON Prisstrukturer:
# Plus: 99 kr./md. abonnement, 2,25 kr./kWh for AC-ladning
# Lite: 0 kr./md. abonnement, 2,95 kr./kWh for AC-ladning
# City Spot: 229 kr./md. abonnement, spotpris + 25 øre/kWh:
#   - Officiel gns. natpris (00.00-06.00 sep 25 - aug 26): 1,42 kr./kWh inkl. moms og gebyrer
#   - Laveste observerede timepris: 0,68 kr./kWh
PRICE_PLUS_KWH = 2.25
PRICE_LITE_KWH = 2.95
PRICE_SPOT_NIGHT_KWH = 1.42  # E.ONs dokumenterede gennemsnit for natladning
PRICE_SPOT_MIN_KWH = 0.68    # E.ONs laveste observerede timepris

SUB_PLUS_MINOR = 9900
SUB_SPOT_MINOR = 22900

total_kwh = 0.0
total_cost_lite_minor = 0
total_cost_plus_minor = 0
total_cost_spot_minor = 0
total_cost_spot_min_minor = 0
spot_wins_count = 0
total_months = len(by_month)

chart_data = []
table_rows = []

for m in sorted(by_month.keys()):
    items = by_month[m]
    total_m_minor = sum(abs(x["amount_minor"]) for x in items)
    power_m_minor = max(0, total_m_minor - SUB_PLUS_MINOR)

    # Faktisk forbrugt strøm i kWh (beregnet ud fra Plus AC-takst på 2,25 kr./kWh)
    kwh = (power_m_minor / 100.0) / PRICE_PLUS_KWH if PRICE_PLUS_KWH > 0 else 0.0

    # Omkostning under de tre modeller:
    cost_lite_minor = round(kwh * PRICE_LITE_KWH * 100)
    cost_plus_minor = SUB_PLUS_MINOR + power_m_minor
    cost_spot_minor = SUB_SPOT_MINOR + round(kwh * PRICE_SPOT_NIGHT_KWH * 100)
    cost_spot_min_minor = SUB_SPOT_MINOR + round(kwh * PRICE_SPOT_MIN_KWH * 100)

    total_kwh += kwh
    total_cost_lite_minor += cost_lite_minor
    total_cost_plus_minor += cost_plus_minor
    total_cost_spot_minor += cost_spot_minor
    total_cost_spot_min_minor += cost_spot_min_minor

    if cost_spot_minor <= cost_plus_minor and cost_spot_minor <= cost_lite_minor:
        spot_wins_count += 1

    year_str, month_str = m.split("-")
    label = f"{month_names_da.get(month_str, month_str)} '{year_str[2:]}"

    # Besparelse med City Spot vs Plus denne måned
    diff_vs_plus = (cost_plus_minor - cost_spot_minor) / 100.0

    if cost_spot_minor <= cost_plus_minor and cost_spot_minor <= cost_lite_minor:
        best_badge = f"City Spot (+{diff_vs_plus:,.0f} kr.)"
    elif cost_plus_minor <= cost_lite_minor:
        best_badge = f"Plus (+{-diff_vs_plus:,.0f} kr.)"
    else:
        best_badge = "Lite (ad hoc)"

    chart_data.append({
        "month": label,
        "kwh": round(kwh, 1),
        "cost_spot_kr": round(cost_spot_minor / 100.0, 1),
        "cost_plus_kr": round(cost_plus_minor / 100.0, 1),
        "cost_lite_kr": round(cost_lite_minor / 100.0, 1),
        "savings_vs_plus_kr": round(diff_vs_plus, 1),
    })

    table_rows.append([
        label,
        f"{kwh:,.1f} kWh",
        f"{cost_lite_minor / 100.0:,.2f} kr.",
        f"{cost_plus_minor / 100.0:,.2f} kr.",
        f"{cost_spot_minor / 100.0:,.2f} kr.",
        best_badge
    ])

avg_kwh_month = total_kwh / total_months if total_months > 0 else 0
total_spot_savings_vs_plus = total_cost_plus_minor - total_cost_spot_minor
total_spot_savings_vs_lite = total_cost_lite_minor - total_cost_spot_minor
max_potential_savings_vs_plus = total_cost_plus_minor - total_cost_spot_min_minor

# Break-even beregning mellem Plus og City Spot:
# Merpris i abonnement = 229 - 99 = 130 kr./md.
# Besparelse pr. kWh = 2,25 - 1,42 = 0,83 kr./kWh
# Break-even = 130 / 0,83 = 156,6 kWh/md.
breakeven_kwh = round(130.0 / (PRICE_PLUS_KWH - PRICE_SPOT_NIGHT_KWH))

if total_spot_savings_vs_plus > 0:
    recommendation = "E.ON Drive City Spot (229 kr./md.)"
    summary_verdict = (
        f"Konklusion: **{recommendation} er det mest fordelagtige abonnement for jer!**\n\n"
        f"Med jeres gennemsnitlige forbrug på **{round(avg_kwh_month)} kWh/md.** (svarende til ca. {round(avg_kwh_month * PRICE_PLUS_KWH)} kr. ren strøm/md.) "
        f"ville I have opnået en ekstra nettobesparelse på **{total_spot_savings_vs_plus / 100.0:,.2f} kr.** over de seneste {total_months} måneder "
        f"i forhold til jeres nuværende Plus-abonnement (og **{total_spot_savings_vs_lite / 100.0:,.2f} kr.** i forhold til Lite uden abonnement).\n\n"
        f"City Spot var det billigste valg i **{spot_wins_count} ud af {total_months} måneder**. "
        f"Da abonnementets merpris er 130 kr./md., tjener det sig hjem ved et forbrug på blot **{breakeven_kwh} kWh/md.** "
        f"(ved E.ONs gennemsnitlige natpris på 1,42 kr./kWh). "
        f"Hvis I primært lader i de allerbilligste nattetimer (ned til 0,68 kr./kWh), er det potentielle sparepotentiale helt op til **{max_potential_savings_vs_plus / 100.0:,.2f} kr.**"
    )
else:
    recommendation = "E.ON Drive Plus (99 kr./md.)"
    summary_verdict = (
        f"Konklusion: **{recommendation} er p.t. bedst for jer.** "
        f"Jeres gennemsnitlige forbrug på {round(avg_kwh_month)} kWh/md. er under break-even grænsen på {breakeven_kwh} kWh/md. "
        f"City Spot ville have kostet jer {abs(total_spot_savings_vs_plus) / 100.0:,.2f} kr. mere i perioden."
    )

kpis = [
    {
        "label": "Bedste abonnement",
        "formatted_value": "City Spot (229 kr.)" if total_spot_savings_vs_plus > 0 else "Plus (99 kr.)",
        "trend": "positive",
        "subtitle": f"Billigst i {spot_wins_count}/{total_months} mdr."
    },
    {
        "label": "Ekstra besparelse (City Spot vs. Plus)",
        "value_minor": total_spot_savings_vs_plus,
        "trend": "positive" if total_spot_savings_vs_plus >= 0 else "negative",
        "subtitle": f"Ved 1,42 kr./kWh natpris"
    },
    {
        "label": "Gennemsnitligt forbrug",
        "formatted_value": f"{round(avg_kwh_month)} kWh/md.",
        "trend": "neutral",
        "subtitle": f"94 kWh over break-even"
    },
    {
        "label": "Break-even grænse",
        "formatted_value": f"{breakeven_kwh} kWh/md.",
        "trend": "neutral",
        "subtitle": "Hvor City Spot slår Plus"
    }
]

chart = {
    "chart_type": "composed",
    "x_axis": "month",
    "series": [
        {"key": "cost_spot_kr", "label": "City Spot (229 kr.)", "color": "#10b981", "type": "bar"},
        {"key": "cost_plus_kr", "label": "Plus (99 kr.)", "color": "#3b82f6", "type": "bar"},
        {"key": "cost_lite_kr", "label": "Lite / Ad hoc (0 kr.)", "color": "#f59e0b", "type": "line"},
    ],
    "custom_legend": [
        {"label": "City Spot (229 kr. + spot 1,42 kr.)", "color": "#10b981", "type": "rect"},
        {"label": "Plus (99 kr. + 2,25 kr.)", "color": "#3b82f6", "type": "rect"},
        {"label": "Lite (0 kr. + 2,95 kr.)", "color": "#f59e0b", "type": "line"},
    ],
    "data": chart_data,
}

table = {
    "columns": ["Måned", "Forbrug", "Lite (0 kr.)", "Plus (99 kr.)", "City Spot (229 kr.)", "Bedste valg"],
    "rows": table_rows
}

output = {
    "success": True,
    "summary": summary_verdict,
    "kpis": kpis,
    "chart": chart,
    "table": table
}

print(json.dumps(output, ensure_ascii=False))
