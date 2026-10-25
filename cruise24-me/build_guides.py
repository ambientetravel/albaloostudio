#!/usr/bin/env python3
"""
build_guides.py — route guides and visa guides, built from the same inventory as the sailing pages.

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

Called by build_journeys.py, never on its own, so a guide is rebuilt every night with the
inventory it describes: it can never list a sailing that is gone or link to a retired page.

What is written by hand here, and only this: what a route IS (geography, the order of the
rivers or coasts), and how the visa rule works. Everything else on a guide is read from the
inventory at build time: which lines and ships sail it, how many sailings, nights, months,
the ports called at most, every departure with a link to its sailing page, and the visa line
each sailing page already carries. No fare, date, inclusion or photo credit is typed here.

Brief: HANDOFF-traffic.md (25 Oct 2026). The route choice follows Search Console: the queries
Google already shows cruise24.me for at positions 40-70.
"""

from __future__ import annotations

import collections
import html
import re
from datetime import date

SEA = re.compile(r"(?i)^(cruising|at sea|sea day|crossing|cruise ahead)")


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def ports(s) -> list[str]:
    return [p for p in s["route"] if not SEA.match(p)]


def ends(s) -> tuple[str, str]:
    p = ports(s)
    return (p[0], p[-1]) if p else ("", "")


def between(a: str, b: str):
    """Sailings that start at one end and finish at the other, either direction."""
    ra, rb = re.compile(a, re.I), re.compile(b, re.I)

    def m(s):
        x, y = ends(s)
        return bool((ra.search(x) and rb.search(y)) or (rb.search(x) and ra.search(y)))
    return m


def calls(pattern: str):
    rx = re.compile(pattern, re.I)
    return lambda s: any(rx.search(p) for p in s["route"])


def all_of(*fns):
    return lambda s: all(f(s) for f in fns)


def round_trip(pattern: str):
    rx = re.compile(pattern, re.I)

    def m(s):
        x, y = ends(s)
        return bool(rx.search(x) and rx.search(y))
    return m


