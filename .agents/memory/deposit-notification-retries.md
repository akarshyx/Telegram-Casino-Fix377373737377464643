---
name: Deposit notification retries
description: Deposit credits and Telegram notifications have separate delivery guarantees.
---

Persist the payment credit before sending Telegram notifications, mark each notification delivered only after a successful Telegram response, and retry missing notifications without re-crediting.

**Why:** Telegram/network failures must not lose a confirmed deposit notification or cause a payment to be credited twice.

**How to apply:** Keep payment deduplication independent from processing/confirmation notification markers; retry notifications from the saved pending-payment record.