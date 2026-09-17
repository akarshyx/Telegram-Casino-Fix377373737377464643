---
name: Admin callback routing
description: Owner and manager action buttons are sent from user-triggered handlers and need special treatment by message ownership protection.
---

Admin approval/rejection callbacks must be exempted from player-message ownership checks, while their individual handlers must continue enforcing owner/manager authorization.

**Why:** The ownership tracker records the user whose handler sent a notification, not necessarily the administrator who receives it. Without the exemption, an owner pressing a withdrawal button is incorrectly told it belongs to another player.

**How to apply:** When adding a new owner/manager callback family, add its prefix to the shared/private callback allowlists and keep authorization in the routed handler.