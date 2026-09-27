#!/usr/bin/env python3
"""
build_journeys.py — turn the inventory sources into the pages people can book from.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Reads    data/sources/*.json            (CruiseHost Explora sailings, Variety catalogue)
Writes   data/sailings.json             one merged inventory, English, provenance per record
         journeys.html                  every sailing as a card, filterable, no JS needed to read
         journeys/<id>.html             one page per sailing: route, days, fares, visa, ship

Rules it enforces rather than suggests:
  * Nothing is invented. Fares, dates, nights, ships and ports come from a source file,
    and every page says which one and as of when. No source date -> "on request".
  * Focus: sailings that call in Türkiye, Greece or Italy sort first everywhere.
  * «Persian Gulf», never "Arabian Gulf", in anything this script writes.
  * Visa: any Greek, Italian, Spanish or French port makes the cruise Schengen, whatever
    else is on the route. French overseas territories are NOT Schengen. Türkiye is
    visa-free or e-visa for many passports, never stated as visa-free for all.

Usage:  python3 build_journeys.py            build
        python3 build_journeys.py --check    build to memory, fail if anything on disk differs
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from collections import Counter, OrderedDict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "data" / "sources"
TODAY = date.today().isoformat()

# ───────────────────────────── ports → countries ─────────────────────────────
# Explicit list, never substring guessing. Keyed by the exact spelling each source uses.
PORT_COUNTRY = {
    # Türkiye
    "Istanbul": "TR", "Kusadasi, Ephesos": "TR", "Kuşadası": "TR", "Bodrum": "TR", "Marmaris": "TR",
    # Greece
    "Piraeus, Athens": "GR", "Athens": "GR", "Athens (Zea Marina)": "GR", "Athens (Lavrio)": "GR", "Mykonos": "GR",
    "Santorini": "GR", "Milos": "GR", "Paros": "GR", "Patmos": "GR", "Amorgos": "GR", "Corfu": "GR",
    "Syros, Kyklades": "GR", "Rhodos": "GR", "Nafplion": "GR", "Pylos, Peloponnese": "GR", "Thessaloniki": "GR",
    "Volos": "GR", "Skiathos": "GR", "Argostoli, Cephalonia": "GR", "Nydri, Nisos Lefkada": "GR",
    "Kythnos": "GR", "Syros (Ermoupoli)": "GR", "Mykonos and Delos": "GR", "Delos": "GR", "Naxos": "GR",
    "Paros and Antiparos": "GR", "Polyaigos and Folegandros": "GR", "Skopelos": "GR", "Alonissos": "GR",
    "Skyros": "GR", "Evia (Karystos)": "GR", "Chalkida": "GR", "Kea": "GR", "Heraklion (Crete)": "GR",
    "Monemvasia": "GR", "Hydra and Athens": "GR", "Paxos and Antipaxos": "GR", "Lefkada": "GR",
    "Kefalonia (Fiskardo)": "GR", "Ithaca": "GR", "Zakynthos": "GR", "Meganisi": "GR", "Hydra": "GR",
    "Spetses": "GR", "Pylos": "GR", "Katakolon": "GR", "Samos": "GR", "Patmos and Lipsi": "GR", "Sifnos": "GR",
    # Italy
    "Civitavecchia, Rome": "IT", "Fusina (Venice)": "IT", "Naples": "IT", "Bari": "IT", "Brindisi": "IT",
    "Livorno": "IT", "Genoa": "IT", "La Spezia, Florence, Pisa, Cinque": "IT", "Amalfi": "IT", "Sorrent": "IT",
    "Messina, Sicily": "IT", "Palermo, Sicily": "IT", "Syracuse, Sicily": "IT", "Trapani, Sicily": "IT",
    "Giardini Naxos": "IT", "Lipari": "IT", "Gallipoli, Apulia": "IT", "Porto Santo Stefano": "IT",
    "Cagliari, Sardinia": "IT", "Alghero, Sardinia": "IT", "Capri": "IT", "Taormina (Sicily)": "IT",
    "Lipari (Aeolian Islands)": "IT", "Salina": "IT", "Sorrento": "IT", "Amalfi Coast": "IT", "Palermo (Sicily)": "IT",
    "Trapani": "IT", "Taormina": "IT", "Stromboli": "IT", "Lipari and Salina": "IT", "Syracuse": "IT",
    "Syracuse (Sicily)": "IT", "Taormina and Giardini Naxos": "IT", "Aeolian Islands": "IT",
    "Tropea (Calabria)": "IT", "Amalfi and Positano": "IT", "Rome (Civitavecchia)": "IT",
    # Malta, Adriatic, Balkans
    "Valletta": "MT", "Valletta (Malta)": "MT", "Gozo": "MT",
    "Dubrovnik": "HR", "Dubrovnik (Croatia)": "HR", "Hvar": "HR", "Split": "HR", "Rijeka": "HR", "Rovinj": "HR",
    "Trogir": "HR", "Zadar": "HR", "Korčula": "HR", "Šibenik": "HR", "Koper": "SI", "Kotor": "ME",
    "Kotor (Montenegro)": "ME", "Sarande": "AL", "Sarandë (Albania)": "AL",
    # Western Mediterranean and Atlantic Europe
    "Barcelona": "ES", "Alicante": "ES", "Valencia": "ES", "Tarragona": "ES", "Palamos": "ES", "Malaga": "ES",
    "Motril, Andalusia": "ES", "Cadiz (Seville)": "ES", "Ibiza, Balearic Islands": "ES",
    "Mahon, Menorca, Balearic Islands": "ES", "Palma de Mallorca, Balearic Islands": "ES", "Bilbao": "ES",
    "La Coruna": "ES", "Arrecife, Lanzarote": "ES", "Puerto del Rosario, Fuerteventura": "ES",
    "Santa Cruz de Tenerife": "ES", "San Sebastian, La Gomera": "ES", "St. Cruz de La Palma": "ES",
    "Marseille": "FR", "Cannes": "FR", "Fireworks in Cannes": "FR", "St. Tropez": "FR", "Villefranche, Nice": "FR",
    "Ajaccio, Corsica": "FR", "Pauillac": "FR", "Monte Carlo": "MC",
    "Lisbon": "PT", "Porto": "PT", "Funchal, Madeira Island": "PT", "Gibraltar": "GI",
    "Casablanca": "MA", "Tanger": "MA", "Agadir": "MA", "La Goulette": "TN", "Algier": "DZ",
    # Northern Europe
    "Southampton": "GB", "Hamburg": "DE", "Zeebrügge": "BE", "Brussels": "BE", "Copenhagen": "DK", "Aarhus": "DK",
    "Ronne": "DK", "Oslo": "NO", "Bergen": "NO", "Stavanger": "NO", "Flåm": "NO", "Nordfjordeid": "NO",
    "Stockholm": "SE", "Visby": "SE", "Lysekil": "SE", "Helsinki": "FI", "Tallinn": "EE",
    # Americas and Caribbean (French overseas ports are outside Schengen)
    "Miami": "US", "Los Angeles, California": "US", "San Juan": "PR", "Grand Turk": "TC", "Ochos Rios": "JM",
    "Spanish Town": "VG", "Road Bay (Sandy Ground)": "AI", "Basseterre": "KN", "St. John´s": "AG",
    "Gustavia, St. Barthelemy": "BL", "Saint-Pierre, Martinique": "MQ", "Castries": "LC", "Bequia": "VC",
    "Bridgetown": "BB", "Port of Spain": "TT", "Oranjestad": "AW", "Willemstad, Curacao": "CW",
    "Santa Marta": "CO", "Panama Canal": "PA", "Panama City": "PA", "Puerto Quetzal": "GT", "Acjutla": "SV",
    "Puerto Madero": "MX", "Huatulco": "MX", "Puerto Vallarta": "MX", "Devil's Island": "GF",
    "Macapà": "BR", "Santarém": "BR", "Alter do Chao": "BR", "Boca de Valeria": "BR", "Parintíns": "BR", "Manaus": "BR",
    # Variety beyond Europe
    "Mindelo (São Vicente)": "CV", "Mindelo": "CV", "Santo Antão": "CV", "São Nicolau": "CV", "Sal": "CV",
    "Boa Vista": "CV", "Maio": "CV", "Santiago (Praia)": "CV",
    "Mahé (Victoria)": "SC", "Mahé": "SC", "Praslin": "SC", "La Digue": "SC", "Curieuse and St Pierre": "SC",
    "Aride Island": "SC", "Sister Islands and Félicité": "SC", "Cerf Island / south Mahé": "SC", "Curieuse": "SC",
    "St Pierre": "SC", "Félicité": "SC", "Praslin and Curieuse": "SC",
    "Papeete (Tahiti)": "PF", "Papeete": "PF", "Huahine": "PF", "Raiatea": "PF", "Taha'a": "PF", "Bora Bora": "PF",
    "Moorea": "PF", "Maupiti": "PF", "Rangiroa": "PF", "Fakarava": "PF", "Anaa": "PF",
}
AT_SEA = {"Cruising Day", "At sea"}
# Cartagena exists in Spain and Colombia; the route decides.
AMBIGUOUS = {"Cartagena": lambda route: "ES" if any(PORT_COUNTRY.get(p) == "ES" for p in route) else "CO"}

COUNTRY = {
    "TR": "Türkiye", "GR": "Greece", "IT": "Italy", "MT": "Malta", "HR": "Croatia", "SI": "Slovenia", "ME": "Montenegro",
    "AL": "Albania", "ES": "Spain", "FR": "France", "MC": "Monaco", "PT": "Portugal", "GI": "Gibraltar", "MA": "Morocco",
    "TN": "Tunisia", "DZ": "Algeria", "GB": "United Kingdom", "DE": "Germany", "BE": "Belgium", "DK": "Denmark",
    "NO": "Norway", "SE": "Sweden", "FI": "Finland", "EE": "Estonia", "US": "United States", "PR": "Puerto Rico",
    "TC": "Turks and Caicos", "JM": "Jamaica", "VG": "British Virgin Islands", "AI": "Anguilla", "KN": "St Kitts and Nevis",
    "AG": "Antigua", "BL": "St Barthélemy", "MQ": "Martinique", "LC": "St Lucia", "VC": "St Vincent and the Grenadines",
    "BB": "Barbados", "TT": "Trinidad and Tobago", "AW": "Aruba", "CW": "Curaçao", "CO": "Colombia", "PA": "Panama",
    "GT": "Guatemala", "SV": "El Salvador", "MX": "Mexico", "GF": "French Guiana", "BR": "Brazil", "CV": "Cape Verde",
    "SC": "Seychelles", "PF": "French Polynesia",
}
SCHENGEN = {"GR", "IT", "ES", "FR", "PT", "MT", "HR", "SI", "DE", "BE", "DK", "NO", "SE", "FI", "EE", "MC"}
FOCUS = ["TR", "GR", "IT"]

# Search areas: the keys the home-page search and the filter use. Focus areas first.
AREAS = OrderedDict([
    ("turkiye", "Türkiye"), ("greece", "Greece and the Greek islands"), ("italy", "Italy, Sicily and Malta"),
    ("adriatic", "Croatia and the Adriatic"), ("western-med", "Western Mediterranean"),
    ("northern-europe", "Northern Europe and the fjords"), ("atlantic", "Atlantic islands and crossings"),
    ("americas", "Caribbean and the Americas"), ("seychelles", "Seychelles"), ("tahiti", "Tahiti and French Polynesia"),
])
AREA_OF = {"TR": "turkiye", "GR": "greece", "IT": "italy", "MT": "italy", "HR": "adriatic", "SI": "adriatic",
           "ME": "adriatic", "AL": "adriatic", "ES": "western-med", "FR": "western-med", "MC": "western-med",
           "GI": "western-med", "MA": "western-med", "TN": "western-med", "DZ": "western-med",
           "GB": "northern-europe", "DE": "northern-europe", "BE": "northern-europe", "DK": "northern-europe",
           "NO": "northern-europe", "SE": "northern-europe", "FI": "northern-europe", "EE": "northern-europe",
           "PT": "atlantic", "CV": "atlantic", "SC": "seychelles", "PF": "tahiti"}
for c in ("US", "PR", "TC", "JM", "VG", "AI", "KN", "AG", "BL", "MQ", "LC", "VC", "BB", "TT", "AW", "CW", "CO", "PA", "GT", "SV", "MX", "GF", "BR"):
    AREA_OF[c] = "americas"

EXPLORA_YEAR = {"Explora I": 2023, "Explora II": 2024, "Explora III": 2026, "Explora IV": 2027}

# Explora imagery (downloaded from Explora's own site, see HANDOFF). Chosen by area, rotated by id.
MEDIA = json.loads((HERE / "media" / "index.json").read_text(encoding="utf-8")) if (HERE / "media" / "index.json").exists() else {}
def m(name: str) -> str:
    hit = next((p for p in MEDIA.values() if p.endswith(name)), None)
    if not hit:
        raise SystemExit(f"media file missing: {name}")
    return hit
EXPLORA_IMG = {
    # checked by eye 27 Sep: Amalfi-style coast, a Mediterranean harbour town from above, Monaco, and the
    # ship at sea. NOT "An-Invitation-to-celebrate" (a fjord) or "Summer-2028-122" (unidentified coast).
    "med": ["Thumbnail-Vertical.jpg", "Summer-2028-136.jpg", "F1-44.jpg", "EXIII_01_Clean.webp",
            "Drone-Shoot-14.webp", "ExploraIII_Aerial_2_mob.jpg"],
    "western-med": ["F1-44.jpg", "Thumbnail-Vertical.jpg"],
    "northern-europe": ["Thumbnail-Northern-Europe.jpg"],
    "americas": ["Caribbean-Central-America.jpg", "Winter-Car-5.jpg", "South-America-Explora-Journeys-4.jpg"],
    "atlantic": ["img.jpg", "Explora-Journeys-New-York.jpeg"],
}


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def country_of(port: str, route: list[str]) -> str | None:
    if port in AT_SEA:
        return None
    if port in AMBIGUOUS:
        return AMBIGUOUS[port](route)
    return PORT_COUNTRY.get(port)


DISPLAY = {
    "Piraeus, Athens": "Athens (Piraeus)", "Civitavecchia, Rome": "Rome (Civitavecchia)", "Fusina (Venice)": "Venice (Fusina)",
    "Kusadasi, Ephesos": "Kuşadası (Ephesus)", "Villefranche, Nice": "Villefranche (Nice)", "Nydri, Nisos Lefkada": "Nydri (Lefkada)",
    "Argostoli, Cephalonia": "Argostoli (Kefalonia)", "La Spezia, Florence, Pisa, Cinque": "La Spezia (for Florence and Pisa)",
    "Sorrent": "Sorrento", "Rhodos": "Rhodes", "Acjutla": "Acajutla", "Algier": "Algiers", "Tanger": "Tangier",
    "Zeebrügge": "Zeebrugge", "Ronne": "Rønne", "Fireworks in Cannes": "Cannes (fireworks night)", "St. John´s": "St John's (Antigua)",
    "Ochos Rios": "Ocho Rios", "Macapà": "Macapá", "Cadiz (Seville)": "Cádiz (for Seville)", "Syros, Kyklades": "Syros",
    "Road Bay (Sandy Ground)": "Road Bay (Anguilla)", "Spanish Town": "Spanish Town (Virgin Gorda)", "Puerto Madero": "Puerto Madero (Chiapas)",
}


def pretty_port(p: str) -> str:
    if p in AT_SEA:
        return "At sea"
    if p in DISPLAY:
        return DISPLAY[p]
    return p.split(",")[0].strip() if "," in p else p


def short_port(p: str) -> str:
    """For titles: 'Athens (Piraeus)' -> 'Athens'."""
    return re.sub(r"\s*\(.*?\)", "", pretty_port(p)).strip()


def title_for(route: list[str]) -> str:
    a, b = short_port(route[0]), short_port(route[-1])
    return f"Round trip from {a}" if a == b else f"{a} to {b}"


def euro(n) -> str:
    return "€{:,}".format(int(n))


def month_label(ym: str) -> str:
    y, mo = ym.split("-")
    return ["January", "February", "March", "April", "May", "June", "July", "August", "September",
            "October", "November", "December"][int(mo) - 1] + " " + y


def visa_lines(codes: list[str]) -> list[str]:
    cs = set(codes)
    out = []
    sch = [COUNTRY[c] for c in codes if c in SCHENGEN]
    if sch:
        out.append("Schengen visa for non-EU passports, for the whole cruise. Calls in " + ", ".join(dict.fromkeys(sch)) + ".")
    if "TR" in cs:
        out.append("Türkiye: visa-free or e-visa for many passports, not all.")
    if cs & {"US", "PR"}:
        out.append("United States: visa or ESTA.")
    if "GB" in cs:
        out.append("United Kingdom: its own entry rules, separate from Schengen.")
    if cs & {"BL", "MQ", "GF", "PF"}:
        out.append("French overseas territories on this route are outside Schengen and have their own entry rules.")
    if cs == {"SC"}:
        out.append("Seychelles: visa-free on arrival for all nationalities.")
    out.append("We confirm the visa position for your passport before you pay anything.")
    return out


# ───────────────────────────── load and merge ─────────────────────────────
def load() -> list[dict]:
    sailings = []
    # The direct CruiseHost sync (sync/cruisehost_sync.py) wins; the snapshot is the interim seed.
    live = SRC / "cruisehost-sailings.json"
    ex = json.loads((live if live.exists() else SRC / "cruisehost-explora-snapshot.json").read_text(encoding="utf-8"))
    for s in ex["sailings"]:
        if s.get("hidden"):
            continue
        route = s["route"]
        sid = s["cruisehostId"]
        deps = [d for d in s["departures"] if d["date"] >= TODAY]
        if not deps:
            continue
        line = s.get("line") or "Explora Journeys"
        sailings.append({
            "id": sid, "line": line, "lineKey": re.sub(r"[^a-z]+", "-", line.lower()).strip("-").split("-")[0],
            "ships": [s["ship"]], "nights": s["nights"], "shipImage": s.get("shipImage"),
            "region": s["region"], "route": route, "title": title_for(route),
            "departures": deps, "priceFrom": min(d["priceFrom"] for d in deps if d["priceFrom"]), "currency": "EUR",
            "priceBasis": "CruiseHost lead fare: per person, cheapest available cabin, two sharing",
            "asOf": s.get("syncedAt") or ex["snapshotDate"], "source": "CruiseHost, the cruise lines' booking system",
            "itinerary": [[pretty_port(p), ""] for p in route] if len(route) == s["nights"] + 1 else None,
            "flags": [],
        })
    va = json.loads((SRC / "variety-catalogue-2026-27.json").read_text(encoding="utf-8"))
    for v in va["itineraries"]:
        route = [d[0] for d in v["itinerary"]]
        sailings.append({
            "id": v["id"], "line": "Variety Cruises", "lineKey": "variety", "ships": v["ships"], "nights": v["nights"],
            "region": v["region"], "route": route, "title": v["title"], "departures": [],
            "priceFrom": v["priceFrom"], "currency": "EUR", "priceBasis": va["priceBasis"],
            "asOf": None, "source": "Variety Cruises catalogue 2026–27", "itinerary": v["itinerary"],
            "image": "media/variety/" + v["image"], "flags": v.get("flags", []),
        })
    for s in sailings:
        codes = [c for c in (country_of(p, s["route"]) for p in s["route"]) if c]
        unknown = [p for p in s["route"] if p not in AT_SEA and not country_of(p, s["route"])]
        if unknown:
            raise SystemExit(f"{s['id']}: no country for {unknown} — add them to PORT_COUNTRY")
        s["countries"] = list(dict.fromkeys(codes))
        s["focus"] = [c for c in FOCUS if c in s["countries"]]
        s["areas"] = list(dict.fromkeys(AREA_OF[c] for c in s["countries"]))
        s["months"] = sorted({d["date"][:7] for d in s["departures"]})
        s["visa"] = visa_lines(s["countries"])
        s["url"] = f"journeys/{s['id']}.html"
        if s["lineKey"] == "explora":
            key = "med" if s["focus"] or "adriatic" in s["areas"] else next((a for a in s["areas"] if a in EXPLORA_IMG), "med")
            pool = EXPLORA_IMG[key]
            s["image"] = m(pool[int(hashlib.sha1(s["id"].encode()).hexdigest(), 16) % len(pool)])
        elif not s.get("image"):
            # Another CruiseHost line: its own ship photo if the sync fetched one, else none.
            # Never borrow a different line's photography.
            s["image"] = s.get("shipImage")
    # Türkiye/Greece/Italy first, then the soonest departure, then price
    sailings.sort(key=lambda s: (0 if s["focus"] else 1, s["departures"][0]["date"] if s["departures"] else "9999", s["priceFrom"]))
    return sailings


# ───────────────────────────── page chrome ─────────────────────────────
def chrome():
    idx = (HERE / "index.html").read_text(encoding="utf-8")
    head = re.search(r"<!doctype html>.*?<link rel=\"stylesheet\" href=\"assets/site.css\">\n", idx, re.S | re.I).group(0)
    nav = re.search(r'<nav class="nav".*?</nav>\n', idx, re.S).group(0)
    foot = re.search(r"<footer>.*?</footer>\n", idx, re.S).group(0)
    return head, nav, foot


def page(head, nav, foot, *, slug, title, desc, body, base="", canonical=None):
    h = head
    h = re.sub(r"<title>.*?</title>", f"<title>{esc(title)}</title>", h, flags=re.S)
    h = re.sub(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{esc(desc)}">', h)
    h = re.sub(r'<meta property="og:title" content="[^"]*">', f'<meta property="og:title" content="{esc(title)}">', h)
    h = re.sub(r'<meta property="og:description" content="[^"]*">', f'<meta property="og:description" content="{esc(desc)}">', h)
    url = canonical or f"https://cruise24.me/{slug}"
    h = re.sub(r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="{url}">', h)
    h = re.sub(r'<meta property="og:url" content="[^"]*">', f'<meta property="og:url" content="{url}">', h)
    h = re.sub(r'<script type="application/ld\+json">.*?</script>\n', "", h, flags=re.S)
    if base:
        h = h.replace('<meta charset="utf-8">', f'<meta charset="utf-8">\n<base href="{base}">', 1)
    return (h + "</head>\n<body data-page=\"journeys\">\n" + nav + body + foot +
            '\n<script src="assets/vendor/gsap.min.js"></script>\n<script src="assets/vendor/ScrollTrigger.min.js"></script>\n'
            '<script src="assets/site.js"></script>\n<script src="assets/journeys.js"></script>\n</body>\n</html>\n')


def card(s) -> str:
    dep = s["departures"][0]["date"] if s["departures"] else None
    when = (f"Next departure {date.fromisoformat(dep).strftime('%-d %b %Y')}" if dep else "Departure dates on request")
    more = f" · {len(s['departures'])} dates" if len(s["departures"]) > 1 else ""
    chips = "".join(f'<span class="chip">{esc(COUNTRY[c])}</span>' for c in s["focus"])
    ship = " or ".join(s["ships"])
    return (f'<a class="jcard2" href="{esc(s["url"])}" data-areas="{" ".join(s["areas"])}" data-months="{" ".join(s["months"]) or "request"}" '
            f'data-line="{s["lineKey"]}" data-nights="{s["nights"]}" data-price="{s["priceFrom"]}" data-date="{dep or "9999"}" data-focus="{1 if s["focus"] else 0}">'
            + (f'<img src="{esc(s["image"])}" alt="" loading="lazy">' if s.get("image") else '<div class="noimg"></div>') +
            f'<div class="jc-body"><small>{esc(s["line"])} · {esc(ship)}</small>'
            f'<h3>{esc(s["title"])}</h3>'
            f'<p class="jc-route">{esc(" · ".join(dict.fromkeys(p for p in (pretty_port(x) for x in s["route"]) if p != "At sea")))}</p>'
            f'<div class="jc-chips">{chips}</div>'
            f'<div class="jc-foot"><span>{s["nights"]} nights<br><em>{esc(when)}{more}</em></span>'
            f'<span class="jc-price">from <b>{euro(s["priceFrom"])}</b><em>per person</em></span></div></div></a>')


def listing(sailings, head, nav, foot) -> str:
    months = sorted({mo for s in sailings for mo in s["months"]})
    n_focus = sum(1 for s in sailings if s["focus"])
    area_opts = "".join(f'<option value="{k}">{esc(v)}</option>' for k, v in AREAS.items()
                        if any(k in s["areas"] for s in sailings))
    month_opts = "".join(f'<option value="{mo}">{month_label(mo)}</option>' for mo in months)
    lines = Counter(s["line"] for s in sailings)
    body = f'''<section class="page-hero" style="min-height:auto;padding-bottom:40px">
  <img src="{esc(m("Thumbnail-Vertical.jpg"))}" alt="" loading="eager">
  <div class="wrap"><span class="kicker">Journeys</span><h1>Sailings you can book</h1>
  <p>{len(sailings)} sailings from {" and ".join(dict.fromkeys(s["line"] for s in sailings))}. {n_focus} of them call in Türkiye, Greece or Italy, and those come first. Explora fares are CruiseHost's current lead fare; Variety fares are the line's 2026–27 catalogue. Every fare is confirmed with the line before you commit.</p></div>
</section>
<section class="section light" style="padding-top:28px">
  <div class="wrap">
    <form class="filters" id="filters" onsubmit="event.preventDefault()">
      <label>Where <select id="f-area"><option value="">Anywhere</option>{area_opts}</select></label>
      <label>When <select id="f-month"><option value="">Any time</option>{month_opts}<option value="request">Dates on request</option></select></label>
      <label>Line <select id="f-line"><option value="">All lines</option>{"".join(f'<option value="{k}">{esc(v)}</option>' for k, v in dict((s["lineKey"], s["line"]) for s in sailings).items())}</select></label>
      <label>Length <select id="f-nights"><option value="">Any length</option><option value="0-5">Up to 5 nights</option><option value="6-8">6 to 8 nights</option><option value="9-14">9 to 14 nights</option><option value="15-99">15 nights or more</option></select></label>
      <label>Sort <select id="f-sort"><option value="focus">Türkiye, Greece, Italy first</option><option value="date">Soonest departure</option><option value="price">Lowest fare</option></select></label>
    </form>
    <p class="fcount" id="fcount" aria-live="polite">{len(sailings)} sailings</p>
    <div class="jgrid2" id="jgrid">
{chr(10).join(card(s) for s in sailings)}
    </div>
    <p class="fine" id="fempty" hidden>Nothing matches those choices. Clear one of them, or <a href="contact.html" style="border-bottom:1px solid var(--accent)">tell us what you have in mind</a>.</p>
    <p class="fine" style="margin-top:32px">Sources: {", ".join(f"{k} ({v})" for k, v in lines.items())}. Silversea and Scenic join when their CruiseHost inventory is connected.</p>
  </div>
</section>
'''
    return page(head, nav, foot, slug="journeys.html", title="Journeys · Cruise24",
                desc=f"{len(sailings)} Explora Journeys and Variety Cruises sailings, with Türkiye, Greece and Italy first. Real fares, dates and routes, confirmed with the line before you book.",
                body=body)


def detail(s, head, nav, foot) -> str:
    ship = " or ".join(s["ships"])
    days = s["itinerary"]
    if days:
        rows = "".join(f'<li><b>Day {i + 1}</b><div>{esc(p)}{"<p>" + esc(n) + "</p>" if n else ""}</div></li>' for i, (p, n) in enumerate(days))
        itin = f'<ul class="days">{rows}</ul>'
    else:
        itin = ('<p class="fine">Ports in order. The day-by-day schedule comes with your quote.</p><ol class="portlist">' +
                "".join(f"<li>{esc(pretty_port(p))}</li>" for p in s["route"]) + "</ol>")
    if s["departures"]:
        fares = ('<table class="fares"><thead><tr><th>Departure</th><th>From, per person</th></tr></thead><tbody>' +
                 "".join(f'<tr><td>{date.fromisoformat(d["date"]).strftime("%a %-d %B %Y")}</td><td>{euro(d["priceFrom"]) if d["priceFrom"] else "On request"}</td></tr>' for d in s["departures"]) +
                 "</tbody></table>")
    else:
        fares = f'<p class="bigfare">from <b>{euro(s["priceFrom"])}</b> per person</p><p class="fine">No departure dates in the source. Dates and the live fare come with your quote.</p>'
    shipnote = ""
    if s["lineKey"] not in ("explora", "variety"):
        shipnote = f'<p>{esc(s["ships"][0])}, {esc(s["line"])}. Ship details and inclusions come with your quote.</p>'
    elif s["lineKey"] == "explora":
        y = EXPLORA_YEAR.get(s["ships"][0])
        shipnote = f'<p>{esc(s["ships"][0])}, all-suite, Explora Journeys{f", in service since {y}" if y and y <= 2026 else f", entering service in {y}" if y else ""}. What the Explora fare includes is <a href="index.html#inclusions" style="border-bottom:1px solid var(--accent)">listed on the home page</a>.</p>'
    else:
        imgs = "".join(f'<figure><img src="media/variety/ship-{esc(n.lower().replace(" ", "-"))}.jpg" alt="{esc(n)}" loading="lazy"><figcaption>{esc(n)}</figcaption></figure>' for n in s["ships"])
        which = ("This route is sailed by " + " or ".join(s["ships"]) + "; the yacht is confirmed at booking.") if len(s["ships"]) > 1 else ""
        shipnote = f'<div class="yachts">{imgs}</div><p>Variety Cruises: small ships of 50 to 72 guests. {esc(which)} Inclusions are confirmed with your quote.</p>'
    flags = ""  # data-quality flags go to data/data-checks.json, never into public HTML
    body = f'''<section class="page-hero" style="min-height:52svh">
  {f'<img src="{esc(s["image"])}" alt="" loading="eager">' if s.get("image") else ""}
  <div class="wrap"><span class="kicker">{esc(s["line"])} · {esc(ship)}</span><h1>{esc(s["title"])}</h1>
  <p>{s["nights"]} nights · {esc(s["region"])} · {esc(pretty_port(s["route"][0]))} to {esc(pretty_port(s["route"][-1]))}</p></div>
</section>
{flags}
<section class="section light" style="padding-top:48px"><div class="wrap sailing">
  <div>
    <span class="kicker">The route</span>
    {itin}
    <h2 class="h-sub">The ship</h2>
    {shipnote}
    <h2 class="h-sub">Visa</h2>
    <ul class="ticks">{"".join(f"<li>{esc(v)}</li>" for v in s["visa"])}</ul>
  </div>
  <aside class="farebox">
    <span class="kicker">Fares</span>
    {fares}
    <p class="fine">{esc(s["priceBasis"])}. Source: {esc(s["source"])}{", as of " + date.fromisoformat(s["asOf"]).strftime("%-d %B %Y") if s["asOf"] else ""}. The line adds its service charge where it applies; we confirm the live fare and cabin before you commit.</p>
    <a class="btn solid full" href="contact.html#{esc(s["id"])}">Ask about this sailing</a>
    <a class="btn full" href="journeys.html">All sailings</a>
  </aside>
</div></section>
'''
    return page(head, nav, foot, slug=f"journeys/{s['id']}.html", base="../",
                title=f"{s['title']}, {s['nights']} nights · {s['line']} · Cruise24",
                desc=f"{s['line']} {ship}: {s['nights']} nights, {pretty_port(s['route'][0])} to {pretty_port(s['route'][-1])}. From {euro(s['priceFrom'])} per person.",
                body=body)


# Port notes for the focus countries. Short, and only what is well established; no
# distances or times we cannot stand behind. `match` lists every spelling the sources use.
PORT_GUIDES = [
    ("turkiye", "Istanbul", ["Istanbul"],
     "Ships berth at Galataport in Karaköy, on the Bosphorus: Galata is a walk away and the old city a short tram ride."),
    ("turkiye", "Kuşadası and Ephesus", ["Kusadasi, Ephesos", "Kuşadası"],
     "The pier is in the middle of town and Ephesus is about twenty minutes by road. <a href=\"journal.html#kusadasi\">Our full port guide</a>."),
    ("turkiye", "Bodrum", ["Bodrum"],
     "The Castle of St Peter and the harbour front are the centre of town; the site of the Mausoleum is a short walk inland."),
    ("turkiye", "Marmaris", ["Marmaris"],
     "A deep, sheltered bay with the old town and castle behind the marina."),
    ("greece", "Athens (Piraeus)", ["Piraeus, Athens", "Athens", "Athens (Zea Marina)", "Athens (Lavrio)", "Hydra and Athens"],
     "Piraeus is Athens' port. The Acropolis is reached by road or metro; allow for traffic on a first or last day."),
    ("greece", "Mykonos and Delos", ["Mykonos", "Mykonos and Delos", "Delos"],
     "Larger ships use the new port north of town, with a sea bus into Chora. Delos, the sanctuary island, is a short boat ride away."),
    ("greece", "Santorini", ["Santorini"],
     "A tender port below Fira. The cable car or the steps climb the caldera cliff, and the cable-car queue is the thing to plan around."),
    ("greece", "Corfu", ["Corfu"],
     "The old town, a UNESCO World Heritage site of Venetian forts and arcades, is a short ride from the port."),
    ("greece", "Nafplion", ["Nafplion"],
     "Greece's first capital. Ships anchor off the harbour; Mycenae and Epidaurus are both within reach for a half day."),
    ("greece", "Katakolon for Olympia", ["Katakolon"],
     "The port for Ancient Olympia, which lies inland by road."),
    ("greece", "Patmos", ["Patmos", "Patmos and Lipsi"],
     "Where tradition places St John's Book of Revelation. The Monastery of St John and the Cave of the Apocalypse are UNESCO-listed."),
    ("greece", "Rhodes", ["Rhodos"],
     "The medieval old town, a UNESCO site, begins at the harbour gates."),
    ("italy", "Rome (Civitavecchia)", ["Civitavecchia, Rome", "Rome (Civitavecchia)"],
     "Civitavecchia is Rome's cruise port. For a day in the city the train from Civitavecchia station is the simplest option."),
    ("italy", "Venice (Fusina)", ["Fusina (Venice)"],
     "Since 2021 large ships no longer sail the Giudecca Canal. Explora uses the Fusina terminal on the mainland, with a boat into the city."),
    ("italy", "Naples, Capri and the Amalfi Coast", ["Naples", "Capri", "Amalfi", "Amalfi Coast", "Sorrent", "Sorrento", "Amalfi and Positano"],
     "Naples' terminal is in the city centre by the Castel Nuovo. Pompeii and Sorrento are day trips; smaller ships anchor off Amalfi, Sorrento and Capri."),
    ("italy", "Sicily", ["Messina, Sicily", "Palermo, Sicily", "Syracuse, Sicily", "Trapani, Sicily", "Giardini Naxos", "Taormina (Sicily)", "Palermo (Sicily)", "Taormina", "Syracuse", "Syracuse (Sicily)", "Taormina and Giardini Naxos", "Trapani"],
     "Taormina sits above Giardini Naxos, where ships tender in. In Syracuse the island of Ortigia is walkable from the pier; Palermo's port is next to the old city."),
    ("italy", "La Spezia for Cinque Terre, Florence and Pisa", ["La Spezia, Florence, Pisa, Cinque"],
     "The port for the Cinque Terre by local train, and for Florence and Pisa by road."),
    ("italy", "Valletta, Malta", ["Valletta", "Valletta (Malta)"],
     "Ships berth below the Grand Harbour bastions; the Upper Barrakka lift takes you up into Valletta."),
]


def ports_page(sailings, head, nav, foot) -> str:
    titles = {"turkiye": "Türkiye", "greece": "Greece", "italy": "Italy and Malta"}
    blocks = []
    for key in ("turkiye", "greece", "italy"):
        items = []
        for k, name, match, note in PORT_GUIDES:
            if k != key:
                continue
            calls = [s for s in sailings if any(p in match for p in s["route"])]
            lines = ", ".join(dict.fromkeys(s["line"] for s in calls))
            count = (f'{len(calls)} of our sailings call here ({esc(lines)}).' if calls else "None of our current sailings call here; ask us.")
            items.append(f'<article class="post"><h3>{esc(name)}</h3><p>{note}</p><p class="fine">{count}</p></article>')
        n = sum(1 for s in sailings if key in s["areas"])
        blocks.append(f'''<section class="section{" light" if key != "greece" else ""}" id="{key}"><div class="wrap">
  <div class="head"><span class="kicker">{esc(titles[key])}</span><h2>{esc(titles[key])}</h2>
  <p>{n} sailings call here. <a href="journeys.html#{key}.any" style="border-bottom:1px solid var(--accent)">See them all</a>.</p></div>
  <div class="grid2">{"".join(items)}</div>
</div></section>''')
    body = f'''<section class="page-hero" style="min-height:auto;padding-bottom:40px">
  <img src="{esc(m("Summer-2028-136.jpg"))}" alt="" loading="eager">
  <div class="wrap"><span class="kicker">Ports</span><h1>Ports of Türkiye, Greece and Italy</h1>
  <p>Where our ships call most, and what each port is like to arrive in. The counts are from the sailings on this site today.</p></div>
</section>
{"".join(blocks)}
'''
    return page(head, nav, foot, slug="ports.html", title="Ports of Türkiye, Greece and Italy · Cruise24",
                desc="Cruise port notes for Istanbul, Kuşadası, Bodrum, Athens, Mykonos, Santorini, Corfu, Rome, Venice, Naples, Sicily and Malta, with the sailings that call there.",
                body=body)


def home_search(sailings) -> str:
    """The home page's 'When' menu lists the months that really have departures."""
    idx = (HERE / "index.html").read_text(encoding="utf-8")
    months = sorted({mo for s in sailings for mo in s["months"]})
    opts = '<option value="">Any time</option>' + "".join(f'<option value="{mo}">{month_label(mo)}</option>' for mo in months)
    new, n = re.subn(r'(<select name="when" id="hs-when">).*?(</select>)', lambda mt: mt.group(1) + opts + mt.group(2), idx, flags=re.S)
    if n != 1:
        raise SystemExit("home search 'when' menu not found in index.html")
    return new


