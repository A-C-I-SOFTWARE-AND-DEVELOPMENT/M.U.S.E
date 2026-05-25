# Rule: Owner-Only vs Code-Side Blockers

Every audit and implementation closes with two separate lists:

**Code-side blockers** — things Claude can fix in the repo.

**Owner-only blockers** — things that require a human and an external
service: Play Console, App Store Connect, Vercel / Netlify / Cloudflare
dashboards, Supabase / Firebase project settings, DNS, Stripe products and
prices, domain registrar, legal sign-off, identity provider consoles,
support inbox, irreversible business decisions.

Each owner-only item includes:

- **Where** — the dashboard or URL.
- **What** — the action.
- **Why** — what it unblocks.
- **How to verify done** — so the owner knows when it's truly off the list.

Never claim Claude can do an owner-only item. Never bury one inside a
code-side item.
