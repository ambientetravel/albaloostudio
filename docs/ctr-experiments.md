# CTR experiments — title rewrites on pages that are shown but not clicked

Method: one change per page, log before/after, compare the same page and query over 28 days before vs 28 days
after (Search Console, web, final data). A click rise alone does not prove the title; also read position and
impressions. Baseline = `tools/ctr_gap.py` run 43616103540 (90 days to 2026-11-11). Yardstick CTR is approximate.

| # | Page | Baseline (90d) | Old title | New title | Applied | Re-check |
|---|---|---|---|---|---|---|
| 1 | boutimar.com/travel-to-iran-now/ | imp 3305, clk 58, CTR 1.75%, pos 8.2 (query "can i travel to iran now") | Is Iran Open for Tourism? Travelling to Iran Now \| Boutimar | Can You Travel to Iran Now? Government Advice and the Ground Picture \| Boutimar | pending (Boutimar.com session) | applied + 28 d |
| 2 | cruisebaz.com/en/aroya/price | imp 2653, clk 37, CTR 1.39%, pos 7.8 ("aroya cruise price") | AROYA Cruise Prices 2026–2027 \| Real Lead Fares by Route \| CruiseBaz | AROYA Cruise Prices 2026–27: Fares per Person by Route \| CruiseBaz | pending (base44) | applied + 28 d |
| 3 | cruisebaz.com/en/aroya/departures | imp 900, clk 5, CTR 0.56%, pos 8.3 | AROYA Cruises — Departures 2026–2027 (Eastern Mediterranean from Istanbul) \| CruiseBaz (86 chars, truncates) | AROYA Cruise Departures 2026–27 from Istanbul \| CruiseBaz | pending (base44) | applied + 28 d |
| 4 | cruisebaz.com/en/cruise-line/aroya/aroya | imp 586, clk 4, CTR 0.68%, pos 8.2 ("aroya cruise") | Aroya Ship Detail \| تور کشتی کروز ۱۴۰۵ \| رزرو آنلاین کروز (Farsi template title on an English page; meta description is Farsi and cut mid-sentence) | AROYA Cruise Ship: Details, Routes and Fares \| CruiseBaz | pending (base44) | applied + 28 d |

Not attempted, by design: fair pages (query is the fair's own name; its official site outranks ours) and hotel pages
(queries are hotel brand names; the hotel and booking sites outrank ours).
