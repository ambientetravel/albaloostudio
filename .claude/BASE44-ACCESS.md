# How sessions reach base44

Written 24 Oct 2026 from the working session **"Ambiente Travel website setup"**
(`session_01DTYkyokkdVRd3h6BXL51w5`), which shipped `/AmbiTours` on
ambientetravel.com the same day.

## What actually works

That session does **not** use a base44 MCP connector. Its MCP server list is
empty for base44. It works like this:

1. It is a **Remote Control session running on Alireza's Mac** (started with
   `claude remote-control`, or from the Claude Desktop app). It shows up in the
   Claude Code app like any other session, but its tools run on the Mac.
2. It drives the **base44 web editor in his own logged-in Chrome** through the
   **Claude in Chrome** extension (`browser_batch`, `javascript_tool`,
   `tabs_context_mcp`).
3. Edits go into the code view, e.g.
   `https://app.base44.com/apps/<appId>/editor/workspace/code?filePath=src%2FApp.jsx`,
   then **Save**, then **Publish** (the last Publish button in the panel).
4. It verifies on the live domain afterwards.

No API key and no base44 credits are spent on code edits made this way. Only the
base44 AI chat spends credits.

## Why the base44 connector fails in cloud sessions

Cloud sessions (claude.ai/code, phone, desktop "cloud") show:

    base44 (404): CLIENT_HTTP_NOT_IMPLEMENTED

The connector entry exists, but this cloud runtime can't open it. A cloud
container also can't reach his Chrome or his base44 login. **A cloud session can't
edit base44.** Don't retry. Do one of these instead:

- **Hand the base44 part to a Mac session.** Use "Ambiente Travel website setup"
  for ambientetravel.com, or the owning session in `session-routing.json`. Use
  `send_message` with the finished spec: file, route and exact text.
- Or reconnect base44 at https://claude.ai/customize/connectors and **start a new
  session**, because connectors load only at session start. Until a new session
  shows base44 tools working, assume the Chrome route is the only route.

## To start a base44-capable session

On the Mac, in the project folder:

    claude remote-control

Chrome must be open with the Claude in Chrome extension enabled and logged in to
base44. The session then appears in the Claude Code app and can be reached from
the phone.

## base44 traps (confirmed live, 24 Oct 2026)

- **No file-create control.** New pages are a component plus a
  `<Route path="/X">` inside `src/App.jsx`. Branded 404, AmbiMare river detail and
  AmbiTOURS all use this pattern.
- **The SEO Meta-tags table won't save a title for a route that isn't in
  `pages.config.js`.** It says "saved", then silently reverts. Set titles
  client-side with `useDocumentMeta(title, description)` in App.jsx. That's also
  the only way to give each `?param=` view its own title.
- **React effect order:** child effects run before parent ones. Make **one**
  `useDocumentMeta` call in the parent, branching on state, or the parent
  overwrites the child's title.
- **Find settings fields by `data-testid`, never by textarea index.** The AI-chat
  box placeholder changed to "What do you want to change?". An index-based filter
  once typed an SEO title into the AI chat. It was caught before sending, but
  sending it would have spent credits.
- `public/sitemap.xml` was listing 28 legacy redirect URLs out of 41. After any
  route change, rebuild it from real routes and diff it against the live file.
- ambientetravel.com is a client-rendered SPA. Its DNS zone is on Wix
  nameservers, with apex A → 216.24.57.1.
