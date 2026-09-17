---
name: Health route order
description: Flask liveness endpoints coexist with a single-segment web-app catch-all.
---

Register operational endpoints such as health and status before the `/<user_id>` web-app catch-all route.

**Why:** Unregistered liveness paths are captured as user-page routes and can return 500 instead of a reliable health response.

**How to apply:** Add new monitoring paths alongside `/healthz` before any generic single-segment route.