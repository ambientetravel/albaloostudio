# cruise24.me — Cruise24, handoff

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari
Written 27 Sep 2026 by session `Cruise24.me website tools`, taking over the
claude.ai chat "building a professional cruise website".

## What this is

**Cruise24** is the brand, at **cruise24.me**: it brings the world of cruising to
the Middle East market. Ocean, river and all-suite luxury journeys worldwide,
sold to travellers in the region. "Excellent cruise deals of the Middle East"
in the logo means the market, not the cruising area (Alireza, 27 Sep).
**AmbiMare** stays only as the wordmark beside the logo in the header, and as
an `alternateName` in the home page's JSON-LD. Ambiente Tours GmbH remains the
legal entity on the imprint, privacy and booking conditions pages. cruise24.ir
is still the Farsi B2C twin. The chat produced two artifacts; both are in this
folder.

## Design, restyled around the logo (27 Sep, later)

The logo is monochrome line art: near-black navy ink (#0c1824) on white with
a pale blue wash (#e2ecf5), heavy geometric numerals, a letterspaced caps
tagline and dotted rules. `assets/site.css` now follows it: ink and wash as
the two backgrounds, one steel-blue accent (#1e4d7a on light, #9fbad6 on
dark) instead of the brass-and-teal pair, Manrope 700 for every heading
instead of the Cormorant serif, kickers as letterspaced caps with a dotted
lead line, 10px corners instead of pills, dotted footer rule. The Cormorant
files stay in `assets/fonts/` but nothing references them; delete when sure.

**The three logo questions, resolved 27 Sep:**
1. Brand is **Cruise24** on every page. AmbiMare stays as the header wordmark.
2. "Of the Middle East" is the market. The home page's title, description,
   kicker, lede, manifesto, footer blurb and JSON-LD `areaServed` now say so.
3. The misspelled tagline ("EXCCELENT" with a broken C) is fixed in
   `assets/logo-master.png`: that one line retyped in Lexend Bold, fitted to the
   original line's measured ink box (210,834)–(874,868), every other pixel
   verified identical. The file as supplied is kept as `logo-as-supplied.png`;
   every cut-out, favicon and the OG card are regenerated from the master.
   If the designer has the source file, their own fix should replace this one.

**Open, raised by the repositioning:** the contact page offers English,
German, Turkish or Italian. A Middle East market probably expects Arabic
and Farsi. Not added, because it is a staffing claim, not a copy change.

## Verified (headless Chromium, 1440×900 and 390×844, served from this folder)

All ten pages, both widths: 0 JS errors, GSAP and both font families
resolve locally, `aria-current` lands on the right nav item, every internal
link returns 200, no horizontal overflow. Row counts: ships 9, lines 8,
itineraries 15 (8 days + 7 routes), journal 6. Home page detail:

| Check | Desktop | Mobile |
|---|---|---|
| Page errors (JS) | 0 | 0 |
| GSAP + ScrollTrigger loaded from `assets/vendor/` | yes | yes |
| Cormorant Garamond and Manrope resolved locally | 11 faces loaded | 11 faces loaded |
| Sections present | 11 of 11 | 11 of 11 |
| Horizontal overflow | none (1440 = 1440) | none (390 = 390) |
| Local requests | 9 × 200, 1 × 404 (`media/index.json`, expected before download) | same |
| Failed remote requests | 35, all `explorajourneys.com` / `dm.explorajourneys.com` | 35, same |
| JSON-LD parses | `TravelAgency` | `TravelAgency` |

Rule checks on every HTML file: «Arabian Gulf» 0 occurrences; the Dubai route
is named "Dubai and the Persian Gulf" and marked easy-visa, not no-visa; the
AROYA Red Sea route says a Saudi visa is needed and that only the line's Egypt
and Türkiye loops are visa-free ("Arabian
Peninsula" appears as Explora's own destination name, which is a different
thing). Visa statements: v1 says Greek ports are Schengen and Türkiye is
visa-free/e-visa — both correct. No rate, departure date or inclusion was
invented by this session; the inclusions list is Explora's own.

## NOT done, and why

**1. Media is not downloaded.** This container's network policy denies
`explorajourneys.com` and `dm.explorajourneys.com` (403 on CONNECT). The ten
pages share 47 distinct media URLs (the inner pages reuse the home page's).
Run on any machine with normal internet:

    cd cruise24-me
    python3 download_media.py --no-videos     # images first, ~1 min
    python3 download_media.py                 # then the ~20 mp4s
    python3 download_media.py --check         # must print OK

Videos are gitignored (`cruise24-me/media/*` except `index.json` and
`.gitkeep`); commit `index.json`, upload `media/` to the host with the site.
Expect the videos to be large — Explora serves desktop hero clips at tens of
MB each. If total is uncomfortable, `ffmpeg -i in.mp4 -vf scale=1920:-2 -crf 28
-an out.mp4` on the hero and panel clips is the usual fix; the resolver does
not care what is inside the file.

**2. Hosting: the site cannot go where cruise24.me currently is.**
`orchestrator/sites.yml` records cruise24.me on **GoDaddy Website Builder** —
no file access, no API, `adapter: unimplemented`. A static folder with a media
directory needs real hosting: the DirectAdmin account that carries
boutimar.ir / cruise24.ir is the obvious place (add the domain, point DNS).
That is a decision and a DNS change, not a build step. Until then there is
nothing to write a DirectAdmin prompt for.

**3. Explora Journeys media rights.** The footer says "Explora Journeys
imagery used with permission of the line". That sentence came from the chat,
not from a document. Trade partners normally get an asset library under the
line's agency terms; if that agreement exists, keep the line. If not, it
must go before launch — it is a factual claim under the company name.

**4. Two copy claims to confirm before launch**, both from the chat:
"Explora I in Port Hercule for the 2027 Grand Prix" (the image path
`f1-2027/` suggests Explora has such a programme, but a departure is a
departure), and "Ambiente has planned quiet European travel for twelve years".

**5. The request form posts nowhere**, on the home page and on `contact.html`. `onsubmit` swaps in a thank-you line.
Wire it to whatever the host provides (the boutimar.ir sites use a PHP
endpoint writing `leads.json.php`; that pattern is in the repo). Do not launch
a form that silently drops enquiries.

**6. Legal pages need facts only the company has.** `imprint.html` and
`privacy.html` are drafted with every unknown highlighted in brass: street
address, managing director, register court and HRB number, VAT ID, phone,
email, TÜRSAB licence, the hosting provider (undecided), log retention, and
whether Cruise24 acts as Reisevermittler or Reiseveranstalter on a booking.
That last one decides whether a Sicherungsschein must be issued; do not
guess it. The EU ODR platform was shut down in July 2025, so no ODR link;
the VSBG statement is there with the choice left open.

**6a. Other placeholders**: `[PHONE] · [EMAIL]` on the contact page, `[licence numbers]` in the footer, and the AmbiMedi / AmbiEvent
links are `href="#"`. Booking conditions, Privacy and Imprint now resolve.

**7. Three journal pieces are teasers only.** "Seven nights on the Danube",
"Explora I, deck by deck" and "What a service charge actually is" exist as
three-line summaries in v1 and nowhere else; `journal.html` lists them under
"In the notebook · publishing next" without links rather than pretending
they are articles. The Kuşadası guide is the only full piece.

## Session routing

`.claude/session-routing.json` now routes **cruise24.me** to this session
(`Cruise24.me website tools`). cruise24.ir and book.cruise24.ir stay with
`Cruise24.ir storefront build`. Alireza brought the Cruise24 work here
explicitly on 27 Sep 2026.