# ── the guides ───────────────────────────────────────────────────────────────
# `intro` is the only hand-written copy: geography and how the route works, nothing that
# changes with a season or a price list. Keep it that way when adding one.
GUIDES = [
    {
        "slug": "rhine-river-cruise-amsterdam-zurich",
        "title": "Rhine river cruises between Amsterdam and Zurich",
        "short": "Rhine: Amsterdam ↔ Zurich",
        "query": "Scenic river cruise Amsterdam to Zurich",
        "where": "River (Danube, Rhine, Douro)",
        "match": between(r"^amsterdam", r"^zurich|^basel"),
        "intro": [
            "The Rhine rises in the Swiss Alps and runs to the North Sea: past Basel, along the border between France and Germany, through the gorge of the Middle Rhine and across the Netherlands. A cruise between Amsterdam and Zurich follows most of that course, and you can sail it in either direction.",
            "Zurich is not on the Rhine; it sits on Lake Zurich and the Limmat. On these itineraries the ship is joined or left at Basel, as far up the Rhine as river cruise ships go, and the inventory lists the Zurich days alongside it. Between the two ends the stops are the old river towns: Strasbourg, Rüdesheim, Koblenz where the Moselle joins, Cologne. Some departures add a detour up the Moselle or into Belgium; the ports for each sailing are on its own page.",
        ],
    },
    {
        "slug": "river-cruise-prague-amsterdam",
        "title": "River cruises between Prague and Amsterdam",
        "short": "Prague ↔ Amsterdam",
        "query": "Prague to Amsterdam river cruise",
        "where": "River (Danube, Rhine, Douro)",
        "match": between(r"^prague", r"^amsterdam"),
        "intro": [
            "Prague sits on the Vltava, which these river ships do not sail. A Prague–Amsterdam cruise therefore opens (or closes) with days in Prague on land, and the inventory shows the river joined further on, then sailed through three rivers: the Danube, the Main and the Rhine.",
            "The link between them is the Main–Danube Canal, which lets a river ship cross from the Danube basin, which drains to the Black Sea, into the Rhine basin, which drains to the North Sea. That is why one voyage can call at Vienna, Passau, Regensburg, Nuremberg, Würzburg and Cologne. The exact order, and which cities get a full day, is on each sailing's page.",
        ],
    },
    {
        "slug": "river-cruise-amsterdam-budapest",
        "title": "River cruises between Amsterdam and Budapest",
        "short": "Amsterdam ↔ Budapest",
        "query": "Scenic Amsterdam to Budapest",
        "where": "River (Danube, Rhine, Douro)",
        "match": between(r"^amsterdam", r"^budapest"),
        "intro": [
            "Amsterdam to Budapest is the classic crossing of Europe by river: down (or up) the Rhine, along the Main, through the Main–Danube Canal, and along the Danube through Germany, Austria and Slovakia into Hungary.",
            "Expect the Rhine towns at one end, Bavaria in the middle (Würzburg, Bamberg, Nuremberg, Regensburg, Passau), then the Wachau valley, Vienna and Bratislava before Budapest. The inventory sails it in both directions; the stops for each departure are on its own page.",
        ],
    },
    {
        "slug": "danube-river-cruise-budapest-bucharest",
        "title": "Lower Danube river cruises: Budapest to Bucharest",
        "short": "Danube: Budapest ↔ Bucharest",
        "query": "Scenic Budapest to Bucharest",
        "where": "River (Danube, Rhine, Douro)",
        "match": between(r"^budapest", r"bucharest"),
        "intro": [
            "Below Budapest the Danube turns south through Hungary, Croatia and Serbia, and passes Belgrade. It then forms the border between Serbia and Romania through the Iron Gates gorge, and the border between Bulgaria and Romania on its way to the Black Sea.",
            "Bucharest is not on the river. These itineraries end (or begin) with the road between the Danube and the city, and the inventory lists the last river ports before it. Fewer ships sail this stretch than the upper Danube, so departures are fewer; every one in the inventory is listed below.",
        ],
    },
    {
        "slug": "danube-river-cruise-budapest-prague-munich",
        "title": "Upper Danube river cruises: Budapest, Vienna, Prague and Munich",
        "short": "Danube: Budapest ↔ Prague / Munich",
        "query": "Danube river cruise Prague to Budapest",
        "where": "River (Danube, Rhine, Douro)",
        "match": between(r"^budapest", r"^prague|^munich"),
        "intro": [
            "The upper Danube links Budapest, Bratislava, Vienna, the Wachau valley and Passau, on the border between Austria and Germany. Neither Prague nor Munich is on the river. Itineraries that start or end in one of them spend the first or last days in that city on land, and join the ship on the Danube.",
            "It is the shortest of the classic central European river routes, and the one with the most capital cities per day of sailing.",
        ],
    },
    {
        "slug": "west-africa-cape-verde-cruise",
        "title": "Cruises to West Africa and the Cape Verde islands",
        "short": "West Africa & Cape Verde",
        "query": "Islands of Cape Verde archipelago cruise",
        "where": "Somewhere else",
        "match": calls(r"mindelo|praia|sal rei|palmeira|fogo|santo ant|dakar|banjul|gambia|bijagos|bissau|^tema|lome|cotonou|takoradi"),
        "intro": [
            "Cape Verde is an archipelago of ten volcanic islands in the Atlantic, off the coast of Senegal. Ocean ships call on the way between Europe, the Caribbean and South America. Small expedition ships sail island-to-island itineraries of their own.",
            "Further south and east the inventory includes the Gambia River, sailed inland from Banjul, and the coast of West Africa from Dakar to the Gulf of Guinea. Visa rules here vary country by country, and several of these routes also call in the Canary Islands, Madeira or Portugal, which brings in Schengen rules. Each sailing below carries its own visa line.",
        ],
    },
    {
        "slug": "small-ship-cruise-venice-dubrovnik-adriatic",
        "title": "Small-ship cruises from Venice to Dubrovnik and the Adriatic",
        "short": "Adriatic: Venice ↔ Dubrovnik",
        "query": "Small ship cruises from Venice to Dubrovnik",
        "where": "Mediterranean",
        "match": all_of(calls(r"venice|fusina|trieste"), calls(r"dubrovnik")),
        "intro": [
            "The eastern shore of the Adriatic runs from the Venetian lagoon down the Croatian coast to Dubrovnik and on to the Bay of Kotor in Montenegro. Its islands and walled towns are close together, which suits smaller ships that can use ports and anchorages larger ones cannot.",
            "Large cruise ships no longer sail through the centre of Venice: since 2021 they use terminals outside the historic city, such as Fusina, and the inventory names the port each line uses. Croatia joined Schengen in 2023, so an Adriatic cruise is a Schengen cruise even when it also calls in Montenegro or Albania.",
        ],
    },
    {
        "slug": "cruise-istanbul-to-athens",
        "title": "Cruises between Istanbul and Athens",
        "short": "Istanbul ↔ Athens",
        "query": "Cruise from Istanbul to Athens",
        "where": "Mediterranean",
        "match": between(r"^istanbul", r"piraeus|^athens"),
        "intro": [
            "Istanbul and Athens are joined by the Aegean: out of the Bosphorus and the Sea of Marmara, past the Dardanelles, and down the Turkish coast and the Greek islands to Piraeus, the port of Athens.",
            "Starting in Istanbul does not keep a cruise out of Schengen. Athens and every Greek island are in the Schengen area, so the Schengen visa rule applies to the whole voyage the moment one Greek port is on it. Each departure below carries its visa line.",
        ],
    },
    {
        "slug": "greek-islands-cruise-from-athens",
        "title": "Greek island cruises from Athens",
        "short": "Greek islands from Athens",
        "query": "Variety Cruises Greece",
        "where": "Greek islands",
        "match": round_trip(r"piraeus|^athens|lavrio"),
        "intro": [
            "Round trips from Athens start and end at Piraeus, or at one of the smaller harbours near the city such as Lavrio. Between those two days they sail the Cyclades, the Dodecanese or the Saronic and Ionian islands, depending on the itinerary.",
            "Small ships can use island harbours the big ones anchor off, and a week is enough for five or six islands. Every Greek port is in Schengen, so these are Schengen cruises; the islands and visa line for each departure are below.",
        ],
    },
    {
        "slug": "cruise-buenos-aires-valparaiso-cape-horn",
        "title": "Cruises between Buenos Aires and Valparaíso around Cape Horn",
        "short": "Buenos Aires ↔ Valparaíso",
        "query": "Cruising between Buenos Aires and Valparaiso",
        "where": "Somewhere else",
        "match": lambda s: (between(r"buenos aires", r"valpara|san antonio")(s)
                            or (calls(r"buenos aires")(s) and calls(r"valpara|san antonio")(s))),
        "intro": [
            "Valparaíso is Chile's port for Santiago, and Buenos Aires is Argentina's capital on the Río de la Plata. Between them a ship goes round the bottom of South America. It sails the Chilean fjords, through or around the Strait of Magellan and past Cape Horn, and calls at Ushuaia, the Falkland Islands and the Uruguayan coast.",
            "Some voyages in the inventory continue to South Georgia and the Antarctic Peninsula before returning north. Those details are in each sailing's port list.",
        ],
    },
]

