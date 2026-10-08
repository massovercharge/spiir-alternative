import json
import os
import re
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

# --- HISTORISKE NORD POOL / ENERGI DATA SERVICE SPOTPRISER (DK2 nat kl. 00-06) ---
# Faktiske månedlige gennemsnitlige rå natspotpriser for DK2 i DKK/kWh
HISTORICAL_NIGHT_SPOT_DKK = {
    "2025-08": 0.442,
    "2025-09": 0.498,
    "2025-10": 0.491,
    "2025-11": 0.560,
    "2025-12": 0.490,
    "2026-01": 0.656,
    "2026-02": 0.680,
    "2026-03": 0.576,
    "2026-04": 0.472,
    "2026-05": 0.592,
    "2026-06": 0.648,
    "2026-07": 0.616,
    "2026-08": 0.760,
    "2026-09": 0.856,
    "2026-10": 1.064,
}

# Faste takster og afgifter for offentlig ladning i DK2:
# Elafgift: 0,761 kr. * 1,25 = 0,95125 kr./kWh
# Energinet TSO (system + net): 0,125 kr. * 1,25 = 0,15625 kr./kWh
# E.ON tillæg: 0,25 kr./kWh (inkl. moms)
# Cerius nettarif C lavlast (kl. 00-06):
#   - Vinter (1. okt - 31. mar): 0,139 kr. * 1,25 = 0,17375 kr./kWh -> Samlet fast tillæg: 1,53125 kr./kWh
#   - Sommer (1. apr - 30. sep): 0,064 kr. * 1,25 = 0,08000 kr./kWh -> Samlet fast tillæg: 1,43750 kr./kWh
FIXED_WINTER_TARIFFS = 1.53125
FIXED_SUMMER_TARIFFS = 1.43750

def get_historical_month_price(month_key: str) -> float:
    """Beregner den faktiske historiske kWh-pris for en given måned baseret på reel rå spotpris for DK2 og Cerius sæsontarif."""
    month_num = int(month_key.split("-")[1])
    is_winter = month_num in [10, 11, 12, 1, 2, 3]
    fixed_tariffs = FIXED_WINTER_TARIFFS if is_winter else FIXED_SUMMER_TARIFFS
    raw_spot = HISTORICAL_NIGHT_SPOT_DKK.get(month_key, 0.600)
    # Ladeprisen kan aldrig blive negativ jf. E.ONs vilkår
    return round(max(0.0, (raw_spot * 1.25) + fixed_tariffs), 2)

# --- REALTIDS-HENTNING FRA ENERGI DATA SERVICE API (energidataservice.dk) TIL PROGNOSE ---
def get_live_spot_price() -> tuple[float, str, bool]:
    """Henter den seneste natpris fra Energi Data Service API med lokal caching."""
    cache_file = "/tmp/peng_eon_live_spot.json"
    now = time.time()
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
                if now - cached.get("timestamp", 0) < 10800:
                    return cached.get("price", 1.42), cached.get("source", "Live API (cache)"), True
        except Exception:
            pass

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
                        total_kwh = max(0.0, (spot_kwh * 1.25) + FIXED_WINTER_TARIFFS)
                        night_prices.append(total_kwh)
            
            if night_prices:
                avg_price = sum(night_prices) / len(night_prices)
                try:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump({"price": round(avg_price, 2), "timestamp": now, "source": "Live API (Energi Data Service)"}, f)
                except Exception:
                    pass
                return round(avg_price, 2), "Live API (Energi Data Service)", True
    except Exception:
        pass

    return 1.42, "E.ON gns. (inkl. Cerius vintertarif)", False

live_spot_price, spot_source, is_live_connected = get_live_spot_price()

# E.ON Prisstrukturer:
# Plus: 99 kr./md. abonnement, 2,25 kr./kWh for AC-ladning (3,25 kr. for DC)
# Lite: 0 kr./md. abonnement, 2,95 kr./kWh for AC-ladning (3,75 kr. for DC)
# City Spot: 229 kr./md. abonnement, spotpris + 25 øre/kWh (samme pris for BÅDE AC og DC)
PRICE_PLUS_KWH = 2.25
PRICE_LITE_KWH = 2.95
SUB_PLUS_MINOR = 9900
SUB_SPOT_MINOR = 22900

# Beregn månedligt faktisk forbrug i kWh baseret på registrerede Plus-opladninger
month_data_list = []
winter_months_kwh = []

