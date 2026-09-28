# Cruise24 on LinkedIn

Page: https://www.linkedin.com/company/cruise24/ (public URL; the `?viewAsMember=true` link is the admin preview).
Linked from every footer on cruise24.me and in the site's structured data (`sameAs`).

LinkedIn could not be read from the build environment (the proxy blocks it), so the copy below
is written from the site itself: nothing in it is a fact the site does not already state.

## Files

| File | Use | Size |
|---|---|---|
| `cruise24-linkedin-cover.png` | Cover image | 2256 x 382 (1128 x 191 at 2x) |
| `cruise24-linkedin-logo.png` | Page logo | 400 x 400 |
| `_render.html` | Source of both images (brand fonts and colours); re-render with Playwright if the copy changes | |

Cover: the left 280 px are left empty because LinkedIn places the logo over the lower left of the cover.

## Copy

**Tagline** (116 / 120 characters)

Ocean, river and luxury small-ship cruises from the Middle East, with the real price and the visa position up front.

**Overview** (1398 / 2,000 characters)

Cruise24 brings the world of cruising to travellers from the Middle East: ocean cruises, river weeks and luxury small-ship journeys, planned and booked by one person who stays on your file from the first question to the last evening on board.

We work with the lines we know best. Our focus is Explora Journeys, Silversea, Variety Cruises and Scenic. In the Mediterranean we also book Seabourn, Regent Seven Seas, Ponant, SeaDream, Sea Cloud and Star Clippers, and on request Celestyal, AROYA, MSC Cruises, A-ROSA, nicko cruises and Amadeus. From the Greek islands and the Turkish coast to the Red Sea, the Persian Gulf, the Danube and the Norwegian fjords.

Every offer states the real price, with what the fare includes and what it does not, and the visa position for every port on the route and the passport you hold. Any Greek, Italian, Spanish or French port puts a sailing under Schengen rules, and we say so before anyone pays.

For companies, MICE at sea: incentives, leadership off-sites, product launches and client events, from a block of suites on a scheduled sailing to a full-ship charter. With Explore Orient, our group's MICE and DMC company, land and sea are one brief to one team.

Cruise24 is a brand of Ambiente Group: Ambiente Tours GmbH in Rennerod, Germany, for the DACH region, and Ambiente Turizm Seyahat in Kuşadası, Türkiye, for the Middle East, North Africa and Türkiye.

**Website:** https://cruise24.me · **Industry:** Travel Arrangements · **Button:** Visit website → https://cruise24.me

**Specialties** (19 / 20)

- Luxury cruises
- Small-ship cruises
- Yacht cruises
- River cruises
- Ocean cruises
- Expedition cruises
- Mediterranean cruises
- Greek islands cruises
- Red Sea cruises
- Persian Gulf cruises
- MICE at sea
- Incentive travel
- Ship charters
- Group cruises
- Corporate events at sea
- Celebrations at sea
- Cruise visa advice
- Explora Journeys
- Silversea

**Locations:** Rennerod, Germany (primary) · Kuşadası, Türkiye. City and country only.

**Not set, on purpose:** company size, company type, founded year, phone. They are not in any source; fill them in yourself if you want them shown.

## Prompt for Claude in Chrome

Open the LinkedIn page in Chrome while logged in as a page admin, open Claude in Chrome, and paste everything in the box.

```text
You are editing the LinkedIn company page of Cruise24. I am logged in as a page admin.

Page: https://www.linkedin.com/company/cruise24/
Admin view: https://www.linkedin.com/company/cruise24/admin/

Do this in order:

1. BACKUP FIRST. Open the admin view, click "Edit page", and go through every section (Page info, Details, Locations, Buttons). Before you change anything, write me the CURRENT value of every field in this chat: name, tagline, overview/description, website, industry, company size, company type, founded, phone, specialties, locations, custom button. This is my backup. Do not skip it.

2. PAGE INFO
   - Name: leave as it is (Cruise24).
   - Tagline (max 120 characters), exactly:
Ocean, river and luxury small-ship cruises from the Middle East, with the real price and the visa position up front.

3. DETAILS
   - Overview/description, exactly as below, keeping the blank lines between paragraphs:

Cruise24 brings the world of cruising to travellers from the Middle East: ocean cruises, river weeks and luxury small-ship journeys, planned and booked by one person who stays on your file from the first question to the last evening on board.

We work with the lines we know best. Our focus is Explora Journeys, Silversea, Variety Cruises and Scenic. In the Mediterranean we also book Seabourn, Regent Seven Seas, Ponant, SeaDream, Sea Cloud and Star Clippers, and on request Celestyal, AROYA, MSC Cruises, A-ROSA, nicko cruises and Amadeus. From the Greek islands and the Turkish coast to the Red Sea, the Persian Gulf, the Danube and the Norwegian fjords.

Every offer states the real price, with what the fare includes and what it does not, and the visa position for every port on the route and the passport you hold. Any Greek, Italian, Spanish or French port puts a sailing under Schengen rules, and we say so before anyone pays.

For companies, MICE at sea: incentives, leadership off-sites, product launches and client events, from a block of suites on a scheduled sailing to a full-ship charter. With Explore Orient, our group's MICE and DMC company, land and sea are one brief to one team.

Cruise24 is a brand of Ambiente Group: Ambiente Tours GmbH in Rennerod, Germany, for the DACH region, and Ambiente Turizm Seyahat in Kuşadası, Türkiye, for the Middle East, North Africa and Türkiye.

   - Website: https://cruise24.me
   - Industry: Travel Arrangements
   - Specialties: remove the existing ones and add these, one at a time:
- Luxury cruises
- Small-ship cruises
- Yacht cruises
- River cruises
- Ocean cruises
- Expedition cruises
- Mediterranean cruises
- Greek islands cruises
- Red Sea cruises
- Persian Gulf cruises
- MICE at sea
- Incentive travel
- Ship charters
- Group cruises
- Corporate events at sea
- Celebrations at sea
- Cruise visa advice
- Explora Journeys
- Silversea
   - Company size, company type, founded year, phone: DO NOT change and do not invent. If a field is empty, leave it empty and list it for me at the end.

4. LOCATIONS
   - Primary: Rennerod, Germany (Ambiente Tours GmbH).
   - Second: Kuşadası, Türkiye (Ambiente Turizm Seyahat).
   - City and country only. Do not type a street address or postcode unless one is already on the page; if LinkedIn insists on a street, stop and ask me.

5. BUTTONS
   - Custom button: "Visit website", URL https://cruise24.me

6. IMAGES
   - Logo: cruise24-linkedin-logo.png (400 x 400).
   - Cover: cruise24-linkedin-cover.png (2256 x 382, LinkedIn's 1128 x 191 at double resolution).
   - When you reach an upload dialog, STOP and ask me to pick the file myself. Do not try to open files on my computer.

7. BEFORE SAVING: show me a short before/after list of every field you changed and wait for me to say "save". Only then click Save.

Rules:
- Write "Persian Gulf". Never "Arabian Gulf".
- Do not describe any cruise as visa-free, and do not add prices, dates, awards, customer numbers or years that are not in this prompt.
- Do not publish a post, invite followers, message anyone, change admins or change any setting outside the page details above.
- If a field on LinkedIn looks different from what this prompt expects, describe what you see and ask me; do not guess.
```
