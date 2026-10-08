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

# --- REALTIDS-HENTNING FRA ENERGI DATA SERVICE API TIL TREND-SCENARIE ---
def get_live_spot_price() -> tuple[float, str, bool]:
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
avg_monthly_kwh = total_kwh_all / total_months if total_months > 0 else 238.0

# --- BEREGNING AF MATEMATISK BREAK-EVEN FAKTOR ---
# Finder præcis den faktor på spotpriserne, hvor Total Plus == Total City Spot over hele perioden
tot_plus_all = 0
tot_spot_sub_fee = total_months * SUB_SPOT_MINOR
tot_spot_fixed_energy_minor = 0
tot_spot_variable_weight = 0

for item in month_data_list:
    kwh = item["kwh"]
    pwr_m = item["power_m_minor"]
    m_k = item["month_key"]
    tot_plus_all += (SUB_PLUS_MINOR + pwr_m)

    m_num = int(m_k.split("-")[1])
    is_w = m_num in [10, 11, 12, 1, 2, 3]
    fixed_t = FIXED_WINTER_TARIFFS if is_w else FIXED_SUMMER_TARIFFS
    raw_s = HISTORICAL_NIGHT_SPOT_DKK.get(m_k, 0.600)

    tot_spot_fixed_energy_minor += round(kwh * fixed_t * 100)
    tot_spot_variable_weight += (kwh * raw_s * 125.0)

if tot_spot_variable_weight > 0:
    breakeven_factor = round((tot_plus_all - tot_spot_sub_fee - tot_spot_fixed_energy_minor) / tot_spot_variable_weight, 2)
else:
    breakeven_factor = 1.0

breakeven_pct = round((breakeven_factor - 1.0) * 100)

# Beregn Live API faktor
hist_raw_spots = [HISTORICAL_NIGHT_SPOT_DKK.get(x["month_key"], 0.600) for x in month_data_list]
avg_hist_raw_spot = sum(hist_raw_spots) / len(hist_raw_spots) if hist_raw_spots else 0.627
live_raw_spot = max(0.0, (live_spot_price - FIXED_WINTER_TARIFFS) / 1.25)
live_factor = round(live_raw_spot / avg_hist_raw_spot, 2) if avg_hist_raw_spot > 0 else 1.0
# Begræns live faktor til fornuftigt spænd
live_factor = max(0.5, min(2.5, live_factor))
live_pct = round((live_factor - 1.0) * 100)


