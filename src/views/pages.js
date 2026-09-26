import { html } from './html.js';
import { layout } from './layout.js';
import { listingCard } from './listing.js';
import { PLATFORMS, TONES, LANGUAGES, INPUT_LIMITS } from '../platforms.js';
import { PACKS, formatMoney } from '../billing.js';
import { estimateCostUsd } from '../generator.js';

const perListing = (pack, currency) => formatMoney(Math.round(pack.priceCents / pack.credits), currency);

function pricingCards(config, { buyable }) {
  const free = html`<div class="price-card">
    <h3>Free</h3>
    <p class="price">$0</p>
    <p class="price-sub">${config.freeCredits} listings when you sign up</p>
    <ul><li>Every marketplace</li><li>All tones &amp; languages</li><li>No card required</li></ul>
    ${buyable ? '' : html`<a class="btn btn-ghost" href="/signup">Start free</a>`}
  </div>`;

  const paid = Object.entries(PACKS).map(
    ([id, pack]) => html`<div class="price-card ${pack.popular ? 'popular' : ''}">
    ${pack.popular ? html`<span class="ribbon">Most popular</span>` : ''}
    <h3>${pack.name}</h3>
    <p class="price">${formatMoney(pack.priceCents, config.currency)}</p>
    <p class="price-sub">${pack.credits} listings · ${perListing(pack, config.currency)} each</p>
    <ul><li>${pack.blurb}</li><li>Credits never expire</li><li>History &amp; CSV export</li></ul>
    ${buyable
      ? html`<form method="post" action="/billing/checkout"><input type="hidden" name="pack" value="${id}"><button class="btn ${pack.popular ? '' : 'btn-ghost'}" type="submit">Buy ${pack.name}</button></form>`
      : html`<a class="btn ${pack.popular ? '' : 'btn-ghost'}" href="/signup">Get started</a>`}
  </div>`,
  );
  return html`<div class="pricing-grid">${buyable ? '' : free}${paid}</div>`;
}

const EXAMPLE_TAGS = [
  'speckled mug', 'handmade mug', 'ceramic coffee mug', 'pottery mug', 'stoneware cup',
  'rustic mug', 'coffee lover gift', '12 oz mug', 'handmade pottery', 'kitchen gift',
  'tea cup', 'housewarming gift', 'minimalist mug',
];

