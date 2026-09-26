import path from 'node:path';
import { fileURLToPath } from 'node:url';
import express from 'express';

import {
  createAuth,
  hashPassword,
  verifyPassword,
  validateCredentials,
  requireUser,
  requireAdmin,
  safeNext,
  newToken,
  hashToken,
  RESET_TTL_MS,
} from './auth.js';
import { securityHeaders, sameOriginOnly, rateLimit } from './security.js';
import { parseGenerateInput, checkListing } from './platforms.js';
import { GenerationError } from './generator.js';
import { CHECKOUT_ERRORS } from './billing.js';
import { listingCard } from './views/listing.js';
import * as pages from './views/pages.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const MINUTE = 60 * 1000;

// Used to keep login timing identical whether or not the email exists.
const DUMMY_HASH = await hashPassword('timing-equalizer-password');

export function createApp({ config, store, generator, billing, mailer }) {
  const app = express();
  const auth = createAuth({ store, config });

  app.disable('x-powered-by');
  app.set('trust proxy', config.trustProxy ? 1 : false);
  app.use(securityHeaders(config));
  app.use(express.static(path.join(here, '..', 'public'), { maxAge: config.isProduction ? '1h' : 0 }));

  app.get('/healthz', (_req, res) => res.json({ ok: true }));

  // Stripe needs the raw body to verify signatures, so this route is
  // registered before the body parsers.
  app.post('/webhooks/stripe', express.raw({ type: 'application/json', limit: '1mb' }), (req, res) => {
    try {
      billing.handleWebhook(req.body, req.get('stripe-signature'));
      res.json({ received: true });
    } catch (err) {
      console.error(`[webhook] ${err.message}`);
      res.status(err.status || 500).send(err.message);
    }
  });

  app.use(express.urlencoded({ extended: false, limit: '20kb' }));
  app.use(express.json({ limit: '20kb' }));
  app.use(auth.loadUser);
  app.use(sameOriginOnly(config, { exempt: ['/webhooks/'] }));

  const render = (res, html, status = 200) => res.status(status).type('html').send(html);
  const ctx = (req, extra = {}) => ({ config, user: req.user, ...extra });

  // ---------- public pages ----------
  app.get('/', (req, res) => render(res, pages.landingPage(ctx(req))));
  app.get('/terms', (req, res) => render(res, pages.legalPage(ctx(req, { kind: 'terms' }))));
  app.get('/privacy', (req, res) => render(res, pages.legalPage(ctx(req, { kind: 'privacy' }))));

  app.get('/robots.txt', (_req, res) =>
    res.type('text/plain').send(`User-agent: *\nDisallow: /app\nDisallow: /admin\nSitemap: ${config.baseUrl}/sitemap.xml\n`),
  );
  app.get('/sitemap.xml', (_req, res) => {
    const urls = ['/', '/signup', '/login', '/terms', '/privacy']
      .map((p) => `<url><loc>${config.baseUrl}${p}</loc></url>`)
      .join('');
    res.type('application/xml').send(
      `<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${urls}</urlset>`,
    );
  });

  // ---------- auth ----------
  const authLimiter = rateLimit({ windowMs: 15 * MINUTE, max: 20, message: 'Too many attempts. Try again in a few minutes.' });
  const signupLimiter = rateLimit({ windowMs: 60 * MINUTE, max: 10, message: 'Too many sign-ups from this network. Try again later.' });
  const forgotLimiter = rateLimit({ windowMs: 60 * MINUTE, max: 5, message: 'Too many reset requests. Try again later.' });

  app.get('/signup', (req, res) => (req.user ? res.redirect(303, '/app') : render(res, pages.signupPage(ctx(req)))));

  app.post('/signup', signupLimiter, async (req, res) => {
    const email = String(req.body?.email || '').trim().toLowerCase();
    const password = req.body?.password;
    const error = validateCredentials(email, password);
    if (error) return render(res, pages.signupPage(ctx(req, { error, email })), 400);

    const taken = () =>
      render(
        res,
        pages.signupPage(ctx(req, { error: 'An account with that email already exists. Try logging in.', email })),
        409,
      );
    if (store.getUserByEmail(email)) return taken();

    const passwordHash = await hashPassword(password);
    let userId;
    try {
      userId = store.createUser(email, passwordHash, config.freeCredits);
    } catch (err) {
      // Two signups for the same email raced past the check above.
      if (store.getUserByEmail(email)) return taken();
      throw err;
    }
    auth.startSession(res, userId);
    res.redirect(303, '/app');
  });

  app.get('/login', (req, res) => {
    if (req.user) return res.redirect(303, safeNext(req.query.next));
    const info = req.query.reset ? 'Password updated. Log in with your new password.' : null;
    render(res, pages.loginPage(ctx(req, { next: safeNext(req.query.next), info })));
  });

  app.post('/login', authLimiter, async (req, res) => {
    const email = String(req.body?.email || '').trim().toLowerCase();
    const password = String(req.body?.password || '');
    const user = store.getUserByEmail(email);
    const ok = await verifyPassword(password, user ? user.password_hash : DUMMY_HASH);
    if (!user || !ok) {
      return render(
        res,
        pages.loginPage(ctx(req, { error: 'Wrong email or password.', email, next: safeNext(req.body?.next) })),
        401,
      );
    }
    auth.startSession(res, user.id);
    res.redirect(303, safeNext(req.body?.next));
  });

  app.post('/logout', (req, res) => {
    auth.endSession(req, res);
    res.redirect(303, '/');
  });

  app.get('/forgot', (req, res) => render(res, pages.forgotPage(ctx(req, { sent: false }))));

  app.post('/forgot', forgotLimiter, async (req, res) => {
    const email = String(req.body?.email || '').trim().toLowerCase();
    const user = store.getUserByEmail(email);
    if (user) {
      const token = newToken();
      store.createPasswordReset(hashToken(token), user.id, Date.now() + RESET_TTL_MS);
      const link = `${config.baseUrl}/reset?token=${token}`;
      try {
        await mailer.send({
          to: user.email,
          subject: `Reset your ${config.appName} password`,
          text: `Someone asked to reset the password for your ${config.appName} account.\n\nChoose a new password here (link expires in 1 hour):\n${link}\n\nIf this wasn't you, you can ignore this email.`,
        });
      } catch (err) {
        console.error(`[forgot] Failed to send reset email: ${err.message}`);
      }
    }
    // Same response either way so nobody can probe which emails have accounts.
    render(res, pages.forgotPage(ctx(req, { sent: true })));
  });

  app.get('/reset', (req, res) =>
    render(res, pages.resetPage(ctx(req, { token: String(req.query.token || '') }))),
  );

  app.post('/reset', authLimiter, async (req, res) => {
    const token = String(req.body?.token || '');
    const password = req.body?.password;
    if (typeof password !== 'string' || password.length < 8 || password.length > 200) {
      return render(res, pages.resetPage(ctx(req, { token, error: 'Password must be 8 to 200 characters.' })), 400);
    }
    const userId = token ? store.consumePasswordReset(hashToken(token), Date.now()) : null;
    if (!userId) {
      return render(
        res,
        pages.resetPage(ctx(req, { token, error: 'This reset link is invalid or has expired. Request a new one.' })),
        400,
      );
    }
    store.setPassword(userId, await hashPassword(password));
    store.deleteUserSessions(userId);
    auth.startSession(res, userId);
    res.redirect(303, '/app');
  });

  // ---------- the product ----------
  app.get('/app', requireUser, (req, res) => {
    const purchased = Number.parseInt(req.query.purchased, 10) || null;
    const notice = CHECKOUT_ERRORS[req.query.error] || null;
    render(
      res,
      pages.appPage(ctx(req, { generatorMode: generator.mode, billing, purchased, notice })),
    );
  });

  const generateLimiter = rateLimit({
    windowMs: MINUTE,
    max: 10,
    key: (req) => `u${req.user.id}`,
    message: 'You are going fast! Wait a moment and try again.',
  });

  app.post('/api/generate', requireUser, generateLimiter, async (req, res) => {
    const { input, error } = parseGenerateInput(req.body ?? {});
    if (error) return res.status(400).json({ error });

    if (!store.reserveCredit(req.user.id)) {
      return res.status(402).json({ error: "You're out of credits. Grab a pack below to keep going.", outOfCredits: true });
    }

    try {
      const result = await generator.generate(input);
      const warnings = checkListing(input.platform, result.listing);
      const id = store.saveGeneration({
        userId: req.user.id,
        platform: input.platform,
        productName: input.productName,
        input,
        output: result.listing,
        model: result.model,
        inputTokens: result.inputTokens,
        outputTokens: result.outputTokens,
      });
      res.json({
        id,
        credits: store.getUserById(req.user.id).credits,
        listing: result.listing,
        warnings,
        html: listingCard({ platform: input.platform, listing: result.listing, warnings }).toString(),
      });
    } catch (err) {
      store.refundCredit(req.user.id, String(err.message).slice(0, 200));
      if (!(err instanceof GenerationError)) console.error('[generate]', err);
      res.status(err instanceof GenerationError ? err.status : 500).json({
        error: err.userMessage || 'Something went wrong. Your credit was refunded; please try again.',
        credits: store.getUserById(req.user.id).credits,
      });
    }
  });

  app.get('/app/history', requireUser, (req, res) =>
    render(res, pages.historyPage(ctx(req, { generations: store.listGenerations(req.user.id) }))),
  );

  app.get('/app/history.csv', requireUser, (req, res) => {
    const rows = store.allGenerations(req.user.id).map((g) => {
      const l = JSON.parse(g.output_json);
      return [g.id, g.created_at, g.platform, g.product_name, l.title, l.description, l.bullets.join('\n'), l.tags.join(', '), l.meta_description, l.seo_keywords.join(', ')];
    });
    const header = ['id', 'created_at', 'marketplace', 'product', 'title', 'description', 'highlights', 'tags', 'meta_description', 'keywords'];
    res
      .type('text/csv')
      .set('Content-Disposition', 'attachment; filename="listings.csv"')
      .send([header, ...rows].map((r) => r.map(csvCell).join(',')).join('\r\n'));
  });

  app.get('/app/listing/:id', requireUser, (req, res, next) => {
    const generation = store.getGeneration(req.user.id, Number(req.params.id));
    if (!generation) return next();
    const listing = JSON.parse(generation.output_json);
    render(
      res,
      pages.listingPage(ctx(req, { generation, listing, warnings: checkListing(generation.platform, listing) })),
    );
  });

  app.get('/app/account', requireUser, (req, res) =>
    render(res, pages.accountPage(ctx(req, { purchases: store.listPurchases(req.user.id) }))),
  );

  // ---------- billing ----------
  app.post('/billing/checkout', requireUser, async (req, res) => {
    try {
      const url = await billing.createCheckout(req.user, req.body?.pack);
      res.redirect(303, url);
    } catch (err) {
      console.error(`[checkout] ${err.message}`);
      res.redirect(303, `/app?error=${err.code || 'checkout_failed'}#buy`);
    }
  });

  app.get('/billing/success', requireUser, async (req, res) => {
    try {
      const credits = await billing.handleSuccessRedirect(req.user, req.query.session_id);
      res.redirect(303, credits ? `/app?purchased=${credits}` : '/app');
    } catch (err) {
      console.error(`[billing/success] ${err.message}`);
      res.redirect(303, '/app');
    }
  });

  // ---------- admin ----------
  const admin = requireAdmin(config);
  app.get('/admin', admin, (req, res) => {
    const message = typeof req.query.msg === 'string' ? req.query.msg.slice(0, 200) : null;
    render(res, pages.adminPage(ctx(req, { stats: store.stats(), message })));
  });

  app.post('/admin/grant', admin, (req, res) => {
    const email = String(req.body?.email || '').trim().toLowerCase();
    const credits = Number.parseInt(req.body?.credits, 10);
    const user = store.getUserByEmail(email);
    let msg;
    if (!user) msg = `No user with email ${email}.`;
    else if (!(credits > 0 && credits <= 10000)) msg = 'Credits must be between 1 and 10000.';
    else {
      store.grantCredits(user.id, credits, 'admin_grant', req.user.email);
      msg = `Granted ${credits} credits to ${email}.`;
    }
    res.redirect(303, `/admin?msg=${encodeURIComponent(msg)}`);
  });

  // ---------- fallthrough ----------
  app.use((req, res) => {
    if (req.path.startsWith('/api/')) return res.status(404).json({ error: 'Not found' });
    render(res, pages.notFoundPage(ctx(req)), 404);
  });

  app.use((err, req, res, _next) => {
    const status = err.status || err.statusCode || 500;
    if (status >= 500) console.error('[error]', err);
    if (req.path.startsWith('/api/')) return res.status(status).json({ error: 'Something went wrong.' });
    res.status(status).type('text/plain').send(status === 500 ? 'Something went wrong.' : err.message);
  });

  return app;
}

// Quotes a CSV cell and neutralizes spreadsheet formula injection.
function csvCell(value) {
  let s = value === null || value === undefined ? '' : String(value);
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  return `"${s.replace(/"/g, '""')}"`;
}