def generate_factor_scenario(sc_id: str, label: str, description: str, factor: float) -> dict:
    pct_change = round((factor - 1.0) * 100)

    total_lite_minor = 0
    total_plus_minor = 0
    total_spot_minor = 0
    spot_wins = 0

    winter_cost_plus_minor = 0
    winter_cost_spot_minor = 0

    chart_data = []
    table_rows = []
    scenario_kwh_prices = []

    for item in month_data_list:
        kwh = item["kwh"]
        power_m_minor = item["power_m_minor"]
        label_m = item["label"]
        m_key = item["month_key"]

        month_num = int(m_key.split("-")[1])
        is_winter = month_num in [10, 11, 12, 1, 2, 3]
        fixed_tariffs = FIXED_WINTER_TARIFFS if is_winter else FIXED_SUMMER_TARIFFS

        base_raw_spot = HISTORICAL_NIGHT_SPOT_DKK.get(m_key, 0.600)
        # Forskyd spotprisen med scenariets faktor
        scenario_raw_spot = base_raw_spot * factor
        # Samlet kWh-pris (kan aldrig blive negativ jf. E.ON regler)
        month_kwh_price = round(max(0.0, (scenario_raw_spot * 1.25) + fixed_tariffs), 2)
        scenario_kwh_prices.append(month_kwh_price)

        cost_lite = round(kwh * PRICE_LITE_KWH * 100)
        cost_plus = SUB_PLUS_MINOR + power_m_minor
        cost_spot = SUB_SPOT_MINOR + round(kwh * month_kwh_price * 100)

        total_lite_minor += cost_lite
        total_plus_minor += cost_plus
        total_spot_minor += cost_spot

        if month_num in [11, 12, 1, 2]:
            winter_cost_plus_minor += cost_plus
            winter_cost_spot_minor += cost_spot

        diff_vs_plus = (cost_plus - cost_spot) / 100.0

        if cost_spot <= cost_plus and cost_spot <= cost_lite:
            spot_wins += 1
            best_badge = f"City Spot (+{diff_vs_plus:,.0f} kr.)"
        elif cost_plus <= cost_lite:
            best_badge = f"Plus (+{-diff_vs_plus:,.0f} kr.)"
        else:
            best_badge = "Lite (ad hoc)"

        chart_data.append({
            "month": label_m,
            "kwh": round(kwh, 1),
            "cost_spot_kr": round(cost_spot / 100.0, 1),
            "cost_plus_kr": round(cost_plus / 100.0, 1),
            "cost_lite_kr": round(cost_lite / 100.0, 1),
            "savings_vs_plus_kr": round(diff_vs_plus, 1),
        })

        table_rows.append([
            label_m,
            f"{kwh:,.1f} kWh",
            f"{cost_lite / 100.0:,.2f} kr.",
            f"{cost_plus / 100.0:,.2f} kr.",
            f"{cost_spot / 100.0:,.2f} kr. ({month_kwh_price:.2f} kr.)",
            best_badge
        ])

    avg_sc_price = sum(scenario_kwh_prices) / len(scenario_kwh_prices) if scenario_kwh_prices else 0.0
    total_savings_vs_plus = (total_plus_minor - total_spot_minor) / 100.0
    winter_savings_vs_plus = (winter_cost_plus_minor - winter_cost_spot_minor) / 100.0

    if total_savings_vs_plus >= 0:
        overall_text = (
            f"Ved dette prisniveau ({pct_change:+.0f} % forskydning, gns. {avg_sc_price:.2f} kr./kWh) "
            f"ville City Spot give et samlet overskud på **+{total_savings_vs_plus:,.2f} kr.** i forhold til Plus "
            f"(billigst i {spot_wins} ud af {total_months} måneder)."
        )
    else:
        overall_text = (
            f"Ved dette prisniveau ({pct_change:+.0f} % forskydning, gns. {avg_sc_price:.2f} kr./kWh) "
            f"er Plus billigst samlet set og sparer jer for **+{-total_savings_vs_plus:,.2f} kr.** i forhold til City Spot."
        )

    if winter_savings_vs_plus >= 0:
        winter_text = f"I de 4 koldeste vintermåneder (nov–feb) sparer City Spot jer **+{winter_savings_vs_plus:,.0f} kr.** samlet."
    else:
        winter_text = f"I de 4 koldeste vintermåneder (nov–feb) beskytter Plus jer og sparer jer **+{-winter_savings_vs_plus:,.0f} kr.** samlet mod vinterkulde."

    dc_and_rules_note = (
        "\n\n🚗 **Bemærkninger til vilkår:**\n"
        "• **Lynladning (DC):** City Spot koster spotpris + 25 øre (samme som AC!). På Plus koster DC 3,25 kr./kWh (+1,00 kr. tillæg).\n"
        "• **Spærregebyr:** Reglerne er ens på begge abonnementer (24 timers gebyrfri parkering efter endt AC-opladning, så I bevarer samme fleksibilitet)."
    )

    summary = (
        f"**Scenarie: {label}**\n\n"
        f"📈 **Model:** Beregningen tager udgangspunkt i jeres **faktiske månedlige kørselsmønster og historiske natspotpriser for DK2**, "
        f"men forskyder spotprisen med **{pct_change:+.0f} %** (faktor {factor:.2f}) svarende til en gns. natpris på **{avg_sc_price:.2f} kr./kWh**.\n\n"
        f"**Samlet konklusion:** {overall_text}\n\n"
        f"❄️ **Vintermånederne (Nov–Feb):** {winter_text}\n\n"
        f"🎯 **Smertegrænse:** Hvis spotpriserne stiger over {breakeven_pct:+.0f} % (faktor {breakeven_factor:.2f}), tipper balancen til Plus' fordel."
        f"{dc_and_rules_note}"
    )

    kpis = [
        {
            "label": "Prisforskydning",
            "formatted_value": f"{pct_change:+.0f} %",
            "trend": "positive" if factor <= 1.0 else "negative",
            "subtitle": f"Gns. natpris: {avg_sc_price:.2f} kr./kWh"
        },
        {
            "label": "Kritisk smertegrænse",
            "formatted_value": f"{breakeven_pct:+.0f} %",
            "trend": "neutral",
            "subtitle": f"Break-even ved faktor {breakeven_factor:.2f}"
        },
        {
            "label": "Samlet resultat (City Spot)",
            "value_minor": round(total_savings_vs_plus * 100),
            "trend": "positive" if total_savings_vs_plus >= 0 else "negative",
            "subtitle": f"Bedst i {spot_wins}/{total_months} måneder"
        },
        {
            "label": "Vinterresultat (Nov-Feb)",
            "value_minor": round(winter_savings_vs_plus * 100),
            "trend": "positive" if winter_savings_vs_plus >= 0 else "negative",
            "subtitle": f"I de 4 vintermåneder"
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
            {"label": f"City Spot (229 kr. + forskudt månedlig spot {pct_change:+.0f} %)", "color": "#10b981", "type": "rect"},
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


# Opret de 6 faktor-scenarier
scenarios = [
    generate_factor_scenario(
        "baseline",
        "📊 Historisk baseline (0 %)",
        "Faktiske månedlige natspotpriser for DK2 og sæsontariffer (ingen forskydning).",
        1.0
    ),
    generate_factor_scenario(
        "mild",
        "☀️ Mild vinter (-20 %)",
        "Simulerer et ekstra mildt og blæsende år med 20 % lavere spotpriser.",
        0.80
    ),
    generate_factor_scenario(
        "live",
        f"⚡ Live trend ({live_pct:+.0f} %)",
        f"Forskyder priserne med {live_pct:+.0f} % baseret på den seneste realtids natpris ({live_spot_price:.2f} kr./kWh).",
        live_factor
    ),
    generate_factor_scenario(
        "breakeven",
        f"🎯 Smertegrænse ({breakeven_pct:+.0f} %)",
        f"Det præcise stigningsniveau ({breakeven_pct:+.0f} % på spotprisen), hvor City Spot og Plus koster nøjagtig det samme.",
        breakeven_factor
    ),
    generate_factor_scenario(
        "cold",
        "🥶 Kold vinter (+25 %)",
        "Simulerer en kold vinter med højere efterspørgsel og 25 % højere elpriser.",
        1.25
    ),
    generate_factor_scenario(
        "crisis",
        "🔥 Energikrise (+60 %)",
        "Simulerer et kraftigt prischok (+60 % på spotprisen). Plus beskytter markant.",
        1.60
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
    "default_scenario_id": "baseline"
}

print(json.dumps(output, ensure_ascii=False))
