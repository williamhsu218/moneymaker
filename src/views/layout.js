import { html } from './html.js';

export const logo = html`<svg class="logo-mark" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2l2.2 6.6L21 11l-6.8 2.4L12 20l-2.2-6.6L3 11l6.8-2.4z" fill="currentColor"/><circle cx="19" cy="4.5" r="1.6" fill="currentColor"/></svg>`;

export function layout({ config, user, title, description, body, bodyClass = '', noindex = false }) {
  const pageTitle = title ? `${title} · ${config.appName}` : `${config.appName} – AI product listings for Etsy, Amazon, Shopify & eBay`;
  const metaDescription =
    description ||
    'Write search-optimized product titles, descriptions, bullet points and tags for Etsy, Amazon, Shopify and eBay in seconds. 5 free listings, no card required.';

  return html`<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${pageTitle}</title>
<meta name="description" content="${metaDescription}">
${noindex ? html`<meta name="robots" content="noindex">` : ''}
<meta property="og:title" content="${pageTitle}">
<meta property="og:description" content="${metaDescription}">
<meta property="og:type" content="website">
<meta property="og:url" content="${config.baseUrl}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/styles.css">
<script src="/app.js" defer></script>
</head>
<body class="${bodyClass}">
<header class="site-header">
  <div class="container nav">
    <a class="brand" href="${user ? '/app' : '/'}">${logo}<span>${config.appName}</span></a>
    <nav class="nav-links">
      ${user
        ? html`
          <a href="/app">Write</a>
          <a href="/app/history">History</a>
          <a href="/app/account">Account</a>
          <a class="credits-pill" href="/app#buy" title="Listings left"><span data-credits>${user.credits}</span> credits</a>
          <form method="post" action="/logout" class="inline"><button class="link-button" type="submit">Log out</button></form>`
        : html`
          <a href="/#pricing" class="hide-sm">Pricing</a>
          <a href="/#faq" class="hide-sm">FAQ</a>
          <a href="/login">Log in</a>
          <a class="btn btn-small" href="/signup">Start free</a>`}
    </nav>
  </div>
</header>
<main>
${body}
</main>
<footer class="site-footer">
  <div class="container footer-inner">
    <span>© ${new Date().getFullYear()} ${config.appName}</span>
    <nav>
      <a href="/#pricing">Pricing</a>
      <a href="/terms">Terms</a>
      <a href="/privacy">Privacy</a>
      <a href="mailto:${config.supportEmail}">Contact</a>
    </nav>
  </div>
</footer>
</body>
</html>`.toString();
}
