# دریانامه — business case v1 (2026-09-06)

Companion to BRAINSTORM.md. All numbers are estimates from comparable niche media, not measurements.
Assumed entity: Ambiente Tours (Germany). Currency EUR.

## 1. Verdict

Worth 12 months of committed time, as the group's audience and acquisition engine. Not as a standalone media
company: Persian-language cruise editorial is too small a niche to pay a salary from ads in year 1.
It pays back three ways, in this order of certainty:
1. Bookings referred to cruise24.ir / cruisebaz.com / boutimar.ir (commission on fares).
2. Advertising from diaspora businesses, magazine pages, sponsor slots.
3. Magazine subscriptions / paid membership (small, treat as print cost recovery).

Kill-or-continue check at month 6, three numbers: newsletter >= 1,500 subscribers, >= 6 paying advertisers,
>= 5 referred bookings per month. Two of three missed -> fold back into boutimar.ir/daryanameh, keep Telegram only.

## 2. Reach and revenue, base case (conservative / upside in brackets)

| Metric                          | Month 3            | Month 6              | Month 12               |
|---------------------------------|--------------------|----------------------|------------------------|
| Telegram members                | 1,500 (800/2,000)  | 4,500 (3k/6k)        | 12,000 (8k/15k)        |
| Newsletter subscribers          | 500 (300/800)      | 1,800 (1k/2.5k)      | 4,500 (3k/6k)          |
| Podcast listens / episode       | 300 (200/500)      | 700                  | 1,500 (1k/2.5k)        |
| Founding partners (free)        | 12 (8/15)          | -                    | -                      |
| Paying advertisers              | 0                  | 9 (6/12)             | 28 (20/35)             |
| Avg advertiser / month          | -                  | 150                  | 180                    |
| Web+newsletter+TG ad revenue/mo | 0                  | 1,350 (900/1,800)    | 5,000 (3.5k/6k)        |
| Magazine ad pages / issue       | -                  | 12 (8/15) @ 600      | 20 (15/25) @ 700       |
| Referred bookings / month       | 2 (1/3)            | 8 (5/10)             | 18 (10/25)             |
| Commission @ ~300 avg / booking | 600                | 2,400                | 5,400 (3k/7.5k)        |
| Paid members (magazine subs)    | 0                  | 60                   | 200 (100/300)          |

Year-1 totals, base case
- Direct ad revenue (web, newsletter, Telegram, 3 magazine issues): ~30,000 (conservative 12,000 / upside 45,000)
- Referred booking commission to the group: ~25,000 (15,000 / 40,000)
- Paid membership: ~5,000

Year-1 costs
| Item                                        | EUR / year |
|---------------------------------------------|-----------:|
| Print, 4 issues x 1,000 glossy + shipping   | 8,000–12,000 |
| Tools: ElevenLabs, nitrosend, Zernio, hosting, domains | ~2,000 |
| Part-time Farsi editor from month 4         | 5,000–10,000 |
| Legal: trademark, Impressum/AGB, policy     | 1,000–2,000 |
| App store accounts                          | ~150 |
| Total                                       | 16,000–26,000 |

Base case year 1: direct revenue roughly covers cost; group-level positive once bookings count.
Year 2: advertiser base compounds, print pays for itself; 60–100k direct revenue is plausible.

## 3. Workload (Alireza's hours; Claude Code does the building)

| Phase                  | Hours / week | Where the hours go                                                      |
|------------------------|-------------:|-------------------------------------------------------------------------|
| Months 1–3, build      | 10–12        | 3 editorial review (Farsi quality, visa/rate accuracy), 4 advertiser outreach (~30 conversations to sign 15), 2 brand + magazine decisions, 2 reviewing Code output |
| Months 4–12, run       | 6–8          | 4 advertisers and partners, 2 review, 1 Telegram/newsletter QA          |
| Magazine crunch, 4x    | +20 each     | issue edit, layout approval, print proof                                |
| Year 1 total           | ~450         |                                                                         |