export function landingPage({ config, user }) {
  const body = html`
<section class="hero">
  <div class="container hero-grid">
    <div>
      <p class="eyebrow">For Etsy, Amazon, Shopify &amp; eBay sellers</p>
      <h1>Product listings that get found, and get bought.</h1>
      <p class="lead">Paste your product notes. In about 20 seconds you get a search-optimized title, a description that sells, five punchy highlights and every tag, written to each marketplace's exact rules.</p>
      <div class="cta-row">
        <a class="btn btn-large" href="${user ? '/app' : '/signup'}">${user ? 'Write a listing' : `Write ${config.freeCredits} listings free`}</a>
        <a class="btn btn-ghost btn-large" href="#pricing">See pricing</a>
      </div>
      <p class="fineprint">No card required · No subscription · Credits never expire</p>
    </div>
    <div class="demo-card" aria-label="Example output">
      <div class="demo-input">
        <span class="demo-label">Your notes</span>
        <p>handmade ceramic mug, speckled white glaze, 12oz, dishwasher safe, made in my studio</p>
      </div>
      <div class="demo-output">
        <span class="demo-label">Etsy title <span class="limit">117/140</span></span>
        <p class="field-title">Handmade Speckled Ceramic Mug 12 oz, Rustic Stoneware Coffee Cup, Dishwasher Safe Pottery Mug, Gift for Coffee Lovers</p>
        <span class="demo-label">13 tags, all under 20 characters</span>
        <ul class="chips">${EXAMPLE_TAGS.map((t) => html`<li>${t}</li>`)}</ul>
      </div>
    </div>
  </div>
</section>

<section class="section">
  <div class="container">
    <h2 class="section-title">Hours of listing work, done in seconds</h2>
    <p class="section-lead">A strong listing takes 30 to 45 minutes of keyword research and copywriting. ${config.appName} does it for less than a quarter.</p>
    <div class="feature-grid">
      <div class="feature"><h3>Marketplace-exact</h3><p>Etsy's 140-character titles and 13 tags. Amazon's 5 bullets and 249-byte search terms. eBay's 80-character titles. Built in and checked on every listing.</p></div>
      <div class="feature"><h3>SEO that reads naturally</h3><p>The words shoppers actually search go where the algorithm looks first, without stuffing that turns buyers away.</p></div>
      <div class="feature"><h3>No made-up facts</h3><p>It only uses what you tell it, then points out missing details buyers ask about, like dimensions or care instructions.</p></div>
      <div class="feature"><h3>8 languages</h3><p>Sell across borders in English, Spanish, French, German, Italian, Portuguese, Dutch and Japanese.</p></div>
      <div class="feature"><h3>Your brand voice</h3><p>Friendly, professional, premium, playful or minimal. Every listing in your shop sounds like you.</p></div>
      <div class="feature"><h3>Saved and exportable</h3><p>Every listing is kept in your history. Export to CSV for bulk uploads and spreadsheets.</p></div>
    </div>
  </div>
</section>

<section class="section section-alt">
  <div class="container">
    <h2 class="section-title">How it works</h2>
    <ol class="steps">
      <li><strong>Describe it.</strong> Type what you'd tell a friend: what it is, what it's made of, who it's for.</li>
      <li><strong>Pick a marketplace.</strong> Choose where you sell, plus tone and language if you like.</li>
      <li><strong>Copy, paste, sell.</strong> One-click copy for every field, with character counts checked against the marketplace's limits.</li>
    </ol>
  </div>
</section>

<section class="section" id="pricing">
  <div class="container">
    <h2 class="section-title">Simple pricing. No subscription.</h2>
    <p class="section-lead">Pay once, use whenever. One credit = one complete listing.</p>
    ${pricingCards(config, { buyable: false })}
  </div>
</section>

<section class="section section-alt" id="faq">
  <div class="container narrow">
    <h2 class="section-title">Questions</h2>
    <details><summary>Is it really free to try?</summary><p>Yes. You get ${config.freeCredits} complete listings when you create an account. No credit card needed.</p></details>
    <details><summary>Which marketplaces do you support?</summary><p>Etsy, Amazon, Shopify and eBay, each with its own title limits, tag rules and style guidelines. There's also a general mode for WooCommerce, Squarespace, Wix and any other online store.</p></details>
    <details><summary>Do credits expire?</summary><p>Never. Buy a pack and use it this week or next year.</p></details>
    <details><summary>What if a listing fails to generate?</summary><p>You're only charged for listings that are delivered. If anything goes wrong, the credit goes straight back to your balance.</p></details>
    <details><summary>Who owns the copy?</summary><p>You do. Use it anywhere, edit it however you like.</p></details>
    <details><summary>Can I get a refund?</summary><p>If you're not happy, email <a href="mailto:${config.supportEmail}">${config.supportEmail}</a> within 14 days of purchase and we'll refund any unused credits.</p></details>
  </div>
</section>

<section class="section cta-band">
  <div class="container">
    <h2>Your next listing could be done before your coffee cools.</h2>
    <a class="btn btn-large btn-inverse" href="${user ? '/app' : '/signup'}">${user ? 'Write a listing' : 'Start free'}</a>
  </div>
</section>`;
  return layout({ config, user, body });
}

function authCard({ title, subtitle, error, info, form, footer }) {
  return html`<section class="auth">
  <div class="auth-card">
    <h1>${title}</h1>
    ${subtitle ? html`<p class="muted">${subtitle}</p>` : ''}
    ${error ? html`<div class="notice notice-error" role="alert">${error}</div>` : ''}
    ${info ? html`<div class="notice notice-ok" role="status">${info}</div>` : ''}
    ${form}
    ${footer ? html`<p class="auth-footer">${footer}</p>` : ''}
  </div>
</section>`;
}