# Visa guides: the copy is the rule, the numbers and examples are the inventory's own.
VISA_GUIDES = [
    {"slug": "schengen-visa-mediterranean-cruise",
     "title": "Do I need a Schengen visa for a Mediterranean cruise?",
     "short": "Schengen visa for a Mediterranean cruise"},
    {"slug": "cruises-on-a-uae-gcc-residence-visa",
     "title": "Which cruises can I take on a UAE or GCC residence visa?",
     "short": "Cruising on a UAE or GCC residence visa"},
]

MED = re.compile(r"(?i)mediterran|adriatic|aegean|greek")


# ── helpers ──────────────────────────────────────────────────────────────────
def next_dep(s):
    deps = [d for d in s["departures"] if not d.get("soldOut")] or s["departures"]
    return deps[0]["date"] if deps else None


def fmt_date(iso: str | None) -> str:
    return date.fromisoformat(iso).strftime("%-d %b %Y") if iso else "Dates on request"


def visa_short(s) -> str:
    v = (s.get("visa") or [""])[0]
    if v.startswith("Schengen"):
        return "Schengen"
    if v.startswith("French overseas"):
        return "French overseas rules"
    if v.startswith("Greenland"):
        return "Greenland, Faroes, Svalbard"
    m = re.match(r"([A-Z][A-Za-zü ]+?)(?:[:.,]| rules| visa| for)", v)
    if m and m.group(1).strip() not in ("We confirm the", "Some stops on this route are not yet matched to a country above", "French overseas territories on this route are outside Schengen and have"):
        return m.group(1).strip()
    if v.startswith("French overseas"):
        return "French overseas rules"
    return "Confirmed for your passport"


