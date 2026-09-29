# Legal pages: what is still open

`conditions.html`, `imprint.html` and `privacy.html` are English only. Nothing on
them addresses the site owner any more. Facts only the company can supply show as
short highlighted labels (`<span class="todo">`). Before go-live, `python3 build_bundle.py` must pass: it refuses to build while any `class="todo"` is left.

Not deployed (matches `HANDOFF*.md`).

## Facts filled in (29 Sep, from Alireza)

- Imprint: Ambiente Tours GmbH, Hauptstr. 81, 56477 Rennerod; managing directors Cyrus Martin Nurischad
  and Alireza Mozaffari; +49 (0) 2664 9931 821, res@cruise24.me (also on the contact page).
- Privacy: server logs 14 days, unbooked enquiries 6 months. Hosting: GoDaddy, European data centre.

**Rennerod appears only in the imprint.** Alireza does not want the town in the marketing. The imprint must
show the full address where the company can be served (§ 5 DDG), so it stays there; everywhere else says
"Germany", and the contact and about pages say "Westerwald, between Frankfurt and Cologne". If a city
address is wanted, it has to be a real business address that accepts legal mail (a registered-office
service in Frankfurt, say); that costs money and is Alireza's call.

**Judgement calls to confirm:**
1. Register court written as **Amtsgericht Montabaur** (Rennerod is in the Westerwaldkreis, whose register
   is kept in Montabaur). Only "HRB 24620" was given.
2. Company name kept as **Ambiente Tours GmbH**, as everywhere else. The message said "Ambientetours GmbH";
   the imprint must match the register exactly.
3. **Responsible for editorial content: Alireza Mozaffari.** "admin" was given, but § 18 (2) MStV needs a
   named person with an address.
4. **VAT ID left off** at Alireza's request. § 5 DDG requires it where the company has one; leaving it off
   is a warning-letter (Abmahnung) risk.

## Still open

| Page | Field |
|---|---|
| privacy | the contracting GoDaddy company and its address, from GoDaddy's data processing addendum (prompt in HANDOFF-godaddy.md) |

## Decisions taken in the text: check these

1. **Both roles.** The text says Cruise24 acts as travel agent for a cruise on its
   own, and Ambiente Tours GmbH is the organiser when a cruise is packaged with
   flights, hotels or transfers. If the company never packages, delete the
   organiser paragraphs in conditions §§ 1, 4, 6, 9 and 10, and in the imprint's
   "Travel law" section.
2. **Insolvency protection.** Conditions § 10 says that, as organiser, payments are
   protected and the security certificate names the insurer. German law requires
   this of an organiser (§ 651r BGB), so an insurer or fund contract must exist
   before any packaged booking is taken.
3. **Consumer dispute resolution.** The imprint says "We do not take part". This
   is permitted for travel businesses. If you prefer to take part, name the
   arbitration board instead.
4. **Data protection officer.** The privacy page says none is appointed because
   the company is below the § 38 BDSG threshold (fewer than 20 people regularly
   processing personal data). If that is not true, name the officer.
5. **Photo rights.** The imprint says Explora imagery is "used with its
   permission", the same wording as the footer. Other ship photos are described as
   coming from the cruise lines or from Wikimedia Commons. Both still need the
   rights confirmation listed in HANDOFF.md.
6. **Jurisdiction.** The text uses "the courts at the registered seat of Ambiente
   Tours GmbH" instead of naming a town, so it stays right if the seat is not
   Rennerod.

Have a lawyer who knows German travel law read all three pages before go-live.
