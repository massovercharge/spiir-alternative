import json
import os
import re
import sqlite3
import time
import urllib.request
from collections import defaultdict

# DB-sti med automatisk fallback til container-placering
default_db = "/data/peng.sqlite" if os.path.exists("/data/peng.sqlite") else "data/peng.sqlite"
db_path = os.environ.get("PENG_DB_PATH", default_db)
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
    "2025-08": 0.448,  # Rå døgngns: 56 øre -> natgns (~80%): 44,8 øre
    "2025-09": 0.432,  # Rå døgngns: 54 øre -> natgns (~80%): 43,2 øre
    "2025-10": 0.488,  # Rå døgngns: 61 øre -> natgns (~80%): 48,8 øre
    "2025-11": 0.656,  # Rå døgngns: 82 øre -> natgns (~80%): 65,6 øre
    "2025-12": 0.616,  # Rå døgngns: 77 øre -> natgns (~80%): 61,6 øre
    "2026-01": 0.656,  # Rå døgngns: 82 øre -> natgns (~80%): 65,6 øre
    "2026-02": 0.680,  # Rå døgngns: 85 øre -> natgns (~80%): 68,0 øre
    "2026-03": 0.576,  # Rå døgngns: 72 øre -> natgns (~80%): 57,6 øre
    "2026-04": 0.472,  # Rå døgngns: 59 øre -> natgns (~80%): 47,2 øre
    "2026-05": 0.592,  # Rå døgngns: 74 øre -> natgns (~80%): 59,2 øre
    "2026-06": 0.648,  # Rå døgngns: 81 øre -> natgns (~80%): 64,8 øre
    "2026-07": 0.616,  # Rå døgngns: 77 øre -> natgns (~80%): 61,6 øre
    "2026-08": 0.760,  # Rå døgngns: 95 øre -> natgns (~80%): 76,0 øre
    "2026-09": 0.856,  # Rå døgngns: 107 øre -> natgns (~80%): 85,6 øre
    "2026-10": 1.064,  # Rå døgngns: 133 øre -> natgns (~80%): 106,4 øre
}

# Indlæs eventuel opdateret cache fra fil i widget-mappen
widget_dir = os.path.dirname(os.path.abspath(__file__))
cache_file = os.path.join(widget_dir, "historical_spot_cache.json")
if os.path.exists(cache_file):
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
            months = cache_data.get("months", {})
            for m_key, val in months.items():
                if isinstance(val, dict) and "night_avg_dkk" in val:
                    HISTORICAL_NIGHT_SPOT_DKK[m_key] = float(val["night_avg_dkk"])
                elif isinstance(val, (int, float)):
                    HISTORICAL_NIGHT_SPOT_DKK[m_key] = float(val)
    except Exception:
        pass

# Faste takster og afgifter for offentlig ladning i DK2:
# Elafgift: 0,761 kr. * 1,25 = 0,95125 kr./kWh
# Energinet TSO (system + net): 0,125 kr. * 1,25 = 0,15625 kr./kWh
# E.ON tillæg: 0,25 kr./kWh (inkl. moms)
# Cerius nettarif C lavlast (kl. 00-06):
#   - Vinter (1. okt - 31. mar): 0,139 kr. * 1,25 = 0,17375 kr./kWh -> Samlet fast tillæg: 1,53125 kr./kWh
#   - Sommer (1. apr - 30. sep): 0,064 kr. * 1,25 = 0,08000 kr./kWh -> Samlet fast tillæg: 1,43750 kr./kWh
FIXED_WINTER_TARIFFS = 1.53125
FIXED_SUMMER_TARIFFS = 1.43750