ROUTE_SPECIFIC = re.compile(r"\s*(Calls in [^.]*\.|Some stops on this route are not yet matched[^.]*\.)")


def visa_rule(s) -> str:
    """The sailing's visa wording without the parts that only fit that one route."""
    return ROUTE_SPECIFIC.sub("", " ".join(s.get("visa") or [])).strip()


def and_list(items: list[str]) -> str:
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def words(html_text: str) -> int:
    return len(re.sub(r"<[^>]+>", " ", html_text).split())


def form(where: str, topic: str) -> str:
    opts = ["Not sure yet", "Mediterranean", "Greek islands", "River (Danube, Rhine, Douro)", "Red Sea / Persian Gulf",
            "Northern Europe", "Caribbean", "Alaska", "Asia", "Somewhere else"]
    sel = "".join(f'<option{" selected" if o == where else ""}>{esc(o)}</option>' for o in opts)
    return f'''<form class="form" action="api/enquiry.php" method="post" data-enquiry>
    <label>Name <input type="text" name="name" autocomplete="name" required></label>
    <label>Email <input type="email" name="email" autocomplete="email" required></label>
    <label>Travellers <select name="pax"><option>2</option><option>1</option><option>3</option><option>4</option><option>5+</option></select></label>
    <label>Where <select name="where">{sel}</select></label>
    <label class="full">Roughly when <input type="text" name="when" placeholder="e.g. Easter 2027, or any week in October"></label>
    <label class="full">Anything we should know <textarea name="notes" placeholder="Passports on board, a birthday, a wheelchair">{esc(topic)}: </textarea></label>
    <label class="hp" aria-hidden="true">Leave this empty <input type="text" name="c24_nb" tabindex="-1" autocomplete="off" data-lpignore="true" data-1p-ignore></label>
      <button class="btn solid full" type="submit">Send request</button>
    <p class="note" role="status" aria-live="polite">No payment now. We check capacity, the final fare and the visa position for your passport with the line before you commit.</p>
  </form>'''