export function signupPage({ config, error, email = '' }) {
  const body = authCard({
    title: 'Create your account',
    subtitle: `Get ${config.freeCredits} free listings. No card required.`,
    error,
    form: html`<form method="post" action="/signup" class="stack">
      <label>Email<input type="email" name="email" value="${email}" autocomplete="email" required></label>
      <label>Password<input type="password" name="password" minlength="8" autocomplete="new-password" required><small class="muted">At least 8 characters.</small></label>
      <button class="btn btn-block" type="submit">Create account</button>
      <p class="fineprint">By signing up you agree to the <a href="/terms">Terms</a> and <a href="/privacy">Privacy Policy</a>.</p>
    </form>`,
    footer: html`Already have an account? <a href="/login">Log in</a>`,
  });
  return layout({ config, title: 'Sign up', body });
}

export function loginPage({ config, error, info, email = '', next = '' }) {
  const body = authCard({
    title: 'Welcome back',
    error,
    info,
    form: html`<form method="post" action="/login" class="stack">
      <input type="hidden" name="next" value="${next}">
      <label>Email<input type="email" name="email" value="${email}" autocomplete="email" required></label>
      <label>Password<input type="password" name="password" autocomplete="current-password" required></label>
      <button class="btn btn-block" type="submit">Log in</button>
    </form>`,
    footer: html`<a href="/forgot">Forgot password?</a> · <a href="/signup">Create an account</a>`,
  });
  return layout({ config, title: 'Log in', body });
}

export function forgotPage({ config, sent }) {
  const body = authCard({
    title: 'Reset your password',
    info: sent ? 'If that email has an account, a reset link is on its way. It expires in 1 hour.' : null,
    form: html`<form method="post" action="/forgot" class="stack">
      <label>Email<input type="email" name="email" autocomplete="email" required></label>
      <button class="btn btn-block" type="submit">Send reset link</button>
    </form>`,
    footer: html`<a href="/login">Back to log in</a>`,
  });
  return layout({ config, title: 'Reset password', body, noindex: true });
}

export function resetPage({ config, token, error }) {
  const body = authCard({
    title: 'Choose a new password',
    error,
    form: html`<form method="post" action="/reset" class="stack">
      <input type="hidden" name="token" value="${token}">
      <label>New password<input type="password" name="password" minlength="8" autocomplete="new-password" required></label>
      <button class="btn btn-block" type="submit">Save password</button>
    </form>`,
  });
  return layout({ config, title: 'New password', body, noindex: true });
}