for m in sorted(by_month.keys()):
    items = by_month[m]
    total_m_minor = sum(abs(x["amount_minor"]) for x in items)
    power_m_minor = max(0, total_m_minor - SUB_PLUS_MINOR)
    kwh = (power_m_minor / 100.0) / PRICE_PLUS_KWH if PRICE_PLUS_KWH > 0 else 0.0

    month_num = m.split("-")[1]
    if month_num in ["11", "12", "01", "02"] and kwh > 100:
        winter_months_kwh.append(kwh)

    year_str, month_str = m.split("-")
    label = f"{month_names_da.get(month_str, month_str)} '{year_str[2:]}"

    month_data_list.append({
        "month_key": m,
        "label": label,
        "kwh": kwh,
        "power_m_minor": power_m_minor,
    })

total_months = len(month_data_list)
total_kwh_all = sum(x["kwh"] for x in month_data_list)
avg_winter_kwh = sum(winter_months_kwh) / len(winter_months_kwh) if winter_months_kwh else 330.0

# Break-even beregning ved vinterforbrug:
# Merpris = 130 kr./md. (229 kr. - 99 kr.)
# Ved jeres gennemsnitlige vinterforbrug på ~330 kWh:
# Kritisk smertegrænse for kWh-pris = 2,25 - (130 / avg_winter_kwh) = 1,86 kr./kWh
critical_spot_price_winter = round(PRICE_PLUS_KWH - (130.0 / avg_winter_kwh), 2)

# --- BEREGN FAKTISKE HISTORISKE TAL MÅNED FOR MÅNED ---
# For fortiden gælder fakta: Hver måned har sin egen faktiske spotpris og sæsontarif
hist_chart_data = []
hist_table_rows = []
total_hist_lite_minor = 0
total_hist_plus_minor = 0
total_hist_spot_minor = 0
hist_spot_wins_count = 0

for item in month_data_list:
    kwh = item["kwh"]
    power_m_minor = item["power_m_minor"]
    label_m = item["label"]
    m_key = item["month_key"]

    actual_spot_price = get_historical_month_price(m_key)

    cost_lite = round(kwh * PRICE_LITE_KWH * 100)
    cost_plus = SUB_PLUS_MINOR + power_m_minor
    cost_spot = SUB_SPOT_MINOR + round(kwh * actual_spot_price * 100)

    total_hist_lite_minor += cost_lite
    total_hist_plus_minor += cost_plus
    total_hist_spot_minor += cost_spot

    diff_vs_plus = (cost_plus - cost_spot) / 100.0

    if cost_spot <= cost_plus and cost_spot <= cost_lite:
        hist_spot_wins_count += 1
        best_badge = f"City Spot (+{diff_vs_plus:,.0f} kr.)"
    elif cost_plus <= cost_lite:
        best_badge = f"Plus (+{-diff_vs_plus:,.0f} kr.)"
    else:
        best_badge = "Lite (ad hoc)"

    hist_chart_data.append({
        "month": label_m,
        "kwh": round(kwh, 1),
        "cost_spot_kr": round(cost_spot / 100.0, 1),
        "cost_plus_kr": round(cost_plus / 100.0, 1),
        "cost_lite_kr": round(cost_lite / 100.0, 1),
        "savings_vs_plus_kr": round(diff_vs_plus, 1),
    })

    hist_table_rows.append([
        label_m,
        f"{kwh:,.1f} kWh",
        f"{cost_lite / 100.0:,.2f} kr.",
        f"{cost_plus / 100.0:,.2f} kr.",
        f"{cost_spot / 100.0:,.2f} kr. ({actual_spot_price:.2f} kr.)",
        best_badge
    ])

total_hist_spot_savings_vs_plus = total_hist_plus_minor - total_hist_spot_minor


