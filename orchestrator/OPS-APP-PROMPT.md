# Prompt to paste into the base44 AI builder (new app)

Paste everything between the lines, in one message. Don't add sample data.

---

Build a mobile-first internal app called **Albaloo Ops**. It's the control room for a travel company's content and sales pipeline. Staff use it mostly on their phones. Design: clean, large tap targets, bottom tab bar on mobile, sidebar on desktop, light and dark mode. Support right-to-left text, because many articles are in Farsi.

**Login and access**
- Users must log in. Only invited users can sign up.
- Add to User: `role` (one of owner, manager, sales, content, partner, viewer; default viewer) and `properties` (list of website domains this person works on).
- owner and manager see every record. Everyone else sees only records whose `property` is in their own `properties` list. partner sees only Lead records where `partner_id` equals their own `partner_id` (add `partner_id` text to User).
- Only owner can edit users' role, properties and partner_id.

**Data tables** (all written by an external sync service through the API, unless marked "staff edit")

1. **ArticleReview**: property, repo, pr_number, pr_url, title, language (en or fa), word_count, house_rules_verdict (PASS, WARN or BLOCK), verdict_notes (long text), body_markdown (long text), created_at, age_days, status (to_review, approved, needs_edits, rejected, published, closed), live_url, synced_at. **Staff edit:** decision (publish, needs_edits, reject), feedback (long text), decided_by, decided_at.
2. **AgentRun**: agent, result (success, failure, skipped), age_days, run_url, synced_at.
3. **HealthItem**: level (critical, needs_you, warn, fine), text, property, synced_at.
4. **Metric**: name, value (number), previous (number), synced_at.
5. **Lead**: property, partner_id, source, language, summary, qualification (hot, warm, cold), draft_reply (long text), escalated (yes or no), escalation_reason, created_at, synced_at. **Staff edit:** status (new, contacted, quoted, won, lost), assigned_to, notes, reply_released (yes or no).
6. **SocialPost**: property, channel, copy (long text), image_url, article_url, status (held, approved, rejected, posted), synced_at. **Staff edit:** decision (approve, reject), decided_by, decided_at.

**Pages**

1. **Review** (home page, first tab). A list of ArticleReview where status = to_review, oldest first. Each card shows the title, site, language flag, how many days it has been waiting (red if more than 3 days), word count and the house-rules verdict as a coloured badge. A badge on the tab shows the count waiting. Tapping a card opens the full article rendered from body_markdown (right-to-left when language = fa), the verdict notes, and a link to the PR. At the bottom, three big buttons: **Publish**, **Needs edits** (requires feedback text), **Reject** (requires a reason). Pressing one saves decision, feedback, decided_by = the current user and decided_at = now, then shows "Sent. Publishes on the next sync (within an hour)." If house_rules_verdict = BLOCK, disable Publish and show the notes.
2. **Today**. A "Needs you" list (HealthItem level critical or needs_you), then one coloured card per AgentRun (green success, red failure, grey skipped, amber if age_days > 8), then a row of Metric tiles showing value and its change from previous.
3. **Leads**. Tabs: New, Mine, All. Each card shows the summary, site, qualification badge and age. Detail shows the draft reply with a Copy button, a status picker, assign-to, notes, and a "Mark reply sent" toggle. This app never sends messages to customers itself.
4. **Social**. SocialPost with status = held, shown as a preview card (image + copy) with Approve and Reject buttons.
5. **Team** (owner only). Users with role, properties and partner_id editable.

Every page shows a small "Last synced: <time>" from the newest synced_at. Empty states say "Nothing waiting" in a friendly tone. Don't create sample or placeholder records.

---

## After base44 builds it

1. Copy the app ID from the browser address bar (`app.base44.com/apps/<APP_ID>/…`) and give it to the "4-Agent orchestration pipeline" session.
2. Invite your team in base44 and set each person's role and properties on the Team page.
3. On your phone, open the app's published URL and choose **Add to Home Screen**. It then behaves like an app.