export function appPage({ config, user, generatorMode, billing, purchased, notice }) {
  const platformOptions = Object.entries(PLATFORMS).map(
    ([key, p], i) => html`<label class="pill"><input type="radio" name="platform" value="${key}" ${i === 0 ? 'checked' : ''}><span>${p.label}</span></label>`,
  );
  const body = html`
<div class="container app">
  ${generatorMode === 'demo'
    ? html`<div class="notice notice-warn"><strong>Demo mode.</strong> No <code>ANTHROPIC_API_KEY</code> is set, so listings are placeholder text. Add a key to generate real copy.</div>`
    : ''}
  ${purchased ? html`<div class="notice notice-ok" role="status"><strong>Payment received.</strong> ${purchased} credits were added to your account. Happy selling!</div>` : ''}
  ${notice ? html`<div class="notice notice-error" role="alert">${notice}</div>` : ''}

  <div class="app-grid">
    <form id="generate-form" class="card stack" autocomplete="off">
      <h1 class="card-title">Describe your product</h1>
      <fieldset>
        <legend>Where are you selling?</legend>
        <div class="pills">${platformOptions}</div>
      </fieldset>
      <label>Product
        <input name="productName" maxlength="${INPUT_LIMITS.productName}" placeholder="e.g. Handmade ceramic coffee mug" required>
      </label>
      <label>Details
        <textarea name="details" rows="7" maxlength="${INPUT_LIMITS.details}" data-counter required placeholder="Materials, size, colors, what makes it special, who it's for, care instructions… Bullet points or rough notes are fine."></textarea>
        <small class="muted counter" aria-live="polite"></small>
      </label>
      <details class="more-options">
        <summary>More options</summary>
        <div class="stack">
          <label>Target buyer <span class="muted">(optional)</span>
            <input name="audience" maxlength="${INPUT_LIMITS.audience}" placeholder="e.g. coffee lovers, new moms, gamers">
          </label>
          <label>Must-include keywords <span class="muted">(optional, comma separated)</span>
            <input name="keywords" maxlength="${INPUT_LIMITS.keywords}" placeholder="e.g. gift for her, boho decor">
          </label>
          <div class="row">
            <label>Tone
              <select name="tone">${Object.entries(TONES).map(([k, v]) => html`<option value="${k}">${v}</option>`)}</select>
            </label>
            <label>Language
              <select name="language">${Object.entries(LANGUAGES).map(([k, v]) => html`<option value="${k}">${v}</option>`)}</select>
            </label>
          </div>
        </div>
      </details>
      <div class="form-error notice notice-error" role="alert" hidden></div>
      <button class="btn btn-block btn-large" type="submit" data-label="Write my listing · 1 credit">Write my listing · 1 credit</button>
      <p class="fineprint center">You have <strong data-credits>${user.credits}</strong> credits. <a href="#buy">Get more</a></p>
    </form>

    <div id="result" class="result" aria-live="polite">
      <div class="result-empty">
        <p><strong>Your listing will appear here.</strong></p>
        <p class="muted">Tip: the more specific your details (materials, measurements, what's included), the better the listing.</p>
      </div>
    </div>
  </div>

  <section id="buy" class="buy">
    <h2>Get more listings</h2>
    <p class="muted">One-time purchase, no subscription. Credits never expire.</p>
    ${!billing.enabled && !billing.devFakePayments
      ? html`<div class="notice notice-warn">Payments aren't configured yet. Set <code>STRIPE_SECRET_KEY</code> to start selling credits.</div>`
      : ''}
    ${billing.devFakePayments
      ? html`<div class="notice notice-warn"><strong>Test mode:</strong> <code>DEV_FAKE_PAYMENTS</code> is on, so purchases add credits without charging.</div>`
      : ''}
    ${pricingCards(config, { buyable: true })}
  </section>
</div>`;
  return layout({ config, user, title: 'Write a listing', body, noindex: true });
}

export function historyPage({ config, user, generations }) {
  const body = html`<div class="container page">
  <div class="page-head">
    <h1>Your listings</h1>
    ${generations.length ? html`<a class="btn btn-ghost" href="/app/history.csv" download>Export CSV</a>` : ''}
  </div>
  ${generations.length
    ? html`<div class="table-wrap"><table class="table">
      <thead><tr><th>Product</th><th>Marketplace</th><th>Created</th><th></th></tr></thead>
      <tbody>${generations.map(
        (g) => html`<tr>
          <td>${g.product_name}</td>
          <td>${PLATFORMS[g.platform]?.label || g.platform}</td>
          <td><time datetime="${g.created_at.replace(' ', 'T')}Z">${g.created_at.slice(0, 10)}</time></td>
          <td class="right"><a href="/app/listing/${g.id}">Open</a></td>
        </tr>`,
      )}</tbody></table></div>`
    : html`<div class="card center"><p>No listings yet.</p><a class="btn" href="/app">Write your first listing</a></div>`}