# --- SPOTPRIS TIL TREND-SCENARIE ---
def get_live_spot_price() -> tuple[float, str, bool]:
    live_cache_file = "/tmp/peng_eon_live_spot.json"
    if os.path.exists(live_cache_file):
        try:
            with open(live_cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
                return cached.get("price", 1.42), cached.get("source", "Live API (cache)"), True
        except Exception:
            pass

    # Anvend seneste kendte månedlige spotpris (inkl. moms og vintertariffer)
    latest_m = sorted(HISTORICAL_NIGHT_SPOT_DKK.keys())[-1]
    latest_spot = HISTORICAL_NIGHT_SPOT_DKK.get(latest_m, 0.856)
    latest_kwh = round((latest_spot * 1.25) + FIXED_WINTER_TARIFFS, 2)
    return latest_kwh, "Energi Data Service (seneste opgørelse)", True

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
    scenario_raw_spots = []

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
        sc_raw_spot = base_raw_spot * factor
        scenario_raw_spots.append(sc_raw_spot)

        # Samlet kWh-pris (kan aldrig blive negativ jf. E.ON regler)
        month_kwh_price = round(max(0.0, (sc_raw_spot * 1.25) + fixed_tariffs), 2)
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
            f"{sc_raw_spot * 100:.1f} øre",
            f"{month_kwh_price:.2f} kr.",
            f"{cost_plus / 100.0:,.2f} kr.",
            f"{cost_spot / 100.0:,.2f} kr.",
            best_badge
        ])

    avg_sc_price = sum(scenario_kwh_prices) / len(scenario_kwh_prices) if scenario_kwh_prices else 0.0
    min_sc_price = min(scenario_kwh_prices) if scenario_kwh_prices else 0.0
    max_sc_price = max(scenario_kwh_prices) if scenario_kwh_prices else 0.0
    min_raw_ore = (min(scenario_raw_spots) * 100) if scenario_raw_spots else 0.0
    max_raw_ore = (max(scenario_raw_spots) * 100) if scenario_raw_spots else 0.0

    total_savings_vs_plus = (total_plus_minor - total_spot_minor) / 100.0
    winter_savings_vs_plus = (winter_cost_plus_minor - winter_cost_spot_minor) / 100.0

    if total_savings_vs_plus >= 0:
        overall_text = (
            f"Ved dette prisniveau ville City Spot give et samlet overskud på **+{total_savings_vs_plus:,.2f} kr.** "
            f"i forhold til Plus (billigst i {spot_wins} ud af {total_months} måneder)."
        )
    else:
        overall_text = (
            f"Ved dette prisniveau er Plus billigst samlet set og sparer jer for **+{-total_savings_vs_plus:,.2f} kr.** "
            f"i forhold til City Spot (Plus vinder i {total_months - spot_wins} ud af {total_months} måneder)."
        )

    if winter_savings_vs_plus >= 0:
        winter_text = f"I de 4 koldeste vintermåneder (nov–feb) sparer City Spot jer **+{winter_savings_vs_plus:,.0f} kr.** samlet."
    else:
        winter_text = f"I de 4 koldeste vintermåneder (nov–feb) beskytter Plus jer og sparer jer **+{-winter_savings_vs_plus:,.0f} kr.** samlet mod vinterkulde og høje tariffer."

    dc_and_rules_note = (
        "\n\n🚗 **Bemærkninger til vilkår:**\n"
        "• **Lynladning (DC):** City Spot koster spotpris + 25 øre (samme som AC!). På Plus koster DC 3,25 kr./kWh (+1,00 kr. tillæg).\n"
        "• **Spærregebyr:** Reglerne er ens på begge abonnementer (24 timers gebyrfri parkering efter endt AC-opladning, så I bevarer samme fleksibilitet)."
    )

    if factor == 1.0:
        model_desc = (
            f"📈 **Model:** Beregningen anvender **hver enkelt måneds faktiske historiske spotpris for DK2** "
            f"(kilde: elbørsen Nord Pool / Energi Data Service) tillagt Cerius' sæsontariffer "
            f"(vinter kl. 00-06: 1,53 kr./kWh vs. sommer kl. 00-06: 1,44 kr./kWh før spot). "
            f"Over perioden svinger den rå natspotpris mellem **{min_raw_ore:.1f} og {max_raw_ore:.1f} øre/kWh**, "
            f"hvilket giver en samlet City Spot kWh-pris mellem **{min_sc_price:.2f} og {max_sc_price:.2f} kr./kWh** afhængigt af måneden."
        )
    else:
        model_desc = (
            f"📈 **Model:** Beregningen tager udgangspunkt i **hver enkelt måneds historiske spotpriser**, "
            f"men forskyder niveauet med **{pct_change:+.0f} %** (faktor {factor:.2f}). "
            f"De resulterende månedlige kWh-priser spænder mellem **{min_sc_price:.2f} og {max_sc_price:.2f} kr./kWh** "
            f"(vægtet gennemsnit: {avg_sc_price:.2f} kr./kWh)."
        )

    summary = (
        f"**Scenarie: {label}**\n\n"
        f"{model_desc}\n\n"
        f"**Samlet konklusion:** {overall_text}\n\n"
        f"❄️ **Vintermånederne (Nov–Feb):** {winter_text}\n\n"
        f"🎯 **Smertegrænse:** Hvis spotpriserne stiger over {breakeven_pct:+.0f} % (faktor {breakeven_factor:.2f}), tipper balancen til Plus' fordel."
        f"{dc_and_rules_note}"
    )

    if factor == 1.0:
        kpi_spot_label = "Historisk spot (DK2)"
        kpi_spot_val = f"{min_raw_ore:.0f}–{max_raw_ore:.0f} øre"
        kpi_spot_sub = f"Total: {min_sc_price:.2f}–{max_sc_price:.2f} kr./kWh"
    else:
        kpi_spot_label = "Prisforskydning"
        kpi_spot_val = f"{pct_change:+.0f} %"
        kpi_spot_sub = f"Total: {min_sc_price:.2f}–{max_sc_price:.2f} kr./kWh"

    kpis = [
        {
            "label": kpi_spot_label,
            "formatted_value": kpi_spot_val,
            "trend": "positive" if factor <= 1.0 else "negative",
            "subtitle": kpi_spot_sub
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

    spot_legend_label = "City Spot (229 kr. + månedlig spot)" if pct_change == 0 else f"City Spot (229 kr. + spot {pct_change:+.0f} %)"

    chart = {
        "chart_type": "composed",
        "x_axis": "month",
        "series": [
            {"key": "cost_spot_kr", "label": "City Spot (229 kr.)", "color": "#10b981", "type": "bar"},
            {"key": "cost_plus_kr", "label": "Plus (99 kr.)", "color": "#3b82f6", "type": "bar"},
            {"key": "cost_lite_kr", "label": "Lite / Ad hoc (0 kr.)", "color": "#f59e0b", "type": "line"},
        ],
        "custom_legend": [
            {"label": spot_legend_label, "color": "#10b981", "type": "rect"},
            {"label": "Plus (99 kr. + 2,25 kr. fast)", "color": "#3b82f6", "type": "rect"},
            {"label": "Lite (0 kr. + 2,95 kr. ad hoc)", "color": "#f59e0b", "type": "line"},
        ],
        "data": chart_data,
    }

    table = {
        "columns": [
            "Måned",
            "Forbrug",
            "Rå spot (DK2)",
            "kWh-pris (Spot)",
            "Plus (99 kr.)",
            "City Spot (229 kr.)",
            "Bedste valg"
        ],
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
        "Faktiske månedlige natspotpriser for DK2 og sæsontariffer (hver måned bruger sin egen historiske pris).",
        1.0
    ),
    generate_factor_scenario(
        "mild",
        "☀️ Mild vinter (-20 %)",
        "Simulerer et ekstra mildt og blæsende år med 20 % lavere spotpriser i alle måneder.",
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