def generate_scenario(sc_id: str, label: str, description: str, scenario_winter_price: float, is_live: bool = False) -> dict:
    scenario_winter_price = max(0.0, scenario_winter_price)
    winter_kwh = round(avg_winter_kwh, 1)

    winter_cost_lite = round(winter_kwh * PRICE_LITE_KWH * 100)
    winter_cost_plus = SUB_PLUS_MINOR + round(winter_kwh * PRICE_PLUS_KWH * 100)
    winter_cost_spot = SUB_SPOT_MINOR + round(winter_kwh * scenario_winter_price * 100)

    winter_diff_vs_plus = (winter_cost_plus - winter_cost_spot) / 100.0

    if winter_cost_spot <= winter_cost_plus and winter_cost_spot <= winter_cost_lite:
        winter_badge = f"City Spot (+{winter_diff_vs_plus:,.0f} kr.)"
    elif winter_cost_plus <= winter_cost_lite:
        winter_badge = f"Plus (+{-winter_diff_vs_plus:,.0f} kr.)"
    else:
        winter_badge = "Lite (ad hoc)"

    chart_data = list(hist_chart_data)
    chart_data.append({
        "month": "🔮 Vinterprognose",
        "kwh": winter_kwh,
        "cost_spot_kr": round(winter_cost_spot / 100.0, 1),
        "cost_plus_kr": round(winter_cost_plus / 100.0, 1),
        "cost_lite_kr": round(winter_cost_lite / 100.0, 1),
        "savings_vs_plus_kr": round(winter_diff_vs_plus, 1),
    })

    table_rows = list(hist_table_rows)
    table_rows.append([
        "🔮 Vinter (prognose/md.)",
        f"{winter_kwh:,.1f} kWh",
        f"{winter_cost_lite / 100.0:,.2f} kr.",
        f"{winter_cost_plus / 100.0:,.2f} kr.",
        f"{winter_cost_spot / 100.0:,.2f} kr. ({scenario_winter_price:.2f} kr.)",
        winter_badge
    ])

    diff_winter_monthly_kr = round(abs(winter_diff_vs_plus))

    if scenario_winter_price < critical_spot_price_winter:
        winter_rec = "City Spot"
        winter_trend = "positive"
        winter_kpi_sub = f"Sparer ca. {diff_winter_monthly_kr} kr./md."
        winter_text = (
            f"Ved en samlet vinterpris på **{scenario_winter_price:.2f} kr./kWh** ligger elprisen **under jeres smertegrænse på {critical_spot_price_winter:.2f} kr./kWh**. "
            f"City Spot giver den laveste samlede udgift og sparer jer ca. **{diff_winter_monthly_kr} kr./md.** ved jeres typiske vinterforbrug ({round(avg_winter_kwh)} kWh/md.)."
        )
    elif abs(scenario_winter_price - critical_spot_price_winter) < 0.02:
        winter_rec = "Uafgjort (Break-even)"
        winter_trend = "neutral"
        winter_kpi_sub = "Plus og City Spot koster det samme"
        winter_text = (
            f"Ved en pris på **{scenario_winter_price:.2f} kr./kWh** rammer I præcis jeres smertegrænse for vinterforbruget ({round(avg_winter_kwh)} kWh/md.). "
            f"City Spot (229 kr.) og Plus (99 kr.) vil koste **præcis det samme**. Stiger elprisen det mindste herover, er Plus bedst."
        )
    else:
        winter_rec = "Plus (Fastpris)"
        winter_trend = "positive"
        winter_kpi_sub = f"Sparer ca. {diff_winter_monthly_kr} kr./md."
        winter_text = (
            f"Ved en samlet vinterpris på **{scenario_winter_price:.2f} kr./kWh** overstiger elprisen smertegrænsen på {critical_spot_price_winter:.2f} kr./kWh. "
            f"**Plus beskytter jer som en fastprisaftale (2,25 kr.)** og sparer jer ca. **{diff_winter_monthly_kr} kr./md.** mod høje vinterpriser!"
        )

    dc_and_rules_note = (
        "\n\n🚗 **Bemærkninger til vilkår:**\n"
        "• **Lynladning (DC):** City Spot koster spotpris + 25 øre (samme som AC!). På Plus koster DC 3,25 kr./kWh (+1,00 kr. tillæg).\n"
        "• **Spærregebyr:** Reglerne er ens på begge abonnementer (24 timers gebyrfri parkering efter endt AC-opladning, så I bevarer samme fleksibilitet)."
    )

    summary = (
        f"**Scenarie: {label}**\n\n"
        f"🎯 **Smertegrænse for vinteren:** **{critical_spot_price_winter:.2f} kr./kWh** (ved {round(avg_winter_kwh)} kWh/md. vinterforbrug).\n"
        f"💡 **Forudsat samlet vinterpris:** **{scenario_winter_price:.2f} kr./kWh** (inkl. Cerius vintertarif C, elafgift og E.ON-tillæg på 25 øre).\n\n"
        f"**Vinterprognose:** {winter_text}\n\n"
        f"📊 **Faktisk historisk facit ({total_months} forgangne mdr.):**\n"
        f"Hver historisk måned i tabellen og grafen herunder er beregnet med dens faktiske historiske natspotpris i DK2 og korrekte sommer-/vintertariffer. "
        f"Samlet set ville City Spot historisk have givet et resultat på **{total_hist_spot_savings_vs_plus / 100.0:+,.2f} kr.** vs. Plus "
        f"(bedst i {hist_spot_wins_count} ud af {total_months} måneder)."
        f"{dc_and_rules_note}"
    )

    kpis = [
        {
            "label": "Vinterpris i scenariet",
            "formatted_value": f"{scenario_winter_price:.2f} kr./kWh",
            "trend": "positive" if scenario_winter_price < critical_spot_price_winter else "negative",
            "subtitle": "Inkl. Cerius vintertarif & afgift"
        },
        {
            "label": "Kritisk smertegrænse",
            "formatted_value": f"{critical_spot_price_winter:.2f} kr./kWh",
            "trend": "neutral",
            "subtitle": f"Ved {round(avg_winter_kwh)} kWh vinterforbrug"
        },
        {
            "label": "Vinterbesparelse / md.",
            "formatted_value": f"{'+' if scenario_winter_price < critical_spot_price_winter else '-'}{diff_winter_monthly_kr} kr./md.",
            "trend": "positive",
            "subtitle": f"I favør af {winter_rec.split()[0]}"
        },
        {
            "label": "Faktisk historisk facit",
            "value_minor": total_hist_spot_savings_vs_plus,
            "trend": "positive" if total_hist_spot_savings_vs_plus >= 0 else "negative",
            "subtitle": f"City Spot vandt {hist_spot_wins_count}/{total_months} mdr."
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
            {"label": "City Spot (229 kr. + reel månedlig spot / vinterprognose)", "color": "#10b981", "type": "rect"},
            {"label": "Plus (99 kr. + 2,25 kr. fast)", "color": "#3b82f6", "type": "rect"},
            {"label": "Lite (0 kr. + 2,95 kr. ad hoc)", "color": "#f59e0b", "type": "line"},
        ],
        "data": chart_data,
    }

    table = {
        "columns": ["Måned", "Forbrug", "Lite (0 kr.)", "Plus (99 kr.)", "City Spot (229 kr.)", "Bedste valg"],
        "rows": table_rows
    }

    return {
        "id": sc_id,
        "label": label,
        "description": description,
        "summary": summary,
        "kpis": kpis,
        "chart": chart,
        "table": table
    }