</div>`;
  return layout({ config, user, title: 'History', body, noindex: true });
}

export function listingPage({ config, user, generation, listing, warnings }) {
  const input = JSON.parse(generation.input_json);
  const body = html`<div class="container page narrow">
  <p><a href="/app/history">← All listings</a></p>
  <h1>${generation.product_name}</h1>
  <p class="muted">${PLATFORMS[generation.platform]?.label} · ${TONES[input.tone] || ''} · ${LANGUAGES[input.language] || ''} · ${generation.created_at.slice(0, 16).replace('T', ' ')} UTC</p>
  ${listingCard({ platform: generation.platform, listing, warnings })}
  <details class="card"><summary>Your original notes</summary><div class="prewrap">${input.details}</div></details>
</div>`;
  return layout({ config, user, title: generation.product_name, body, noindex: true });
}

export function accountPage({ config, user, purchases }) {
  const body = html`<div class="container page narrow">
  <h1>Account</h1>
  <div class="card stack">
    <p><strong>Email:</strong> ${user.email}</p>
    <p><strong>Credits:</strong> ${user.credits} <a href="/app#buy">Buy more</a></p>
    <p><strong>Member since:</strong> ${user.created_at.slice(0, 10)}</p>
    <p><a href="/forgot">Change password</a></p>
  </div>
  <h2>Purchases</h2>
  ${purchases.length
    ? html`<div class="table-wrap"><table class="table"><thead><tr><th>Date</th><th>Pack</th><th>Credits</th><th class="right">Amount</th></tr></thead>
      <tbody>${purchases.map(
        (p) => html`<tr><td>${p.created_at.slice(0, 10)}</td><td>${PACKS[p.pack]?.name || p.pack}</td><td>${p.credits}</td><td class="right">${formatMoney(p.amount_cents, p.currency)}</td></tr>`,
      )}</tbody></table></div>`
    : html`<p class="muted">No purchases yet.</p>`}
  <p class="muted">Need an invoice or a refund? Email <a href="mailto:${config.supportEmail}">${config.supportEmail}</a>.</p>
</div>`;
  return layout({ config, user, title: 'Account', body, noindex: true });
}

export function adminPage({ config, user, stats, message }) {
  const usd = (n) => (n === null ? '–' : `$${n.toFixed(4)}`);
  const body = html`<div class="container page">
  <h1>Admin</h1>
  ${message ? html`<div class="notice notice-ok">${message}</div>` : ''}
  <div class="stat-grid">
    <div class="stat"><span>Revenue</span><strong>${formatMoney(stats.revenueCents, config.currency)}</strong></div>
    <div class="stat"><span>Users</span><strong>${stats.users}</strong><small>+${stats.signups7d} this week</small></div>
    <div class="stat"><span>Paying users</span><strong>${stats.payingUsers}</strong><small>${stats.users ? ((stats.payingUsers / stats.users) * 100).toFixed(1) : 0}% conversion</small></div>
    <div class="stat"><span>Listings written</span><strong>${stats.generations}</strong><small>${stats.generations7d} this week</small></div>
  </div>

  <h2>AI cost per listing</h2>
  <div class="table-wrap"><table class="table">
    <thead><tr><th>Model</th><th>Listings</th><th>Avg input tokens</th><th>Avg output tokens</th><th class="right">Avg cost</th></tr></thead>
    <tbody>${stats.tokensByModel.map((m) => {
      const avgIn = m.n ? m.input_tokens / m.n : 0;
      const avgOut = m.n ? m.output_tokens / m.n : 0;
      return html`<tr><td>${m.model}</td><td>${m.n}</td><td>${Math.round(avgIn)}</td><td>${Math.round(avgOut)}</td><td class="right">${usd(estimateCostUsd(m.model, avgIn, avgOut))}</td></tr>`;
    })}</tbody>
  </table></div>

  <h2>Grant credits</h2>
  <form method="post" action="/admin/grant" class="row card">
    <label>Email<input type="email" name="email" required></label>
    <label>Credits<input type="number" name="credits" min="1" max="10000" value="10" required></label>
    <button class="btn" type="submit">Grant</button>
  </form>

  <h2>Recent purchases</h2>
  <div class="table-wrap"><table class="table">
    <thead><tr><th>Date</th><th>Email</th><th>Pack</th><th class="right">Amount</th></tr></thead>
    <tbody>${stats.recentPurchases.map(
      (p) => html`<tr><td>${p.created_at}</td><td>${p.email}</td><td>${p.pack}</td><td class="right">${formatMoney(p.amount_cents, p.currency)}</td></tr>`,
    )}</tbody>
  </table></div>

  <h2>Recent signups</h2>
  <div class="table-wrap"><table class="table">
    <thead><tr><th>Date</th><th>Email</th><th class="right">Credits</th></tr></thead>
    <tbody>${stats.recentUsers.map(
      (u) => html`<tr><td>${u.created_at}</td><td>${u.email}</td><td class="right">${u.credits}</td></tr>`,
    )}</tbody>
  </table></div>