def sailing_rows(ss) -> str:
    rows = []
    for s in sorted(ss, key=lambda s: (next_dep(s) or "9999", s["title"])):
        a, b = ends(s)
        more = len(s["departures"]) - 1
        rows.append(
            f'<tr><td>{esc(fmt_date(next_dep(s)))}' + (f' <span class="fine">+{more} more</span>' if more > 0 else "") + "</td>"
            f'<td><a href="{esc(s["url"])}">{esc(s["title"])}</a></td>'
            f'<td>{s["nights"]}</td><td>{esc(s["line"])} · {esc(" / ".join(s["ships"]))}</td>'
            f'<td>{esc(visa_short(s))}</td></tr>')
    return ('<div class="fares-wrap"><table class="fares"><thead><tr><th>Next departure</th><th>Sailing</th><th>Nights</th>'
            '<th>Line · ship</th><th>Visa</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")


def facts(ss) -> str:
    lines = collections.Counter(s["line"] for s in ss)
    ships = collections.defaultdict(set)
    for s in ss:
        ships[s["line"]].update(s["ships"])
    nights = sorted({s["nights"] for s in ss})
    months = sorted({d["date"][:7] for s in ss for d in s["departures"]})
    deps = sum(len(s["departures"]) for s in ss)
    stop = collections.Counter()
    for s in ss:
        stop.update(set(ports(s)[1:-1]))
    top = [p for p, _ in stop.most_common(8)]
    who = "".join(f"<li><b>{esc(l)}</b>: {n} sailing{'s' if n != 1 else ''}, on {esc(and_list(sorted(ships[l])))}</li>" for l, n in lines.most_common())
    span = (f"{date.fromisoformat(months[0] + '-01').strftime('%B %Y')} to {date.fromisoformat(months[-1] + '-01').strftime('%B %Y')}"
            if months else "dates on request")
    nights_txt = f"{nights[0]} to {nights[-1]} nights" if len(nights) > 1 else f"{nights[0]} nights"
    return (f'<p>In our inventory today: <b>{len(ss)} itineraries</b> with <b>{deps} departures</b>, {nights_txt}, '
            f'departing from {span}.</p><h2 class="h-sub">Who sails it</h2><ul class="ticks">{who}</ul>'
            + (f'<h2 class="h-sub">Ports called at most often</h2><p>{esc(and_list(top))}.</p>' if top else ""))


def visa_block(ss) -> str:
    texts, label = collections.Counter(), {}
    for s in ss:
        t = visa_rule(s)
        texts[t] += 1
        label[t] = visa_short(s)
    items = "".join(f"<li><b>{esc(label[t])}</b>: {esc(t)} <span class=\"fine\">({n} of {len(ss)} itineraries)</span></li>" for t, n in texts.most_common())
    return (f'<h2 class="h-sub">Visa on this route</h2><p>The rule follows the ports, not where you board: one call in a Schengen '
            f'country puts the whole cruise under Schengen rules. Your residence visa does not change this; your passport does.</p>'
            f'<ul class="ticks">{items}</ul>')


def guide_page(g, ss, all_guides, page_fn) -> str:
    related = "".join(f'<li><a href="guides/{esc(o["slug"])}.html">{esc(o["short"])}</a></li>' for o in all_guides if o["slug"] != g["slug"])
    body = f'''<section class="page-hero" style="min-height:auto;padding-bottom:40px">
  <div class="wrap"><span class="kicker">Route guide</span><h1>{esc(g["title"])}</h1>
  <p>{len(ss)} itineraries in our inventory, each linked below to its own page with ports, ship and fare.</p></div>
</section>
<section class="section light" style="padding-top:40px"><div class="wrap sailing">
  <div>
    <span class="kicker">The route</span>
    {"".join(f"<p>{esc(p)}</p>" for p in g["intro"])}
    {facts(ss)}
    <h2 class="h-sub">Every departure in the inventory</h2>
    <p class="fine">Fares, cabins and the full port list are on each sailing's page, with the date the fare was read. We confirm the live fare with the line before you commit.</p>
    {sailing_rows(ss)}
    {visa_block(ss)}
  </div>
  <aside class="farebox">
    <span class="kicker">Ask about this route</span>
    {form(g["where"], g["short"])}
    <h2 class="h-sub" style="font-size:1.1rem">More route guides</h2>
    <ul class="ticks">{related}</ul>
  </aside>
</div></section>
'''
    return page_fn(slug=f"guides/{g['slug']}.html", base="../", title=f"{g['title']} · Cruise24",
                   desc=f"{g['title']}: {len(ss)} itineraries from {and_list(sorted({s['line'] for s in ss}))}, with every departure, the ports and the visa rule.",
                   body=body)


def schengen_page(sailings, page_fn) -> str:
    med = [s for s in sailings if MED.search(s["region"]) or any(a in ("turkiye", "greece", "italy", "adriatic", "western-med") for a in s.get("areas", []))]
    sch = [s for s in med if visa_short(s) == "Schengen"]
    non = [s for s in med if visa_short(s) != "Schengen"]
    ist = [s for s in sch if re.match(r"(?i)istanbul", ends(s)[0])]
    body = f'''<section class="page-hero" style="min-height:auto;padding-bottom:40px">
  <div class="wrap"><span class="kicker">Visa guide</span><h1>Do I need a Schengen visa for a Mediterranean cruise?</h1>
  <p>Almost always the Schengen rules apply. Of the {len(med)} Mediterranean itineraries in our inventory today, {len(sch)} call at a Schengen port.</p></div>
</section>
<section class="section light" style="padding-top:40px"><div class="wrap sailing">
  <div>
    <h2 class="h-sub">The rule</h2>
    <p>A cruise is judged by the ports it calls at, not by where you board. If even one port is in a Schengen country, such as Greece, Italy, Spain, France, Malta or Croatia, the Schengen visa rules apply to the whole voyage. You need a Schengen visa for it unless your passport is Schengen visa-exempt.</p>
    <p>Boarding outside Schengen does not change that. A cruise from Istanbul that calls at a single Greek island is a Schengen cruise. Of the itineraries in our inventory that start in Istanbul, {len(ist)} call at a Schengen port.</p>
    <p>Where you live does not change it either. A UAE or other GCC residence visa is not a Schengen visa; what decides is your passport.</p>
    <h2 class="h-sub">Mediterranean sailings outside Schengen</h2>
    {("<p>These Mediterranean itineraries in our inventory have no Schengen port. Each follows the rules of the countries it does call at:</p>" + sailing_rows(non)) if non else "<p>None in our inventory today: every Mediterranean itinerary we carry calls at a Schengen port.</p>"}
    <h2 class="h-sub">Sailings from Istanbul that are still Schengen</h2>
    {sailing_rows(ist[:30]) if ist else "<p>None in our inventory today.</p>"}
    <h2 class="h-sub">What we do</h2>
    <p>Every sailing page carries its visa line, and we confirm the position for your own passport before you pay anything.</p>
  </div>
  <aside class="farebox">
    <span class="kicker">Ask us about your passport</span>
    {form("Mediterranean", "Schengen visa question")}
  </aside>
</div></section>
'''
    return page_fn(slug="guides/schengen-visa-mediterranean-cruise.html", base="../",
                   title="Do I need a Schengen visa for a Mediterranean cruise? · Cruise24",
                   desc="One Schengen port puts the whole cruise under Schengen rules, even from Istanbul. Which Mediterranean sailings are and are not Schengen, from our live inventory.",
                   body=body)


def residence_page(sailings, page_fn) -> str:
    groups = collections.defaultdict(list)
    for s in sailings:
        groups[visa_short(s)].append(s)
    order = sorted(groups, key=lambda k: -len(groups[k]))
    blocks = []
    for k in order:
        ss = groups[k]
        text = collections.Counter(visa_rule(s) for s in ss).most_common(1)[0][0]
        ex = sorted(ss, key=lambda s: next_dep(s) or "9999")[:3]
        blocks.append(f'<h3 style="font-size:1.15rem;margin-top:22px">{esc(k)} · {len(ss)} itineraries</h3><p>{esc(text)}</p>'
                      + "<ul class=\"ticks\">" + "".join(f'<li><a href="{esc(s["url"])}">{esc(s["title"])}</a>, {esc(s["line"])}, {esc(fmt_date(next_dep(s)))}</li>' for s in ex) + "</ul>")
    body = f'''<section class="page-hero" style="min-height:auto;padding-bottom:40px">
  <div class="wrap"><span class="kicker">Visa guide</span><h1>Which cruises can I take on a UAE or GCC residence visa?</h1>
  <p>Your residence visa lets you live in the Gulf and come home to it. Which cruises you can take depends on your passport and the ports a ship calls at.</p></div>
</section>
<section class="section light" style="padding-top:40px"><div class="wrap sailing">
  <div>
    <h2 class="h-sub">The short answer</h2>
    <p>A UAE, Saudi, Qatari, Omani, Kuwaiti or Bahraini residence permit is not itself a visa for the countries a cruise visits. A few countries ease their rules for Gulf residents, and we check that for you. For a cruise, two things decide what you need. The first is your passport. The second is the ports: one Schengen port puts the whole voyage under Schengen rules, and one US port under US rules.</p>
    <p>Below, the {len(sailings)} itineraries in our inventory today are grouped by the visa rule that applies to them, with that group's wording as it appears on each sailing page and a few examples.</p>
    {"".join(blocks)}
    <h2 class="h-sub">What we do</h2>
    <p>Tell us your passport and where you live, and we check the visa position for the sailing before you pay anything.</p>
  </div>
  <aside class="farebox">
    <span class="kicker">Ask us about your passport</span>
    {form("Not sure yet", "Residence visa question")}
  </aside>
</div></section>
'''
    return page_fn(slug="guides/cruises-on-a-uae-gcc-residence-visa.html", base="../",
                   title="Which cruises can I take on a UAE or GCC residence visa? · Cruise24",
                   desc="A Gulf residence permit is not a visa for anywhere else. Our live inventory grouped by the visa rule that applies, with examples.",
                   body=body)


def hub_page(entries, page_fn) -> str:
    items = "".join(f'<li><a href="guides/{esc(slug)}.html">{esc(title)}</a> <span class="fine">· {n} itineraries</span></li>' for slug, title, n in entries)
    body = f'''<section class="page-hero" style="min-height:auto;padding-bottom:40px">
  <div class="wrap"><span class="kicker">Guides</span><h1>Route and visa guides</h1>
  <p>What a route is, who sails it, every departure in our inventory and the visa rule that applies. Rebuilt every night from the same inventory as the sailing pages.</p></div>
</section>
<section class="section light" style="padding-top:40px"><div class="wrap"><ul class="ticks">{items}</ul></div></section>
'''
    return page_fn(slug="guides.html", title="Route and visa guides · Cruise24",
                   desc="Route guides for the Rhine, Danube, Adriatic, Aegean, Cape Verde and Cape Horn, and visa guides for Gulf residents.", body=body)


def build(sailings, page_fn) -> tuple[dict[str, str], dict[str, list[tuple[str, str]]], dict]:
    """Returns (files, links per sailing id, stats). files maps path -> html."""
    out, links, stats, hub = {}, collections.defaultdict(list), {}, []
    for g in GUIDES:
        ss = [s for s in sailings if g["match"](s)]
        if not ss:
            continue   # a route the inventory no longer sells gets no page, rather than an empty one
        out[f"guides/{g['slug']}.html"] = guide_page(g, ss, GUIDES, page_fn)
        for s in ss:
            links[s["id"]].append((f"guides/{g['slug']}.html", g["short"]))
        stats[g["slug"]] = {"itineraries": len(ss), "departures": sum(len(s["departures"]) for s in ss)}
        hub.append((g["slug"], g["title"], len(ss)))
    out["guides/schengen-visa-mediterranean-cruise.html"] = schengen_page(sailings, page_fn)
    out["guides/cruises-on-a-uae-gcc-residence-visa.html"] = residence_page(sailings, page_fn)
    for v in VISA_GUIDES:
        hub.append((v["slug"], v["title"], len(sailings) if "residence" in v["slug"] else
                    len([s for s in sailings if MED.search(s["region"])])))
    out["guides.html"] = hub_page(hub, page_fn)
    for k, v in out.items():
        stats.setdefault(k.rsplit("/", 1)[-1].replace(".html", ""), {})["words"] = words(v.split("<body", 1)[-1])
    return out, links, stats