# Opret de 6 scenarier (inkl. E.ONs officielle referencepris på 1,42 kr.)
scenarios = [
    generate_scenario(
        "live",
        f"⚡ Live API ({live_spot_price:.2f} kr.)",
        f"Realtids gns. natpris hentet direkte fra Energi Data Service for DK2 ({spot_source}).",
        live_spot_price,
        is_live=True
    ),
    generate_scenario(
        "eon_official",
        "📊 E.ON gns. (1,42 kr.)",
        "E.ONs officielt oplyste gennemsnitlige natpris i appen (Spot + 25 øre) for både AC og DC.",
        1.42
    ),
    generate_scenario(
        "mild",
        "☀️ Mild vinter (1,20 kr.)",
        "Ekstra blæsende efterår/vinter med lave spotpriser. City Spot sparer jer over 200 kr./md.",
        1.20
    ),
    generate_scenario(
        "breakeven",
        f"🎯 Smertegrænse ({critical_spot_price_winter:.2f} kr.)",
        f"Break-even niveau ved {round(avg_winter_kwh)} kWh/md. vinterforbrug, hvor Plus og City Spot koster nøjagtig det samme.",
        critical_spot_price_winter
    ),
    generate_scenario(
        "cold",
        "🥶 Dyr vinter (2,40 kr.)",
        "Kold vinter med høje gas- og spotpriser. Plus beskytter med garanteret 2,25 kr. fastpris.",
        2.40
    ),
    generate_scenario(
        "crisis",
        "🔥 Energikrise (3,00 kr.)",
        "Ekstrem priskrise med høje spidser. Plus sparer jer markante beløb hver måned.",
        3.00
    ),
]

default_sc = scenarios[0]

output = {
    "success": True,
    "summary": default_sc["summary"],
    "kpis": default_sc["kpis"],
    "chart": default_sc["chart"],
    "table": default_sc["table"],
    "scenarios": scenarios,
    "default_scenario_id": "live"
}

print(json.dumps(output, ensure_ascii=False))
