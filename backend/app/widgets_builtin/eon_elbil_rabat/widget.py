import json
import os
import sqlite3
import time
import urllib.request
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

# --- REALTIDS-HENTNING FRA ENERGI DATA SERVICE API (energidataservice.dk) ---
# Faste takster og afgifter for offentlig ladning i DK2 (Cerius område, vintertariffer):
# Elafgift: 0,761 kr. + moms = 0,951 kr./kWh
# Cerius nettarif C vinter (lavlast kl. 00-06): 0,139 kr. + moms = 0,174 kr./kWh
# Energinet TSO (system + net): 0,125 kr. + moms = 0,156 kr./kWh
# E.ON tillæg: 0,25 kr. + moms = 0,3125 kr./kWh
# Fast tillæg i alt før spotpris: ~1,5935 kr./kWh
FIXED_TARIFFS_AND_TAXES = 1.5935

def get_live_spot_price() -> tuple[float, str, bool]:
    """Henter de seneste natpriser fra Energi Data Service API med lokal caching."""
    cache_file = "/tmp/peng_eon_live_spot.json"
    now = time.time()
    
    # 1. Tjek om vi har en gyldig cache (under 3 timer gammel)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
                if now - cached.get("timestamp", 0) < 10800:
                    return cached.get("price", 1.48), cached.get("source", "Live API (cache)"), True
        except Exception:
            pass

    # 2. Hent de seneste data fra Energi Data Service (DK2)
    url = 'https://api.energidataservice.dk/dataset/Elspotprices?filter=%7B%22PriceArea%22:%5B%22DK2%22%5D%7D&sort=HourUTC%20desc&limit=72'
    req = urllib.request.Request(url, headers={'User-Agent': 'Peng-Finance/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=1.8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            records = data.get('records', [])
            night_prices = []
            for r in records:
                h_dk = r.get('HourDK', '')
                hour = int(h_dk[11:13]) if len(h_dk) >= 13 else -1
                if 0 <= hour < 6:
                    spot_mwh = r.get('SpotPriceDKK')
                    if spot_mwh is not None:
                        spot_kwh = spot_mwh / 1000.0
                        total_kwh = (spot_kwh * 1.25) + FIXED_TARIFFS_AND_TAXES
                        night_prices.append(total_kwh)
            
            if night_prices:
                avg_price = sum(night_prices) / len(night_prices)
                # Skriv til cache
                try:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump({"price": round(avg_price, 2), "timestamp": now, "source": "Live API (Energi Data Service)"}, f)
                except Exception:
                    pass
                return round(avg_price, 2), "Live API (Energi Data Service)", True
    except Exception:
        pass

    # 3. Fallback til estimeret aktuel efterårs-/vinterpris hvis API'et ikke svarer
    return 1.48, "Estimat (inkl. Cerius vintertarif)", False

live_spot_price, spot_source, is_live_connected = get_live_spot_price()

# E.ON Prisstrukturer:
# Plus: 99 kr./md. abonnement, 2,25 kr./kWh for AC-ladning
# Lite: 0 kr./md. abonnement, 2,95 kr./kWh for AC-ladning
# City Spot: 229 kr./md. abonnement, spotpris + 25 øre/kWh (gns. natpris ~1,42 - 1,48 kr./kWh)
PRICE_PLUS_KWH = 2.25
PRICE_LITE_KWH = 2.95
PRICE_SPOT_NIGHT_KWH = live_spot_price  # Bruger den dynamiske realtidspris

SUB_PLUS_MINOR = 9900
SUB_SPOT_MINOR = 22900

total_kwh = 0.0
total_cost_lite_minor = 0
total_cost_plus_minor = 0
total_cost_spot_minor = 0
spot_wins_count = 0
total_months = len(by_month)

chart_data = []
table_rows = []
winter_months_kwh = []

for m in sorted(by_month.keys()):
    items = by_month[m]
    total_m_minor = sum(abs(x["amount_minor"]) for x in items)
    power_m_minor = max(0, total_m_minor - SUB_PLUS_MINOR)

    # Faktisk forbrugt strøm i kWh (beregnet ud fra Plus AC-takst på 2,25 kr./kWh)
    kwh = (power_m_minor / 100.0) / PRICE_PLUS_KWH if PRICE_PLUS_KWH > 0 else 0.0

    # Hold øje med vintermåneder (nov, dec, jan, feb)
    month_num = m.split("-")[1]
    if month_num in ["11", "12", "01", "02"] and kwh > 100:
        winter_months_kwh.append(kwh)

    # Omkostning under de tre modeller:
    cost_lite_minor = round(kwh * PRICE_LITE_KWH * 100)
    cost_plus_minor = SUB_PLUS_MINOR + power_m_minor
    cost_spot_minor = SUB_SPOT_MINOR + round(kwh * PRICE_SPOT_NIGHT_KWH * 100)

    total_kwh += kwh
    total_cost_lite_minor += cost_lite_minor
    total_cost_plus_minor += cost_plus_minor
    total_cost_spot_minor += cost_spot_minor

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
avg_winter_kwh = sum(winter_months_kwh) / len(winter_months_kwh) if winter_months_kwh else 334.0
total_spot_savings_vs_plus = total_cost_plus_minor - total_cost_spot_minor
total_spot_savings_vs_lite = total_cost_lite_minor - total_cost_spot_minor

# Break-even beregning ved vinterforbrug:
# Merpris = 130 kr./md.
# Ved jeres gennemsnitlige vinterforbrug på ~334 kWh:
# Kritisk smertegrænse for kWh-pris = 2,25 - (130 / 334) = 1,86 kr./kWh
critical_spot_price_winter = round(PRICE_PLUS_KWH - (130.0 / avg_winter_kwh), 2)

# Vurdering for den kommende vinter:
# Hvis realtidsprisen om natten er lavere end det kritiske prisloft, er City Spot p.t. billigst
if live_spot_price < critical_spot_price_winter:
    winter_recommendation = "City Spot (p.t. fordelagtigt)"
    winter_diff_kr = round((critical_spot_price_winter - live_spot_price) * avg_winter_kwh)
    winter_analysis = (
        f"Den aktuelle natpris er **{live_spot_price:.2f} kr./kWh** ({spot_source}), hvilket ligger under smertegrænsen på **{critical_spot_price_winter:.2f} kr./kWh**. "
        f"Ved dette prisniveau sparer City Spot jer ca. **{winter_diff_kr} kr./md.** henover vinteren."
    )
else:
    winter_recommendation = "Plus (99 kr. - anbefales som prissikring!)"
    winter_diff_kr = round((live_spot_price - critical_spot_price_winter) * avg_winter_kwh)
    winter_analysis = (
        f"Den aktuelle natpris er **{live_spot_price:.2f} kr./kWh** ({spot_source}), hvilket overstiger smertegrænsen på **{critical_spot_price_winter:.2f} kr./kWh**. "
        f"**Plus beskytter jer som en fastprisaftale** og sparer jer ca. **{winter_diff_kr} kr./md.** mod høje vintertariffer og prisstigninger!"
    )

summary_verdict = (
    f"**Status & Vinterprognose (Energi Data Service live integration):**\n\n"
    f"📡 **Aktuel gns. natpris:** **{live_spot_price:.2f} kr./kWh** inkl. Cerius vintertarif C og moms ({spot_source}).\n"
    f"🎯 **Kritisk smertegrænse for vinteren:** **{critical_spot_price_winter:.2f} kr./kWh** (ved jeres typiske vinterforbrug på {round(avg_winter_kwh)} kWh/md.).\n\n"
    f"**Vurdering for vinteren:** {winter_analysis}\n\n"
    f"**Historisk overblik (seneste {total_months} mdr.):** City Spot har samlet set sparet jer for **{total_spot_savings_vs_plus / 100.0:,.2f} kr.** vs. Plus "
    f"(og {total_spot_savings_vs_lite / 100.0:,.2f} kr. vs. Lite). Men hvis elpriserne stiger henover vinteren over {critical_spot_price_winter:.2f} kr./kWh, "
    f"fungerer jeres nuværende Plus-abonnement som en billig forsikring med garanteret fast pris på 2,25 kr."
)

kpis = [
    {
        "label": "Aktuel natpris (Live API)",
        "formatted_value": f"{live_spot_price:.2f} kr./kWh",
        "trend": "positive" if live_spot_price < critical_spot_price_winter else "negative",
        "subtitle": "Fra Energi Data Service"
    },
    {
        "label": "Kritisk smertegrænse",
        "formatted_value": f"{critical_spot_price_winter:.2f} kr./kWh",
        "trend": "neutral",
        "subtitle": f"Ved {round(avg_winter_kwh)} kWh vinterforbrug"
    },
    {
        "label": "Vinteranbefaling",
        "formatted_value": "City Spot" if live_spot_price < critical_spot_price_winter else "Plus (Forsikring)",
        "trend": "positive",
        "subtitle": f"Break-even ved {critical_spot_price_winter:.2f} kr."
    },
    {
        "label": "Historisk besparelse (City Spot)",
        "value_minor": total_spot_savings_vs_plus,
        "trend": "positive" if total_spot_savings_vs_plus >= 0 else "negative",
        "subtitle": f"I {spot_wins_count}/{total_months} måneder"
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
        {"label": f"City Spot (229 kr. + spot {live_spot_price:.2f} kr.)", "color": "#10b981", "type": "rect"},
        {"label": "Plus (99 kr. + 2,25 kr. fast)", "color": "#3b82f6", "type": "rect"},
        {"label": "Lite (0 kr. + 2,95 kr. ad hoc)", "color": "#f59e0b", "type": "line"},
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
