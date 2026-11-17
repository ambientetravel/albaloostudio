# ideas/ — owner ideas that become briefs

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

The pipeline finds topics from Search Console gaps, seed lists and the model's own
planning. None of that can know what the owner just learned: a partner's email, a
product announcement, a photo from a trip, a voice note. This folder is that input.

One JSON file per idea, named `<YYYY-MM-DD>-<slug>.json`. Agent 1 (SEO Scout) reads the
files with `status: "new"`, and for every site named under `domains` it turns the idea
into a brief that ranks ABOVE measured gaps and seeds. Agent 2 (Writer) then drafts it
as it drafts any brief. Same compliance gate, same review PR, same ledger cooldown, so
an idea can never produce a twin of a live page or be written twice.

```json
{
  "id": "2026-11-17-walking-cruises-europe",
  "status": "new",
  "created": "2026-11-17",
  "title": "Cruise and walking holidays in Europe",
  "notes": ["Only facts from the source. Nothing invented."],
  "source": {"kind": "email", "from": "Crociere Europe", "date": "2026-11-17"},
  "domains": {
    "cruise24.me": {"query": "walking cruises europe", "angle": "who it suits, how a day works"}
  }
}
```

Rules the reader enforces:
* `query` is the exact phrase a traveller would type, in the site's own language. A site
  with no entry is untouched.
* `notes` are the ONLY facts the writer may use about the subject. They are attributed to
  the source, never copied word for word, and the source's product is never presented as
  ours. No price, date or itinerary appears unless a note carries it.
* A file older than 45 days, or with `status` other than `new`, is ignored.
* If the site already has a page for the phrase (same test as seeds) the idea is dropped
  and logged, not written as a twin.

Add one with `python3 tools/add_idea.py --help`, or just tell the orchestrator session.
Pictures: put the file next to the idea JSON and list it under `images`; the writer is
told it exists but a licence is still required before any picture is published.
