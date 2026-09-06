# دریانامه — the Farsi cruise hub: brainstorm v1 (2026-09-06)

Owning session: "Daryanameh Farsi cruise domain brainstorm" (branch claude/daryanameh-farsi-cruise-0sdppb).
Status: ideas and decisions, nothing built yet. Existing asset: 4 Farsi articles under boutimar.ir/daryanameh/ plus the
orchestrator pipeline (agent2_writer_listener.py) that already writes into daryanameh/<slug>.html.

## 1. Role in the portfolio

| Property        | Audience                         | Tone                | Job                                   |
|-----------------|----------------------------------|---------------------|---------------------------------------|
| boutimar.ir     | Iranian agencies, trade          | quiet, B2B          | wholesale, agent tools, embed widget  |
| cruise24.ir     | Iran-based consumers             | price, offers       | sell sailings in rial                 |
| cruisebaz.com   | Iranian diaspora                 | practical           | sell to non-resident / dual-passport  |
| THE HUB         | everyone who reads Farsi         | editorial, luxury   | audience + trust + feed + ad revenue  |

The hub never sells. It owns the audience and the vocabulary, and hands warm readers to the three sales sites through
clearly-labelled house ads. Neutrality is the product: if a reader ever feels sold to, the hub loses its only advantage.

Rules carried over from CLAUDE.md: «خلیج فارس» always; visa accuracy (Persian Gulf and Dubai are *easy visa*, only
AROYA Türkiye+Egypt and Seychelles are truly visa-free, any Greek/Italian/Spanish/French port = Schengen); never invent
a rate, date, inclusion or photo credit.

## 2. Name

### Verdict: keep دریانامه as the editorial brand. The "-nameh" family is the strongest asset you have.

Persian already has روزنامه (newspaper), سفرنامه (travelogue), شاهنامه, واژه‌نامه. دریانامه ("sea chronicle") slots into that
family instantly and reads as *publication*, which is exactly the positioning. It also gives you a ready-made section
architecture that no transliterated or coined name can:

- بندرنامه  — port guides
- کشتی‌نامه — ship profiles
- سفرنامه   — itineraries and reader travelogues
- خبرنامه   — the weekly newsletter (this word already means newsletter)
- واژه‌نامه — the cruise glossary
- ویزانامه  — visa guide for Iranian passport holders

Weakness: 10 Latin letters and the spelling drifts (daryanameh / daryaname / darianameh). Mitigate by registering the
variants and by always pairing the wordmark with the Persian script.

### Alternatives worth registering anyway (defensive or as the print title)

| Candidate       | Meaning                             | Why                                                        |
|-----------------|-------------------------------------|------------------------------------------------------------|
| daryagard.com   | دریاگرد — "sea-wanderer"            | coined on جهانگرد (tourist). Ownable, 9 letters, no drift  |
| karaneh.com     | کرانه — shoreline                   | elegant, easy for non-Persians, works as a magazine title  |
| haftdarya.com   | هفت دریا — Seven Seas               | luxury signal, international meaning. Risk: Regent Seven Seas is a cruise line, avoid as primary |
| nakhoda.com     | ناخدا — captain                     | authority voice ("ask the captain" column). Likely taken   |
| daryanavard.com | دریانورد — mariner                  | strong meaning, long                                       |

Availability could not be checked from this container (outbound whois/RDAP blocked by network policy). Check
daryanameh.com / .net / .ir plus daryagard.com and karaneh.com at the registrar before any design work.

## 3. Benchmarks and what to take from each