</div>`;
  return layout({ config, user, title: 'Admin', body, noindex: true });
}

export function legalPage({ config, user, kind }) {
  const name = config.appName;
  const updated = 'Last updated: see repository history';
  const terms = html`
    <h1>Terms of Service</h1>
    <p class="muted">${updated}</p>
    <p>By using ${name} you agree to these terms.</p>
    <h2>The service</h2>
    <p>${name} uses artificial intelligence to draft product listing copy from the information you provide. Output may contain mistakes. You are responsible for reviewing listings before publishing them and for making sure they are accurate and comply with the rules of the marketplaces you sell on.</p>
    <h2>Accounts</h2>
    <p>Keep your password secure. You are responsible for activity on your account. Don't use the service to create misleading, illegal or infringing content, and don't attempt to abuse free credits with multiple accounts.</p>
    <h2>Credits and payments</h2>
    <p>Credits are purchased in one-time packs, processed by Stripe. One credit produces one listing. Credits do not expire and have no cash value. If a listing fails to generate, the credit is returned automatically. You may request a refund of unused credits within 14 days of purchase by emailing <a href="mailto:${config.supportEmail}">${config.supportEmail}</a>.</p>
    <h2>Your content</h2>
    <p>You keep all rights to the information you submit and to the listings generated for you.</p>
    <h2>Liability</h2>
    <p>The service is provided "as is" without warranties of any kind. To the maximum extent permitted by law, our liability is limited to the amount you paid us in the 12 months before a claim.</p>
    <h2>Changes</h2>
    <p>We may update these terms. Continued use after changes means you accept them.</p>
    <h2>Contact</h2>
    <p><a href="mailto:${config.supportEmail}">${config.supportEmail}</a></p>`;
  const privacy = html`
    <h1>Privacy Policy</h1>
    <p class="muted">${updated}</p>
    <h2>What we collect</h2>
    <p>Your email address, a securely hashed password, the product details you submit, the listings we generate, and a record of your purchases. Payment card details are handled by Stripe and never touch our servers.</p>
    <h2>How we use it</h2>
    <p>To run your account, generate your listings, show your history, process payments and provide support. Product details you submit are sent to our AI provider (Anthropic) solely to generate your listing.</p>
    <h2>What we don't do</h2>
    <p>We don't sell your data, and we don't use advertising trackers.</p>
    <h2>Cookies</h2>
    <p>We use a single essential cookie to keep you logged in.</p>
    <h2>Your rights</h2>
    <p>Email <a href="mailto:${config.supportEmail}">${config.supportEmail}</a> to export or delete your data at any time.</p>`;
  const body = html`<div class="container page narrow prose">${kind === 'terms' ? terms : privacy}</div>`;
  return layout({ config, user, title: kind === 'terms' ? 'Terms' : 'Privacy', body });
}

export function notFoundPage({ config, user }) {
  const body = html`<div class="container page narrow center"><h1>Page not found</h1><p><a class="btn" href="/">Go home</a></p></div>`;
  return layout({ config, user, title: 'Not found', body, noindex: true });
}
