#!/usr/bin/env python3
"""
build_journeys.py — turn the inventory sources into the pages people can book from.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Reads    data/sources/*.json            (CruiseHost sailings, Variety Cruises sailings and catalogue)
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import port_countries  # noqa: E402  (the wider port -> country rules)

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
# When an exact spelling is not in PORT_COUNTRY, these word rules place it. Checked top to bottom,
# so an explicit country in the name ("Kusadasi (Turkey)", "Naples, Italy") wins over a place word.
KEYWORD_COUNTRY = [
    (r"\b(turkey|türkiye)\b|kusadasi|kuşadası|istanbul|bodrum|marmaris|fethiye|göcek|gocek|antalya|çanakkale|canakkale|dikili|izmir|cesme|çeşme|bozcaada|kas\b|kaş\b|bartin|amasra|sinop|trabzon|alanya", "TR"),
    (r"\bitaly\b|sicily|sardinia|sicilia|capri|amalfi|positano|sorrent|naples|napoli|salerno|lipari|stromboli|salina|taormina|catania|syracuse|siracusa|palermo|trapani|messina|civitavecchia|\brome\b|venice|venezia|fusina|trieste|ravenna|ancona|bari|brindisi|otranto|gallipoli|tropea|portofino|genoa|genova|la spezia|livorno|elba|portoferraio|porto santo stefano|monopoli|vieste|ortona|gaeta|ischia|procida|milazzo|crotone|giardini", "IT"),
    (r"\bmalta\b|valletta|gozo", "MT"),
    (r"\b(greece|crete)\b|athens|piraeus|\bzeas?\b|lavrio|poros|poliegos|polyaigos|folegandros|antiparos|paros|naxos|syros|mykonos|delos|santorini|thira|milos|sifnos|serifos|kythnos|\bkea\b|tinos|andros|ios\b|amorgos|koufonis|iraklia|levitha|ikaria|samos|patmos|lipsi|leros|kalymnos|kos\b|nisyros|tilos|symi|rhodes|rhodos|karpathos|heraklion|chania|souda|rethymn|agios nikolaos|kythira|monemvasia|gythio|nafplio|mycenae|katakolon|olympia|pylos|kalamata|itea|delphi|corinth|aegina|angistri|hydra|spetses|ermioni|sounion|kefalonia|cephalonia|argostoli|fiskardo|sami\b|ithaca|vathi|lefkada|meganisi|zakynthos|paxos|antipaxos|corfu|kerkyra|parga|preveza|nafpaktos|messolonghi|patras|volos|skiathos|skopelos|alonissos|skyros|evia|chalkida|karystos|thessaloniki|kavala|lesbos|mytilene|chios|limnos|thassos|syme|methoni|elafonisos|galaxidi", "GR"),
    (r"croatia|dubrovnik|split\b|hvar|lastovo|elaphiti|korcula|korčula|sibenik|šibenik|zadar|rijeka|rovinj|trogir|opatija|mali losinj|vis\b|mljet|makarska|pula|krk\b|cres\b", "HR"),
    (r"montenegro|kotor|budva|tivat", "ME"), (r"albania|sarand|durr[eë]s|vlor[eë]", "AL"), (r"sloven|koper|piran", "SI"),
    (r"society islands|tahiti|papeete|mo'?orea|bora bora|huahine|raiatea|taha'?a|maupiti|rangiroa|fakarava|anaa|marquesas|tuamotu|nuku hiva", "PF"),
    (r"gambia|banjul|kuntaur|janjanbureh|kunta kinteh|tendaba|\bkaur\b|bakau", "GM"), (r"senegal|dakar|djiffer|saloum", "SN"),
    (r"seychelles|mah[eé]\b|praslin|la digue|felicit|moyenne|cousin island|anse lazio|aride|st\.? anne|inter island quay|curieuse|cerf island|st\.? pierre\b", "SC"),
    (r"cape verde|cabo verde|\bsal\b|sal rei|boa vista|praia|fogo|mindelo|santo ant[aã]o|s[aã]o vicente|s[aã]o nicolau|maio", "CV"),
]
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
    "SC": "Seychelles", "PF": "French Polynesia", "GM": "The Gambia", "SN": "Senegal",
    "AT": "Austria", "HU": "Hungary", "SK": "Slovakia", "CZ": "Czechia", "NL": "the Netherlands", "CH": "Switzerland",
    "PL": "Poland", "LT": "Lithuania", "LV": "Latvia", "RS": "Serbia", "RO": "Romania", "BG": "Bulgaria", "CY": "Cyprus",
    "GG": "Guernsey", "IE": "Ireland", "IS": "Iceland", "FO": "the Faroe Islands", "SJ": "Svalbard", "GL": "Greenland",
    "VI": "US Virgin Islands", "CA": "Canada", "BZ": "Belize", "HN": "Honduras", "EC": "Ecuador", "PE": "Peru", "CL": "Chile",
    "AR": "Argentina", "UY": "Uruguay", "FK": "the Falkland Islands", "GS": "South Georgia", "AQ": "Antarctica",
    "SX": "Sint Maarten", "MF": "Saint-Martin", "GP": "Guadeloupe", "DM": "Dominica", "DO": "the Dominican Republic",
    "BS": "the Bahamas", "BQ": "Bonaire", "BM": "Bermuda", "MS": "Montserrat", "JP": "Japan", "KR": "South Korea",
    "CN": "China", "HK": "Hong Kong", "TW": "Taiwan", "VN": "Vietnam", "KH": "Cambodia", "TH": "Thailand", "SG": "Singapore",
    "MY": "Malaysia", "ID": "Indonesia", "PH": "the Philippines", "IN": "India", "LK": "Sri Lanka", "LA": "Laos",
    "MU": "Mauritius", "EG": "Egypt", "ZA": "South Africa", "GW": "Guinea-Bissau", "AU": "Australia", "NZ": "New Zealand",
    "FJ": "Fiji", "PN": "the Pitcairn Islands", "CR": "Costa Rica",
}
# Schengen members as of 2026 (Romania and Bulgaria in full since 1 Jan 2025), plus Monaco in practice.
# NOT Schengen: UK, Ireland, Cyprus, Serbia, Greenland, the Faroes, Svalbard, French overseas territories.
SCHENGEN = {"GR", "IT", "ES", "FR", "PT", "MT", "HR", "SI", "DE", "BE", "DK", "NO", "SE", "FI", "EE", "MC",
            "AT", "HU", "SK", "CZ", "NL", "CH", "PL", "LT", "LV", "IS", "RO", "BG", "LU", "LI"}
FOCUS = ["TR", "GR", "IT"]

# Search areas: the keys the home-page search and the filter use. Focus areas first.
AREAS = OrderedDict([
    ("turkiye", "Türkiye"), ("greece", "Greece and the Greek islands"), ("italy", "Italy, Sicily and Malta"),
    ("adriatic", "Croatia and the Adriatic"), ("western-med", "Western Mediterranean"),
    ("northern-europe", "Northern Europe and the fjords"), ("atlantic", "Atlantic islands and crossings"),
    ("rivers", "European rivers"), ("americas", "Caribbean and the Americas"), ("polar", "Arctic and Antarctica"),
    ("asia-pacific", "Asia and the Pacific"), ("africa-arabia", "Africa, the Red Sea and the Indian Ocean"),
    ("seychelles", "Seychelles"), ("tahiti", "Tahiti and French Polynesia"), ("world", "World and ocean crossings"),
])
# When a port's country is not in the table, CruiseHost's own region still places the sailing.
REGION_AREA = [
    (r"alaska|caribbean|america|panama|mexic|hawaii|galapagos|amazon|canada|new england", "americas"),
    (r"antarc|arctic|greenland|svalbard|north cape|northwest passage", "polar"),
    (r"asia|far east|japan|australia|pacific|indonesia|polynes", "asia-pacific"),
    (r"africa|red sea|indian ocean|arabia|gulf", "africa-arabia"),
    (r"norw|baltic|north europe|northeurope|british|iceland", "northern-europe"),
    (r"canary|atlantic ocean europe|around western europe|westeurope", "atlantic"),
    (r"western mediterranean", "western-med"), (r"eastern mediterranean|central mediterranean|mediterranean", "italy"),
    (r"world|trans", "world"),
]
AREA_OF = {"TR": "turkiye", "GR": "greece", "IT": "italy", "MT": "italy", "HR": "adriatic", "SI": "adriatic",
           "ME": "adriatic", "AL": "adriatic", "ES": "western-med", "FR": "western-med", "MC": "western-med",
           "GI": "western-med", "MA": "western-med", "TN": "western-med", "DZ": "western-med",
           "GB": "northern-europe", "DE": "northern-europe", "BE": "northern-europe", "DK": "northern-europe",
           "NO": "northern-europe", "SE": "northern-europe", "FI": "northern-europe", "EE": "northern-europe",
           "PT": "atlantic", "CV": "atlantic", "SC": "seychelles", "PF": "tahiti", "GM": "africa-arabia", "SN": "africa-arabia"}
for c in ("US", "PR", "TC", "JM", "VG", "AI", "KN", "AG", "BL", "MQ", "LC", "VC", "BB", "TT", "AW", "CW", "CO", "PA", "GT", "SV", "MX", "GF", "BR",
          "VI", "CA", "BZ", "HN", "EC", "PE", "CL", "AR", "UY", "SX", "MF", "GP", "DM", "DO", "BS", "BQ", "BM", "MS"):
    AREA_OF[c] = "americas"
for c in ("AT", "HU", "SK", "CZ", "NL", "CH", "PL", "LT", "LV", "RS", "RO", "BG", "IE", "GG", "IS", "FO"):
    AREA_OF.setdefault(c, "northern-europe")
AREA_OF.update({"SJ": "polar", "GL": "polar", "AQ": "polar", "FK": "polar", "GS": "polar",
                "JP": "asia-pacific", "KR": "asia-pacific", "CN": "asia-pacific", "HK": "asia-pacific", "TW": "asia-pacific",
                "VN": "asia-pacific", "KH": "asia-pacific", "TH": "asia-pacific", "SG": "asia-pacific", "MY": "asia-pacific",
                "ID": "asia-pacific", "PH": "asia-pacific", "LA": "asia-pacific", "AU": "asia-pacific", "NZ": "asia-pacific",
                "FJ": "asia-pacific", "PN": "tahiti", "IN": "africa-arabia", "LK": "africa-arabia", "MU": "africa-arabia",
                "EG": "africa-arabia", "ZA": "africa-arabia", "GW": "africa-arabia", "CR": "americas"})
AREA_OF["CY"] = "greece"   # Cyprus sits with the eastern Mediterranean sailings

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
    if port in AT_SEA or port_countries.is_scenery(port):
        return None
    if port in AMBIGUOUS:
        return AMBIGUOUS[port](route)
    if port in PORT_COUNTRY:
        return PORT_COUNTRY[port]
    for pat, cc in KEYWORD_COUNTRY:
        if re.search(pat, port, re.I):
            return cc
    return port_countries.country(port)


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
        out.append("Schengen rules for the whole cruise: a Schengen visa, unless your passport is Schengen visa-exempt. Calls in " + ", ".join(dict.fromkeys(sch)) + ".")
    if "TR" in cs:
        out.append("Türkiye: visa-free or e-visa for many passports, not all.")
    if cs & {"US", "PR", "VI"}:
        out.append("United States: visa or ESTA.")
    if cs & {"GB", "GG"}:
        out.append("United Kingdom: its own entry rules (an ETA for many passports), separate from Schengen.")
    if "IE" in cs:
        out.append("Ireland: outside Schengen, with its own entry rules.")
    if "RS" in cs:
        out.append("Serbia is outside Schengen: if you need a Schengen visa, it should be multiple-entry.")
    if "CY" in cs:
        out.append("Cyprus: EU but outside Schengen, with its own entry rules.")
    if cs & {"GL", "FO", "SJ"}:
        out.append("Greenland, the Faroes and Svalbard are outside Schengen: if you need a Schengen visa, it should be multiple-entry and valid for them.")
    if "CA" in cs:
        out.append("Canada: visa or eTA.")
    if cs & {"BL", "MQ", "GF", "PF"}:
        out.append("French overseas territories on this route are outside Schengen and have their own entry rules.")
    if cs == {"SC"}:
        out.append("Seychelles: visa-free on arrival for all nationalities.")
    out.append("We confirm the visa position for your passport before you pay anything.")
    return out


def visa_for(s) -> list[str]:
    lines = visa_lines(s["countries"])
    if s.get("unplaced"):
        lines.insert(-1, "Some stops on this route are not yet matched to a country above, so the list may be incomplete.")
    return lines


# ───────────────────────────── load and merge ─────────────────────────────
UNKNOWN_PORTS: dict[str, int] = {}
VARIETY_IMG = {"Greek Islands": "greece.jpg", "Greek Islands & Türkiye": "kusadasi.jpg", "Ionian Islands": "greece-3.jpg",
               "Greece: Corinth Canal": "greece-2.jpg", "Italy & Malta": "italy.jpg", "Croatia & Adriatic": "croatia-2.jpg",
               "Seychelles": "sey-1.jpg", "Tahiti & French Polynesia": "grand-borabora.jpg", "Cape Verde": "ship-harmony-v.jpg",
               "West Africa": "ship-harmony-v.jpg"}
# Yacht photos from the boutimar.ir repo, keyed by Variety's own spelling ("Pegasus"; boutimar.ir wrote "Pegasos").
YACHT_IMG = {"Galileo": "ship-galileo.jpg", "Variety Voyager": "ship-variety-voyager.jpg", "Callisto": "ship-callisto.jpg",
             "Harmony V": "ship-harmony-v.jpg", "Harmony G": "ship-harmony-g.jpg", "Pegasus": "ship-pegasos.jpg",
             "Pegasos": "ship-pegasos.jpg", "Panorama": "ship-panorama.jpg", "Panorama II": "ship-panorama-ii.jpg"}


def load() -> list[dict]:
    sailings = []
    # The direct CruiseHost sync (sync/cruisehost_sync.py) wins; the snapshot is the interim seed.
    live = SRC / "cruisehost-sailings.json"
    ex = json.loads((live if live.exists() else SRC / "cruisehost-explora-snapshot.json").read_text(encoding="utf-8"))
    for s in ex["sailings"]:
        if s.get("hidden"):
            continue
        route = [html.unescape(r) for r in s["route"]]   # CruiseHost sends "Barca d&#39;Alva"
        sid = s["cruisehostId"]
        deps = [d for d in s["departures"] if d["date"] >= TODAY]
        if not deps:
            continue
        line = s.get("line") or "Explora Journeys"
        sailings.append({
            "id": sid, "line": line, "lineKey": re.sub(r"[^a-z]+", "-", line.lower()).strip("-"), "kind": s.get("kind", "SEA"),
            "ships": [s["ship"]], "nights": s["nights"], "shipImage": s.get("shipImage"),
            "region": s["region"], "route": route, "title": title_for(route),
            "departures": deps, "priceFrom": min(d["priceFrom"] for d in deps if d["priceFrom"]), "currency": "EUR",
            "priceBasis": "CruiseHost lead fare: per person, cheapest available cabin, two sharing",
            "asOf": s.get("syncedAt") or ex["snapshotDate"], "source": "CruiseHost, the cruise lines' booking system",
            "itinerary": [[pretty_port(p), ""] for p in route] if len(route) == s["nights"] + 1 else None,
            "flags": [],
        })
    vlive = SRC / "variety-sailings.json"
    if vlive.exists():
        vs = json.loads(vlive.read_text(encoding="utf-8"))
        for v in vs["sailings"]:
            deps = [d for d in v["departures"] if d["date"] >= TODAY]
            if not deps:
                continue
            fares = [d["priceFrom"] for d in deps if d.get("priceFrom") and not d.get("soldOut")]
            route = [r for r in v["route"] if not re.match(r"Day \d+\s*\|", r)]
            if len(route) < 2:
                route = [p.strip() for d in v["itinerary"] for p in re.split(r"\s+[–-]\s+", d[0]) if p.strip()]
            sailings.append({
                "id": v["id"], "line": "Variety Cruises", "lineKey": "variety-cruises", "kind": "SEA", "ships": v["ships"],
                "nights": v["nights"], "region": v["region"], "route": route, "title": v["title"],
                "departures": [{"date": d["date"], "priceFrom": d.get("priceFrom"), "soldOut": d.get("soldOut", False), "ship": d.get("ship")} for d in deps],
                "priceFrom": min(fares) if fares else None, "currency": "EUR",
                "priceBasis": "Variety Cruises fare: per person, cheapest cabin category with cabins left, port charges excluded",
                "asOf": vs["synced"], "source": "Variety Cruises", "itinerary": v["itinerary"],
                "included": v.get("included", []), "notIncluded": v.get("notIncluded", []),
                "image": "media/variety/" + VARIETY_IMG.get(v["region"], "variety-hero.jpg"), "flags": [],
            })
        va = {"itineraries": []}
    else:
        va = json.loads((SRC / "variety-catalogue-2026-27.json").read_text(encoding="utf-8"))
    for v in va["itineraries"]:
        route = [d[0] for d in v["itinerary"]]
        sailings.append({
            "id": v["id"], "line": "Variety Cruises", "lineKey": "variety-cruises", "kind": "SEA", "ships": v["ships"], "nights": v["nights"],
            "region": v["region"], "route": route, "title": v["title"], "departures": [],
            "priceFrom": v["priceFrom"], "currency": "EUR", "priceBasis": va["priceBasis"],
            "asOf": None, "source": "Variety Cruises catalogue 2026–27", "itinerary": v["itinerary"],
            "image": "media/variety/" + v["image"], "flags": v.get("flags", []),
        })
    for s in sailings:
        codes = [c for c in (country_of(p, s["route"]) for p in s["route"]) if c]
        unknown = [p for p in s["route"] if p not in AT_SEA and not port_countries.is_scenery(p) and not country_of(p, s["route"])]
        for u in unknown:
            UNKNOWN_PORTS[u] = UNKNOWN_PORTS.get(u, 0) + 1
        s["countries"] = list(dict.fromkeys(codes))
        s["focus"] = [c for c in FOCUS if c in s["countries"]]
        areas = [AREA_OF[c] for c in s["countries"] if c in AREA_OF]
        if s.get("kind") == "RIVER":
            areas = ["rivers"]
        if not areas:
            areas = [next((a for pat, a in REGION_AREA if re.search(pat, s.get("region") or "", re.I)), "world")]
        s["areas"] = list(dict.fromkeys(areas))
        s["months"] = sorted({d["date"][:7] for d in s["departures"]})
        s["unplaced"] = unknown
        s["visa"] = visa_for(s)
        s["url"] = f"journeys/{s['id']}.html"
        if s["lineKey"] == "explora-journeys":
            key = "med" if s["focus"] or "adriatic" in s["areas"] else next((a for a in s["areas"] if a in EXPLORA_IMG), "med")
            pool = EXPLORA_IMG[key]
            s["image"] = m(pool[int(hashlib.sha1(s["id"].encode()).hexdigest(), 16) % len(pool)])
        elif not s.get("image"):
            # Another CruiseHost line: its own ship photo if the sync fetched one, else none.
            # Never borrow a different line's photography.
            s["image"] = s.get("shipImage")
    # Türkiye/Greece/Italy first, then the soonest departure, then price
    sailings.sort(key=lambda s: (0 if s["focus"] else 1, s["departures"][0]["date"] if s["departures"] else "9999", s["priceFrom"] or 10**9))
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


STATIC_CARDS = 36   # written into the HTML for crawlers and no-JS; journeys.js renders the rest from the index


def index_record(s) -> dict:
    """Compact per-sailing record for the listing and the contact prefill (the full inventory
    is ~3 MB; this is what a phone actually downloads)."""
    open_deps = [d for d in s["departures"] if not d.get("soldOut")]
    dep = open_deps[0]["date"] if open_deps else (s["departures"][0]["date"] if s["departures"] else None)
    ports = list(dict.fromkeys(p for p in (pretty_port(x) for x in s["route"]) if p != "At sea"))
    return {"id": s["id"], "u": s["url"], "t": s["title"], "l": s["line"], "k": s["lineKey"], "s": s["ships"], "n": s["nights"],
            "d": dep, "dc": len(s["departures"]), "p": s["priceFrom"], "a": s["areas"], "m": s["months"],
            "f": [COUNTRY[c] for c in s["focus"]], "i": s.get("image"), "r": ports[:9] + (["…"] if len(ports) > 9 else [])}


def card(s) -> str:
    open_deps = [d for d in s["departures"] if not d.get("soldOut")]
    dep = open_deps[0]["date"] if open_deps else (s["departures"][0]["date"] if s["departures"] else None)
    when = (f"Next departure {date.fromisoformat(dep).strftime('%-d %b %Y')}" if dep else "Departure dates on request")
    more = f" · {len(s['departures'])} dates" if len(s["departures"]) > 1 else ""
    chips = "".join(f'<span class="chip">{esc(COUNTRY[c])}</span>' for c in s["focus"])
    ship = " or ".join(s["ships"])
    return (f'<a class="jcard2" href="{esc(s["url"])}" data-areas="{" ".join(s["areas"])}" data-months="{" ".join(s["months"]) or "request"}" '
            f'data-line="{s["lineKey"]}" data-nights="{s["nights"]}" data-price="{s["priceFrom"] or 999999}" data-date="{dep or "9999"}" data-focus="{1 if s["focus"] else 0}">'
            + (f'<img src="{esc(s["image"])}" alt="" loading="lazy">' if s.get("image") else '<div class="noimg"></div>') +
            f'<div class="jc-body"><small>{esc(s["line"])} · {esc(ship)}</small>'
            f'<h3>{esc(s["title"])}</h3>'
            f'<p class="jc-route">{esc(" · ".join(dict.fromkeys(p for p in (pretty_port(x) for x in s["route"]) if p != "At sea")))}</p>'
            f'<div class="jc-chips">{chips}</div>'
            f'<div class="jc-foot"><span>{s["nights"]} nights<br><em>{esc(when)}{more}</em></span>'
            + (f'<span class="jc-price">from <b>{euro(s["priceFrom"])}</b><em>per person</em></span>' if s["priceFrom"] else '<span class="jc-price"><b style="font-size:1rem">Fare on request</b></span>')
            + '</div></div></a>')


def and_list(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def fare_sources(sailings) -> str:
    """Say where the fares on the page come from, from the records themselves."""
    src = {s["source"] for s in sailings}
    parts = []
    if any(x.startswith("CruiseHost") for x in src):
        parts.append("CruiseHost (the cruise lines' booking system)")
    if "Variety Cruises" in src:
        parts.append("Variety Cruises' own booking pages")
    if any("catalogue" in x for x in src):
        parts.append("the Variety Cruises 2026–27 catalogue")
    return ("Fares are read from " + and_list(parts) + ", and each sailing shows the date it was read.") if parts else ""


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
  <p>{len(sailings)} sailings from {and_list(sorted({s["line"] for s in sailings}))}. {n_focus} of them call in Türkiye, Greece or Italy, and those come first. {fare_sources(sailings)} Every fare is confirmed with the line before you commit.</p></div>
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
    <div class="jgrid2" id="jgrid" data-index="data/journeys-index.json">
{chr(10).join(card(s) for s in sailings[:STATIC_CARDS])}
    </div>
    <p style="text-align:center;margin-top:28px"><button class="btn" id="fmore" type="button" style="color:var(--text)">Show more sailings</button></p>
    <p class="fine" id="fempty" hidden>Nothing matches those choices. Clear one of them, or <a href="contact.html" style="border-bottom:1px solid var(--accent)">tell us what you have in mind</a>.</p>
    <p class="fine" style="margin-top:32px">Sources: {", ".join(f"{k} ({v})" for k, v in lines.items())}. Silversea and Scenic join when their CruiseHost inventory is connected.</p>
  </div>
</section>
'''
    return page(head, nav, foot, slug="journeys.html", title="Journeys · Cruise24",
                desc=f"{len(sailings)} sailings from {len({s['line'] for s in sailings})} cruise lines, with Türkiye, Greece and Italy first. Real fares, dates and routes, confirmed with the line before you book.",
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
        multi = len({d.get("ship") for d in s["departures"] if d.get("ship")}) > 1
        def fare(d):
            return "Sold out" if d.get("soldOut") else (euro(d["priceFrom"]) if d.get("priceFrom") else "On request")
        fares = ('<div class="fares-wrap"><table class="fares"><thead><tr><th>Departure</th>' + ("<th>Ship</th>" if multi else "") + '<th>From, per person</th></tr></thead><tbody>' +
                 "".join(f'<tr{" class=sold" if d.get("soldOut") else ""}><td>{date.fromisoformat(d["date"]).strftime("%a %-d %b %Y")}</td>' + (f'<td>{esc(d.get("ship") or "")}</td>' if multi else "") + f'<td>{fare(d)}</td></tr>' for d in s["departures"]) +
                 "</tbody></table></div>")
    else:
        fares = (f'<p class="bigfare">from <b>{euro(s["priceFrom"])}</b> per person</p>' if s["priceFrom"] else "") + '<p class="fine">No departure dates in the source. Dates and the live fare come with your quote.</p>'
    shipnote = ""
    if s["lineKey"] not in ("explora-journeys", "variety-cruises"):
        what = "river ship" if s.get("kind") == "RIVER" else "ship"
        pic = f'<div class="yachts"><figure><img src="{esc(s["shipImage"])}" alt="{esc(s["ships"][0])}" loading="lazy"><figcaption>{esc(s["ships"][0])}</figcaption></figure></div>' if s.get("shipImage") else ""
        shipnote = f'{pic}<p>{esc(s["ships"][0])}, a {what} of {esc(s["line"])}. Ship details and what the fare includes come with your quote.</p>'
    elif s["lineKey"] == "explora-journeys":
        y = EXPLORA_YEAR.get(s["ships"][0])
        shipnote = f'<p>{esc(s["ships"][0])}, all-suite, Explora Journeys{f", in service since {y}" if y and y <= 2026 else f", entering service in {y}" if y else ""}. What the Explora fare includes is <a href="index.html#inclusions" style="border-bottom:1px solid var(--accent)">listed on the home page</a>.</p>'
    else:
        imgs = "".join(f'<figure><img src="media/variety/{esc(YACHT_IMG[n])}" alt="{esc(n)}" loading="lazy"><figcaption>{esc(n)}</figcaption></figure>' for n in s["ships"] if n in YACHT_IMG)
        which = ("This route is sailed by " + " or ".join(s["ships"]) + "; each departure's yacht is in the fares table.") if len(s["ships"]) > 1 else ""
        inc = ""
        if s.get("included"):
            inc = ('<div class="grid2" style="margin-top:18px"><div><h3 style="font-size:1.1rem">Included</h3><ul class="ticks">' + "".join(f"<li>{esc(x)}</li>" for x in s["included"]) +
                   '</ul></div><div><h3 style="font-size:1.1rem">Not included</h3><ul class="ticks">' + "".join(f"<li>{esc(x)}</li>" for x in s.get("notIncluded", [])) + "</ul></div></div>")
        shipnote = f'<div class="yachts">{imgs}</div><p>Variety Cruises: small ships of 50 to 72 guests. {esc(which)}</p>{inc}' + ("" if inc else "<p>Inclusions are confirmed with your quote.</p>")
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
                desc=f"{s['line']} {ship}: {s['nights']} nights, {pretty_port(s['route'][0])} to {pretty_port(s['route'][-1])}." + (f" From {euro(s['priceFrom'])} per person." if s["priceFrom"] else ""),
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


def recount(path: str, sailings) -> str:
    """Pages that quote "N sailings to book" next to a journeys.html#<area> link get the live count."""
    html_ = (HERE / path).read_text(encoding="utf-8")
    def fix(mt):
        area = mt.group(1)
        n = sum(1 for s in sailings if area in s["areas"])
        return mt.group(0).replace(mt.group(2), str(n))
    return re.sub(r'journeys\.html#([a-z-]+)\.any"[^<]*?(?:<[^>]+>[^<]*?){0,8}?(\d+) sailings to book', fix, html_)


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
    checks["_unknownPorts"] = dict(sorted(UNKNOWN_PORTS.items(), key=lambda kv: -kv[1]))
    out = {"data/sailings.json": json.dumps({"generated": TODAY, "count": len(public), "sailings": public}, ensure_ascii=False, indent=1) + "\n",
           "data/data-checks.json": json.dumps({"_about": "Records to verify against the line before launch. Internal: do not deploy.", "checks": checks}, ensure_ascii=False, indent=1) + "\n",
           "journeys.html": listing(sailings, head, nav, foot),
           "data/journeys-index.json": json.dumps([index_record(s) for s in sailings], ensure_ascii=False, separators=(",", ":")),
           "index.html": home_search(sailings),
           "destinations.html": recount("destinations.html", sailings),
           "ports.html": ports_page(sailings, head, nav, foot)}
    # ships.html and itineraries.html are redirects now (to lines.html#ships, destinations.html#itineraries)
    static = ["", "journeys.html", "destinations.html", "ports.html", "lines.html", "mice.html", "about.html",
              "journal.html", "contact.html", "conditions.html", "imprint.html", "privacy.html"]
    # lastmod only where it is known: a sailing changes when its source was last synced, the
    # generated listings with every build, the hand-written pages have no date to give. With a
    # daily rebuild, stamping every URL with today would tell search engines all 1,700 changed.
    built = {"", "journeys.html", "destinations.html", "ports.html"}
    entries = [(f"https://cruise24.me/{p}", TODAY if p in built else None) for p in static] + \
              [(f"https://cruise24.me/{s['url']}", s.get("asOf")) for s in sailings]
    out["sitemap.xml"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                          + "".join(f"  <url><loc>{u}</loc>" + (f"<lastmod>{m}</lastmod>" if m else "") + "</url>\n" for u, m in entries)
                          + "</urlset>\n")
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