| Site                         | Lang | Model                                   | Steal this                                              |
|------------------------------|------|-----------------------------------------|---------------------------------------------------------|
| Cruise Critic (Tripadvisor)  | EN   | reviews + forums + news, ad-funded      | member reviews per ship; "roll call" per sailing        |
| Cruise Hive / Cruise Fever   | EN   | daily news, affiliate                   | daily cadence, one story per day works                  |
| Porthole Cruise & Travel     | EN   | quarterly glossy + web                  | the print-plus-web model you want                       |
| CruiseMapper                 | EN   | ship tracker + port pages, huge SEO     | data pages (ships, ports, schedules) drive most traffic |
| cruisetimetables.com         | EN   | "which ships are in port X on day Y"    | port schedule pages for Dubai/Doha/Abu Dhabi/Muscat     |
| Cruisetricks.de              | DE   | one-person independent editorial, newsletter, press-code | independence as brand; blog-of-the-year 5x  |
| Crucero Magazin              | DE   | quarterly in bookstores + web           | your exact cadence: 4 print issues + daily web          |
| Cruceroadicto.com            | ES   | community-first editorial               | reader Q&A as content engine                            |
| ALEPH Magazine (Vancouver)   | FA   | seasonal luxury Persian lifestyle glossy | the design bar; the advertiser mix (jewellers, realtors, clinics) |

Gap you fill: there is no Persian-language equivalent of any of these. Arabic has none either.

## 4. What lives inside the domain (pillars)

Evergreen data pages first, stories second. Data pages are what search engines send people to for years.

1. کشتی‌نامه — ship database. One page per ship: line, class, size, cabins, dining, kids, spa, dress code, plus the
   fields nobody else has: halal options, alcohol-free bars, prayer space, Farsi-speaking crew sightings,
   Persian Gulf deployments, and **which lines accept Iranian passport holders** (facts only, sourced, dated).
2. بندرنامه — port guides. Walkable or not, visa status for Iranian passports, currency, tipping, halal food, and a
   "نزدیک بندر" block: Persian restaurant / shop / doctor near the port. That block IS the ad inventory.
3. سفرنامه — itineraries by region with a visa layer for Iranian passports, plus reader travelogues.
4. کروز رودخانه‌ای — river cruises (Nile first: Egypt is visa-friendly; then Danube, Rhine, Douro, Mekong).
5. خطوط کروز — cruise line profiles, fleet lists, loyalty programmes explained in Farsi.
6. ویزانامه — the definitive Farsi visa guide for cruising; updated, dated, sourced.
7. واژه‌نامه — cruise glossary. You get to set the standard Farsi vocabulary. Every other site will link to it.
8. مدرسه کروز — first-cruise academy (the four existing articles seed this).
9. تقویم — Persian calendar sailings: Nowruz cruises, Yalda, summer holidays. Nowruz 1406 roundup is the first big
   traffic piece of the year.
10. جدول بنادر — "ships in Dubai / Doha / Abu Dhabi / Muscat this week" schedule pages.
11. ناخدا پاسخ می‌دهد — ask-the-captain column; later a column by Iranian crew members.
12. Reviews — Iranian passengers rate ships; short structured form, not free text.
13. Directory — «ایران‌پسند» badge for Iranian-friendly services near ports and in home-port cities.
14. Video/podcast — دریانامه TV on YouTube and Telegram; short ship walk-throughs dubbed in Farsi.
15. Events — diaspora "cruise nights" in Toronto, Vancouver, LA, Dubai, Hamburg, Istanbul, run with the sales sites.

## 5. Channels and cadence

| Channel     | Cadence          | Content                                                                 | Tool already connected |
|-------------|------------------|-------------------------------------------------------------------------|------------------------|
| Telegram    | daily or 2-daily | port of the day, ship of the day, one visa fact, one poll, one deal pointer to a sales site | Zernio / Zapier |
| Newsletter  | weekly, Thursday | «پنجشنبه‌های دریا»: 1 long read, 3 short, ships-in-port, one sponsor slot | nitrosend |
| Web         | 3–5 pieces/week  | orchestrator pipeline output plus data-page updates                      | existing orchestrator |
| Magazine    | quarterly        | best of the quarter, re-edited; PDF + print run for diaspora cities      | Canva (brand template) |
| YouTube     | fortnightly      | ship walk-throughs, port walks                                          | Higgsfield for cut-downs |