def main() -> int:
    check = "--check" in sys.argv
    sailings = load()
    head, nav, foot = chrome()
    public = [{k: v for k, v in s.items() if k != "flags"} for s in sailings]
    checks = {s["id"]: s["flags"] for s in sailings if s["flags"]}
    out = {"data/sailings.json": json.dumps({"generated": TODAY, "count": len(public), "sailings": public}, ensure_ascii=False, indent=1) + "\n",
           "data/data-checks.json": json.dumps({"_about": "Records to verify against the line before launch. Internal: do not deploy.", "checks": checks}, ensure_ascii=False, indent=1) + "\n",
           "journeys.html": listing(sailings, head, nav, foot),
           "index.html": home_search(sailings),
           "ports.html": ports_page(sailings, head, nav, foot)}
    static = ["", "journeys.html", "destinations.html", "ports.html", "ships.html", "lines.html", "itineraries.html",
              "journal.html", "contact.html", "conditions.html", "imprint.html", "privacy.html"]
    urls = [f"https://cruise24.me/{p}" for p in static] + [f"https://cruise24.me/{s['url']}" for s in sailings]
    out["sitemap.xml"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                          + "".join(f"  <url><loc>{u}</loc><lastmod>{TODAY}</lastmod></url>\n" for u in urls) + "</urlset>\n")
    for s in sailings:
        out[s["url"]] = detail(s, head, nav, foot)
    for k, text in out.items():
        if re.search(r"arabian\s+gulf", text, re.I):
            raise SystemExit("«Arabian Gulf» in generated output — refused")
        if k != "data/data-checks.json" and re.search(r"boutimar|\.ir\b", text, re.I):
            raise SystemExit(f"{k}: mentions boutimar/.ir — cruise24.me must not; refused")
    stale = [p for p in (HERE / "journeys").glob("*.html") if f"journeys/{p.name}" not in out] if (HERE / "journeys").exists() else []
    if check:
        diff = [k for k, v in out.items() if not (HERE / k).exists() or (HERE / k).read_text(encoding="utf-8") != v]
        print(f"{len(out)} files, {len(diff)} differ, {len(stale)} stale", diff[:5])
        return 1 if diff or stale else 0
    (HERE / "journeys").mkdir(exist_ok=True)
    for p in stale:
        p.unlink()
    for k, v in out.items():
        (HERE / k).write_text(v, encoding="utf-8")
    c = Counter(s["line"] for s in sailings)
    print(f"{len(sailings)} sailings ({dict(c)}), {sum(1 for s in sailings if s['focus'])} in Türkiye/Greece/Italy; "
          f"wrote journeys.html + {len(sailings)} pages; removed {len(stale)} stale")
    return 0


if __name__ == "__main__":
    sys.exit(main())
