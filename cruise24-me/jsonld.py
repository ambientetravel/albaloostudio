"""JSON-LD for every cruise24.me page (Albaloo Agent 5 flagged 9 pages without it).

Used by build_journeys.page() for generated pages and by inject_jsonld.py for the
hand-written ones. Only facts already on the page: title, description, address.
No dates, ratings or prices are invented.
"""
from __future__ import annotations

import json

SITE = "https://cruise24.me/"
ORG = {"@id": SITE + "#org"}
IMAGE = SITE + "assets/og-image.jpg"

_KIND = {
    "about.html": "AboutPage", "contact.html": "ContactPage",
    "guides.html": "CollectionPage", "destinations.html": "CollectionPage",
    "journeys.html": "CollectionPage", "ports.html": "CollectionPage",
    "lines.html": "CollectionPage", "ships.html": "CollectionPage",
    "itineraries.html": "CollectionPage", "journal.html": "CollectionPage",
}


def block(slug: str, title: str, desc: str, url: str) -> str:
    name = title.split(" · ")[0]
    crumbs = [("Cruise24", SITE)]
    if slug.startswith("guides/"):
        crumbs += [("Guides", SITE + "guides.html"), (name, url)]
        node = {"@type": "Article", "headline": name[:110], "description": desc, "image": IMAGE,
                "author": ORG, "publisher": ORG, "inLanguage": "en", "mainEntityOfPage": url}
    elif slug.startswith("journeys/"):
        crumbs += [("Journeys", SITE + "journeys.html"), (name, url)]
        node = {"@type": "WebPage", "name": name, "description": desc, "url": url}
    else:
        crumbs.append((name, url))
        node = {"@type": _KIND.get(slug, "WebPage"), "name": name, "description": desc, "url": url,
                "inLanguage": "en", "isPartOf": {"@type": "WebSite", "name": "Cruise24", "url": SITE}}
    node["about" if node["@type"] == "AboutPage" else "publisher"] = ORG
    data = {"@context": "https://schema.org", "@graph": [
        node,
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(crumbs)]},
    ]}
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "</script>\n"
