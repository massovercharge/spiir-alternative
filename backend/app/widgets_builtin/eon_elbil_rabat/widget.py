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

# Group transactions by month (from August 2025 onwards, where subscription is active)
by_month = defaultdict(list)
for r in rows:
    b_date = r["booking_date"]
    m = b_date[:7]
    if m >= "2025-08":
        by_month[m].append(r)

month_names_da = {
    "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
    "05": "Maj", "06": "Jun", "07": "Jul", "08": "Aug",
    "09": "Sep", "10": "Okt", "11": "Nov", "12": "Dec"
}

total_power_minor = 0
total_sub_minor = 0
total_savings_minor = 0
total_net_minor = 0
profitable_months = 0
total_months = len(by_month)

chart_data = []
table_rows = []

for m in sorted(by_month.keys()):
    items = by_month[m]
    total_m_minor = sum(abs(x["amount_minor"]) for x in items)
    sub_m_minor = 9900  # 99 kr.
    power_m_minor = max(0, total_m_minor - sub_m_minor)

    # 20% discount on standard price: paid = 80%, discount = 20% = power / 0.8 * 0.2 = power * 0.25
    savings_m_minor = round(power_m_minor * 0.25)
    net_m_minor = savings_m_minor - sub_m_minor

    total_power_minor += power_m_minor
    total_sub_minor += sub_m_minor
    total_savings_minor += savings_m_minor
    total_net_minor += net_m_minor

    if net_m_minor > 0:
        profitable_months += 1

    year_str, month_str = m.split("-")
    label = f"{month_names_da.get(month_str, month_str)} '{year_str[2:]}"

    # Green if savings >= 99 kr (net profit), Red if savings < 99 kr (net loss)
    bar_color = "#10b981" if net_m_minor >= 0 else "#ef4444"

    chart_data.append({
        "month": label,
        "savings_kr": round(savings_m_minor / 100.0, 1),
        "cost_kr": 99,
        "power_kr": round(power_m_minor / 100.0, 1),
        "net_kr": round(net_m_minor / 100.0, 1),
        "savings_kr_color": bar_color,
        "color": bar_color,
    })

    table_rows.append([
        label,
        f"{total_m_minor / 100.0:,.2f} kr.",
        "99,00 kr.",
        f"{power_m_minor / 100.0:,.2f} kr.",
        f"{savings_m_minor / 100.0:,.2f} kr.",
        f"{net_m_minor / 100.0:+,.2f} kr."
    ])

net_sign = "+" if total_net_minor >= 0 else ""
summary = (
    f"Konklusion: {'JA, abonnementet tjener sig hjem!' if total_net_minor > 0 else 'Nej, abonnementet har givet underskud.'} "
    f"Over de seneste {total_months} måneder har I opnået en samlet nettobesparelse på {net_sign}{total_net_minor / 100.0:,.2f} kr. "
    f"Abonnementet var profitabelt i {profitable_months} ud af {total_months} måneder."
)

kpis = [
    {
        "label": "Samlet nettobesparelse",
        "value_minor": total_net_minor,
        "trend": "positive" if total_net_minor >= 0 else "negative",
        "subtitle": "Rabat minus 99 kr./md."
    },
    {
        "label": "Gevinstmåneder",
        "formatted_value": f"{profitable_months} / {total_months} mdr.",
        "trend": "positive" if profitable_months > total_months / 2 else "neutral",
        "subtitle": "Måneder med overskud"
    },
    {
        "label": "Betalt for el-opladning",
        "value_minor": total_power_minor,
        "trend": "neutral",
        "subtitle": "Strøm ekskl. abonnement"
    },
    {
        "label": "Månedlig break-even",
        "value_minor": 39600,
        "trend": "neutral",
        "subtitle": "Forbrugsgrænse for overskud"
    }
]

chart = {
    "chart_type": "composed",
    "x_axis": "month",
    "series": [
        {"key": "savings_kr", "label": "Opnået rabat (kr.)", "color": "#10b981", "type": "bar"},
        {"key": "cost_kr", "label": "Abonnementspris (99 kr.)", "color": "#fbbf24", "type": "line"}
    ],
    "data": chart_data
}

table = {
    "columns": ["Måned", "Total betalt", "Abonnement", "Strøm betalt", "Opnået rabat", "Nettogevinst"],
    "rows": table_rows
}

output = {
    "success": True,
    "summary": summary,
    "kpis": kpis,
    "chart": chart,
    "table": table
}

print(json.dumps(output, ensure_ascii=False))
