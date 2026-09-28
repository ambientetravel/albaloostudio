# Legal pages: what is still open

`conditions.html`, `imprint.html` and `privacy.html` are English only. Nothing on
them addresses the site owner any more. Facts only the company can supply show as
short highlighted labels (`<span class="todo">`). Before go-live, `python3 build_bundle.py` must pass: it refuses to build while any `class="todo"` is left.

Not deployed (matches `HANDOFF*.md`).

## Facts to fill in

| Page | Field |
|---|---|
| imprint | street and number, postcode (Rennerod) |
| imprint | managing director |
| imprint | telephone, email |
| imprint | register court and HRB number |
| imprint | VAT ID (DE…) |
| imprint | person responsible for editorial content (§ 18 (2) MStV) |
| privacy | hosting provider: GoDaddy (decided 28 Sep). The contracting GoDaddy entity, its address and the basis for the US transfer come from GoDaddy's Data Processing Addendum for the account; see `HANDOFF-godaddy.md` |
| privacy | server-log retention, in days (depends on the host) |
| privacy | deletion period, in months, for enquiries that do not lead to a booking |

The booking conditions have no gaps left. Deposit, balance date, payment methods,
change fees and the organiser's cancellation scale are now stated as "in the offer
and the confirmation", because they vary by line and by booking.

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