Print distribution loop: advertisers (Persian restaurants, shops, clinics) receive copies to display. They pay for the
page and hand out the magazine that carries it. Same loop ALEPH runs.

## 6. Advertising: neutral, and how the free-then-paid period actually works

Structure
- Separate brand and legal home from the sales companies. Hold the hub under the non-Iranian entity (Ambiente) so
  international advertisers can pay by card; Iran-based advertisers pay in rial through the cruise24 rails.
- A published editorial policy page: house ads are labelled «آگهی», sponsored guides are labelled
  «با حمایت», reviews are never sold.

Inventory
- Site: leaderboard, in-article, the "نزدیک بندر" block on port pages (geo-targeted by port), directory listing.
- Newsletter: one sponsor slot per issue, max one.
- Telegram: one pinned sponsor post per week.
- Magazine: full page, half page, inside covers, back cover.
- Advertorial: labelled, written by us to house style.

Founding Partners programme (replaces "free for 90 days")
- First 30 advertisers, invitation only, 90 days free.
- In exchange: a signed rate-card agreement with a start date at day 91, a testimonial, print distribution at their
  premises, and two referrals.
- Day 60: each partner gets a one-page performance report (impressions, clicks, QR scans, promo-code uses).
  That report is what converts them; without measurement the free period just ends.
- Founding badge stays on their listing for life. That is the reason to join early.

Measurement
- One UTM and one short promo code per advertiser; QR codes in print; a monthly PDF report auto-generated.

Advertiser mix to target (in this order)
1. Persian restaurants and shops in home-port cities (Dubai, Istanbul, Barcelona, Genoa, Athens, Miami, Toronto,
   Vancouver, LA, Hamburg).
2. Clinics and doctors serving the diaspora (cosmetic, dental).
3. Real estate (Dubai, Toronto), immigration lawyers, private banking.
4. Jewellers, watches, carpets, luxury retail.
5. Travel insurance, eSIM, luggage.
6. Your own three sites, labelled, never more than one third of the visible inventory on any page.

## 7. Technology, reusing what exists

- Same static-HTML + DirectAdmin stack as boutimar.ir / cruise24.ir, so the same deploy bundle process.
- The orchestrator already targets daryanameh/<slug>.html. Add the hub as a new site profile with its own base_url;
  the hub becomes canonical, the three sales sites show excerpts with canonical links back (no duplicate content).
- Every page emits RSS/JSON feed. Zernio/Zapier consume the feed for Telegram; nitrosend composes the weekly digest
  from the same feed; the sales sites embed a "تازه‌های دریانامه" widget from it.
- Data pages (ships, ports) as JSON that both the hub and boutimar's embed widget can read.
- Search: Pagefind (static). Ads: a JSON rotation first; Revive Adserver self-hosted only when there are 20+ paying
  advertisers.
- Magazine: Canva brand template, one master, 4 issues a year.

## 8. First 90 days

Weeks 1–2   Register domains. Editorial policy page. Brand: wordmark in Persian + Latin, palette, Canva template.
Weeks 2–4   Move the 4 existing articles, publish واژه‌نامه and ویزانامه, 10 port pages (Persian Gulf first), 10 ships.
Week 4      Telegram channel live, daily. Newsletter #1.
Weeks 5–8   40 more data pages. Founding Partners outreach: 30 invitations, target 15 signed.
Weeks 9–12  Nowruz 1406 cruise roundup. Magazine issue 1 in production. Day-60 reports to partners.
Day 91      First invoices.

## 9. Assumptions I made

- You keep دریانامه as the name; alternatives are defensive registrations or the print title.
- The hub is hosted under Ambiente, not Boutimar, so it can take card payments from outside Iran.
- Farsi only; a Latin wordmark for the logo but no English content.
- The three existing sites keep their roles; nothing is merged.
