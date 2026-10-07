---
name: run-means-hand-over
description: "When asked to \"run the system/dashboard\", start it and give the user the URL — don't drift into test drives or debugging side issues"
metadata:
  node_type: memory
  type: feedback
  originSessionId: f00aab06-eab2-417f-a14e-13e54f10a9af
  modified: 2026-09-29T03:18:29.530Z
---

When the user asks to "run the system" or "run the dashboard", they want it up so *they* can use it: start `streamlit run src/dashboard/app.py` (themesync_env, `--server.address 127.0.0.1 --server.port 8501`) and hand over the URL.

**Why:** On 2026-09-29 I started it, then kept driving it with Selenium and began probing a Figure 2 preview glitch; the user rejected the probe and repeated "run the system (dashboard)".

**How to apply:** Launch, confirm it answers, give the link. Mention anything broken you noticed in one line and offer to fix it; don't investigate unasked. Related: [[themesync-thesis-context]].
