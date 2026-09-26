# ListingSpark

**AI product listings for Etsy, Amazon, Shopify and eBay sellers, sold as credit packs.**

Sellers paste rough product notes and get back a search-optimized title, a description, five highlights, the right number of tags, a meta description and target keywords. Each listing follows the marketplace's own rules (Etsy's 140-character titles and 13 tags of up to 20 characters, Amazon's 5 bullets and 249-byte search terms, eBay's 80-character titles), and the app checks those limits on every result.

You make money by selling one-time credit packs through Stripe. New accounts get 5 free listings, and each paid listing costs you about 5¢ in AI fees against 17–24¢ in revenue.

| | |
|---|---|
| **Customers** | Etsy, Amazon, Shopify and eBay sellers: millions of small businesses that write listings by hand |
| **Pricing** | Free: 5 listings · Starter $12 / 50 · Growth $39 / 200 · Pro $99 / 600. Credits never expire |
| **Margin** | ~65–75% gross after AI and Stripe fees (see [Money math](#money-math)) |
| **Fixed costs** | ~$10/month (hosting plus a domain) |
| **Stack** | Node 22, Express, SQLite (built into Node), Stripe Checkout, Claude API. No build step |

For how to get your first customers, see **[LAUNCH.md](LAUNCH.md)**.

---

## Run it locally (2 minutes)

```bash
npm install
cp .env.example .env
npm run dev
```

Open http://localhost:3000 and sign up. With no API keys set:

- **The AI runs in demo mode.** It returns placeholder listings so you can click through everything at no cost.
- **Payments are off.** Set `DEV_FAKE_PAYMENTS=true` in `.env` to make the "Buy" buttons add credits without charging, so you can test the full purchase flow.
- **Password-reset emails are printed** to the terminal.

To see real listings, add your `ANTHROPIC_API_KEY` to `.env` and restart.

## Go live checklist

### 1. Anthropic (the AI)
1. Create an API key at https://console.anthropic.com and add billing.
2. Set `ANTHROPIC_API_KEY`.

The default model is `claude-opus-5` at `low` effort. If Claude's safety filters decline a request, it is retried automatically on a fallback model (`fallbacks: "default"`). If a generation fails for any reason, the customer's credit is refunded.

### 2. Stripe (getting paid)
1. Create a Stripe account and complete business verification. Stripe requires the Terms, Privacy and contact pages, which the app already has.
2. Copy your **secret key** into `STRIPE_SECRET_KEY`. Use `sk_test_...` first, then `sk_live_...`.
3. In **Developers → Webhooks**, add an endpoint:
   - URL: `https://YOUR_DOMAIN/webhooks/stripe`
   - Events: `checkout.session.completed` and `checkout.session.async_payment_succeeded`
4. Copy the endpoint's **signing secret** into `STRIPE_WEBHOOK_SECRET`.

You don't need to create products in Stripe, because prices are defined in `src/billing.js`. Promotion codes are enabled at checkout, so coupons you create in Stripe work immediately.

Credits are added in two ways: by the webhook, and as a backup when the buyer returns from Stripe. Both paths are idempotent, so a purchase is never credited twice.

To test, use card `4242 4242 4242 4242` with any future date and any CVC while on test keys.

### 3. Email (password resets)
1. Create a free account at https://resend.com and verify your domain.
2. Set `RESEND_API_KEY` and `EMAIL_FROM` (e.g. `ListingSpark <hello@yourdomain.com>`).

### 4. Deploy
The app is one Docker container plus one SQLite file. The file needs a **persistent disk** mounted at `/data`.

- **Render (easiest):** push this repo to GitHub, then in Render choose **New → Blueprint** and pick the repo. `render.yaml` sets up the service and a 1 GB disk. Fill in the secret env vars when prompted.
- **Railway / Fly.io / any VPS:** build the `Dockerfile`, mount a volume at `/data`, and set the env vars from `.env.example`.

Required production settings: `NODE_ENV=production`, `BASE_URL=https://yourdomain.com`, `TRUST_PROXY=true` (behind a platform proxy), `SUPPORT_EMAIL` and `ADMIN_EMAILS`. The site must be served over HTTPS because session cookies are marked `Secure` in production.

### 5. Before announcing
- [ ] Make a real purchase with a live card, then refund it in Stripe.
- [ ] Read `/terms` and `/privacy` (in `src/views/pages.js`) and adjust them to your business and jurisdiction.
- [ ] Check that the name "ListingSpark" is free to use where you sell, or change `APP_NAME`.
- [ ] Set up backups of `/data/app.db`, e.g. [Litestream](https://litestream.io) to S3, or a nightly `sqlite3 app.db ".backup ..."`.
- [ ] Log in with an `ADMIN_EMAILS` address and open `/admin`.

## Money math

These are estimates. `/admin` shows your **actual** average AI cost per listing from real token usage, so check it after your first ~50 listings and adjust.

AI cost per listing with `claude-opus-5` at `low` effort: roughly 1.5K input tokens + 1.5K output tokens ≈ **$0.05**. Stripe charges 2.9% + 30¢ per purchase (US cards).

| Pack | Price | Stripe fee | AI cost (all credits used) | Gross profit | Margin |
|---|---|---|---|---|---|
| Starter · 50 | $12 | $0.65 | $2.50 | **$8.85** | 74% |
| Growth · 200 | $39 | $1.43 | $10.00 | **$27.57** | 71% |
| Pro · 600 | $99 | $3.17 | $30.00 | **$65.83** | 66% |

Real margins are higher because not every purchased credit gets used. Each free signup costs you about 25¢ (5 × 5¢).

**What it takes:** about 37 Growth packs a month is $1,000 gross profit. About 180 a month is $5,000.

## Tuning

| Change | Where |
|---|---|
| Pack prices and sizes | `PACKS` in `src/billing.js` |
| Free credits per signup | `FREE_CREDITS` env var |
| AI quality vs. cost | `CLAUDE_EFFORT` (`low` / `medium` / `high`) and `CLAUDE_MODEL` env vars. Re-check `/admin` cost after any change |
| Marketplace rules and limits | `src/platforms.js` |
| Prompt and output format | `SYSTEM_PROMPT` and `LISTING_SCHEMA` in `src/generator.js` |
| Landing page copy, FAQ, legal text | `src/views/pages.js` |
| Colors and styling | `public/styles.css` (brand color is `--brand`) |

## Admin dashboard (`/admin`)

Available only to emails in `ADMIN_EMAILS`. It shows revenue, users, paid conversion rate, listings written, the real AI cost per listing, recent purchases and signups. It also has a form to **grant credits** by email, which is useful for support, refunds-as-credit and influencer deals. Every credit change is recorded in the `credit_events` table.

## Project layout

```
src/
  server.js        entry point: wires everything and starts listening
  app.js           all routes (pages, auth, /api/generate, billing, admin)
  config.js        every environment variable in one place
  db.js            SQLite schema, migrations and all queries
  generator.js     Claude call (structured JSON output) + offline demo generator
  platforms.js     marketplace rules, input validation, limit checks
  billing.js       credit packs, Stripe Checkout, webhook fulfillment
  auth.js          scrypt passwords, sessions, password resets
  security.js      security headers, CSRF origin check, rate limiting
  mailer.js        Resend email (or console fallback)
  views/           server-rendered HTML (auto-escaped templates)
public/            CSS, browser JS, favicon
test/              node:test suite (no network needed)
```

## Tests

```bash
npm test
```

The suite covers signup and login, password reset, credit spending and refunds, CSRF blocking, listing privacy, CSV export, Stripe webhook signature checks and idempotency, fake payments, the admin page, and the Claude request shape including refusal, fallback and rate-limit handling. It runs fully offline.

## Security notes

- Passwords are hashed with scrypt, and session and reset tokens are stored only as SHA-256 hashes.
- Session cookies are `HttpOnly` and `SameSite=Lax` (plus `Secure` in production), and every state-changing request must come from your own origin.
- The CSP allows only same-origin scripts. All HTML output is escaped by default.
- Login, signup, password reset and generation are rate limited. The limiter is in memory, so move it to Redis if you ever run more than one instance.
- CSV exports neutralize spreadsheet formula injection.
- Stripe webhooks are signature-verified, and purchases are keyed on the Checkout Session id so they can't be double-credited.

## Roadmap: ways to earn more per customer

1. **Free SEO tools as lead magnets.** An "Etsy tag checker" or "Amazon title length checker" page ranks in Google and funnels sellers to signup. This is the highest-leverage next build.
2. **Bulk mode.** Upload a CSV of products and download finished listings. This is what agencies and big catalogs will pay the Pro tier for.
3. **Photo to listing.** Claude reads product photos, so sellers can upload an image instead of typing notes.
4. **Subscription option.** For example, $19/month for 150 listings, for sellers who prefer predictable billing.
5. **Direct publishing.** Push listings straight to Etsy or Shopify through their APIs.
6. **Affiliate program.** Pay Etsy coaches and YouTubers 30% of what their referrals spend.