From month 4 a part-time Farsi editor / community manager (Iran-based, 500–1,200 / month) takes the daily
Telegram and first-pass review; his hours drop to 3–4 / week, all on advertisers.

## 4. Legal role

It is a publisher / media platform. It never sells travel, so it sits outside package-travel law (no
Pauschalreise duties, no insolvency insurance, no IATA). What it does need:
- Impressum with a named responsible editor (MStV §18), and an editorial policy page naming the three sales
  companies as commercial partners.
- Separation and labelling of advertising (Trennungsgebot): «آگهی» on house ads, «با حمایت» on sponsored guides,
  reviews never sold.
- GDPR double opt-in for the newsletter and app push consent.
- Image licensing for every photo; no invented credits (existing hard rule).
- EU AI Act Art. 50 (in force 2 Aug 2026): AI-generated podcast audio needs an audible disclosure at the start of
  each episode and machine-readable marking of the file. Make it a brand feature: name the two AI hosts, say so.
- Sanctions and payments: international advertisers pay the German entity by card / SEPA. Iran-based advertisers
  pay in rial to the Iranian entity under an intercompany service agreement; screen advertisers against
  sanctions lists; never take payment from a listed person or entity.
- Trademark: word mark «دریانامه» / Daryanameh at EUIPO and in Iran once the name is final.
- Structure: a trade name / division of Ambiente Tours now; a separate GmbH/UG only when direct revenue passes
  ~50k / year or an outside partner comes in.

## 5. What it is called

Public: «دریانامه» + descriptor «رسانهٔ فارسی‌زبان کروز و سفر دریایی».
Slogan (ALEPH pattern): «نخستین رسانهٔ فارسی‌زبان کروز» / "The first Persian-language cruise media platform".
Legal line in the Impressum: "Daryanameh Media, a division of Ambiente Tours [GmbH]".
Call it a media platform, never just a magazine: web + newsletter + Telegram + podcast + quarterly print + app.

## 6. Podcast (AI, two hosts, Farsi, bi-weekly)

- Both routes work in Persian: NotebookLM Audio Overviews (one click, weak fact control, foreign-sounding Farsi)
  and a scripted route: Claude writes the script from that fortnight's published articles (facts already reviewed),
  ElevenLabs v3 renders two fixed Persian voices, 15–20 minutes. Use the scripted route: visa or rate errors in
  audio cannot be quietly corrected.
- Name: «رادیو دریانامه» (or «گفت‌وگوی عرشه», Deck Talk). Two named AI hosts, disclosed in the intro.
- Cost ~30–60 / month. Distribution: Castbox first (dominant among Iranians), Spotify, Apple, YouTube, Telegram.
- Value is credibility and 6–8 short clips per episode for Telegram, not direct revenue.

## 7. App

Two steps, both under Ambiente's developer accounts.
1. Month 2–3, ~1 week of Code work: PWA of the hub. Installable on iPhone and Android, push notifications,
   and the one feature that justifies an app at all: offline port guides, ship info and excursion notes
   downloaded before sailing (internet at sea costs 20–40 / day). Plus "ships in port today" and a member card
   with partner discounts.
2. Month 6–9, 3–4 weeks: Capacitor wrapper for App Store and Google Play, plus Cafe Bazaar and Myket for
   Iran-based Android users (official stores are not available there). Fees ~150 / year.
Paid tier in-app for diaspora only (3–5 / month or 40–60 / year including the 4 printed issues shipped);
Iran-based users get the free tier or pay in rial via cruise24's gateway.

## 8. Membership estimate at month 12

Free reach (Telegram + newsletter + app): 15–25k combined, roughly 6–10k unique people.
Paid: 100–300 base, 500–800 upside only if the printed magazine is the perk. Model it as a magazine
subscription, not a content paywall; Iran-based readers will not pay for online content.
