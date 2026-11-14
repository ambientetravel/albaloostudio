# CTR experiments — title rewrites on pages that are shown but not clicked

Method: one change per page, log before/after, compare the same page and query over 28 days before vs 28 days
after (Search Console, web, final data). A click rise alone does not prove the title; also read position and
impressions. Baseline = `tools/ctr_gap.py` run 43616103540 (90 days to 2026-11-11). Yardstick CTR is approximate.

| # | Page | Baseline (90d) | Old title | New title | Applied | Re-check |
|---|---|---|---|---|---|---|
| 1 | boutimar.com/travel-to-iran-now/ | imp 3305, clk 58, CTR 1.75%, pos 8.2 (query "can i travel to iran now") | Is Iran Open for Tourism? Travelling to Iran Now \| Boutimar | Can You Travel to Iran Now? Official Advice and Reality \| Boutimar (66 chars) | 2026-11-14 16:38 UTC, boutimar c175417 | 2026-12-12 |
| 2 | cruisebaz.com/en/aroya/price | imp 2653, clk 37, CTR 1.39%, pos 7.8 ("aroya cruise price") | AROYA Cruise Prices 2026–2027 \| Real Lead Fares by Route \| CruiseBaz | AROYA Cruise Prices 2026–27: Fares per Person by Route \| CruiseBaz | pending (base44) | applied + 28 d |
| 3 | cruisebaz.com/en/aroya/departures | imp 900, clk 5, CTR 0.56%, pos 8.3 | AROYA Cruises — Departures 2026–2027 (Eastern Mediterranean from Istanbul) \| CruiseBaz (86 chars, truncates) | AROYA Cruise Departures 2026–27 from Istanbul \| CruiseBaz | pending (base44) | applied + 28 d |
| 4 | cruisebaz.com/en/cruise-line/aroya/aroya | imp 586, clk 4, CTR 0.68%, pos 8.2 ("aroya cruise") | Aroya Ship Detail \| تور کشتی کروز ۱۴۰۵ \| رزرو آنلاین کروز (Farsi template title on an English page; meta description is Farsi and cut mid-sentence) | AROYA Cruise Ship: Details, Routes and Fares \| CruiseBaz | pending (base44) | applied + 28 d |

Not attempted, by design: fair pages (query is the fair's own name; its official site outranks ours) and hotel pages
(queries are hotel brand names; the hotel and booking sites outrank ours).

## Confound on row 1
The page body was rewritten on 2026-11-08 (boutimar b914697: new description, H1, five-government advisory section, July
ground report, 6th FAQ). The title stayed the same until 2026-11-14. So the 90-day baseline (to 4 Nov) is entirely
pre-rewrite, and a 28-day "before" window (17 Oct-13 Nov) spans two page versions. Read row 1 three ways and report all:
(a) 28 d before 14 Nov vs 28 d after (title + rewrite together), (b) 8-13 Nov only as a short clean "rewrite, old title"
baseline vs after, (c) 90-day baseline vs after. Treat any result as the rewrite plus the title, not the title alone.
