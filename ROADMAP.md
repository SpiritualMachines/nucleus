# Roadmap

Planned features and integrations under consideration.
Items are not committed or scheduled unless marked otherwise.

---

## Under Consideration

### QuickBooks Online Integration
Push Square and cash transactions recorded in Nucleus to QuickBooks Online automatically.

- OAuth 2.0 authentication with persistent encrypted token storage and auto-refresh
- Admin settings page to map Nucleus transaction types (membership, day pass, consumables, cash, card) to QBO Chart of Accounts
- Customer sync: look up or create QBO customer records matched to Nucleus members
- Idempotent push: store QBO transaction ID against each local transaction to prevent duplicates
- Sales Receipt creation per completed transaction
- Sandbox and production environment switching
- Phase 2 (separate scope): pull-back reconciliation to verify QBO matches local records

---

## Planned

### Square Recurring Membership Subscriptions

Enable members to enroll in automatically recurring membership subscriptions billed through Square,
with Nucleus syncing status daily rather than managing payments directly.

**Architecture**

- Nucleus creates or looks up the member as a Square Customer using their existing email address
- Nucleus creates a subscription against a Square Catalog Plan (aligned with Product Category tier templates)
- If no card is on file, Square sends the member a hosted payment link via email to complete enrollment
- Member enters card details on Square's hosted page — no card data touches Nucleus
- Square manages all recurring billing, payment retries, receipts, and cancellation emails
- Nucleus polls Square's ListSubscriptions endpoint daily (alongside the existing daily report scheduler)
  and maps subscription status to membership state:
  - ACTIVE: membership current
  - PAUSED / CANCELED / DELINQUENT: flag for staff review or trigger grace period logic

**Build Phases**

1. Trigger and poll: "Enroll in Subscription" button on member profile, daily sync job, subscription
   status stored against membership record. Spike against Square Sandbox first to confirm
   PENDING enrollment email behaviour (automatic vs. Nucleus-generated payment link).
2. Auto-renewal: on ACTIVE poll result, extend membership expiry automatically without staff action.
3. Staff visibility: subscription status column in member list, filter by subscription state.

**Notes**

- No inbound webhook infrastructure required for initial implementation; webhooks can be added
  when Nucleus moves to a web backend for real-time event handling.
- Square handles dunning and member-facing subscription management (card updates, cancellation).
- QBO integration (under consideration) will benefit naturally once subscription payments
  are flowing through Square consistently.
