import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startTestApp, validInput, WEBHOOK_SECRET } from './helpers.js';
import { GenerationError } from '../src/generator.js';

describe('public pages', () => {
  let t;
  before(async () => (t = await startTestApp()));
  after(() => t.close());

  test('landing page renders with pricing and security headers', async () => {
    const res = await t.client().get('/');
    assert.equal(res.status, 200);
    const body = await res.text();
    assert.match(body, /Simple pricing/);
    assert.match(body, /\$39</);
    assert.match(res.headers.get('content-security-policy'), /default-src 'self'/);
    assert.equal(res.headers.get('x-frame-options'), 'DENY');
  });

  test('app redirects anonymous visitors to login', async () => {
    const res = await t.client().get('/app');
    assert.equal(res.status, 303);
    assert.equal(res.headers.get('location'), '/login?next=%2Fapp');
  });

  test('robots, sitemap, legal pages and 404', async () => {
    const c = t.client();
    assert.equal((await c.get('/robots.txt')).status, 200);
    assert.match(await (await c.get('/sitemap.xml')).text(), /<urlset/);
    assert.equal((await c.get('/terms')).status, 200);
    assert.equal((await c.get('/privacy')).status, 200);
    assert.equal((await c.get('/nope')).status, 404);
  });
});

describe('accounts', () => {
  let t;
  before(async () => (t = await startTestApp()));
  after(() => t.close());

  test('signup grants free credits and logs in', async () => {
    const c = t.client();
    const email = await c.signup('New@Example.com');
    assert.equal(email, 'New@Example.com');
    const user = t.store.getUserByEmail('new@example.com');
    assert.equal(user.credits, 3);
    const app = await c.get('/app');
    assert.equal(app.status, 200);
    assert.match(await app.text(), /data-credits>3</);
  });

  test('rejects duplicate emails and weak passwords', async () => {
    const c = t.client();
    await c.signup('dup@example.com');
    const dup = await t.client().post('/signup', { form: { email: 'DUP@example.com', password: 'password123' } });
    assert.equal(dup.status, 409);
    const weak = await t.client().post('/signup', { form: { email: 'weak@example.com', password: 'short' } });
    assert.equal(weak.status, 400);
  });

  test('login checks the password and logout ends the session', async () => {
    await t.client().signup('login@example.com', 'correct-horse');
    const c = t.client();
    const bad = await c.post('/login', { form: { email: 'login@example.com', password: 'wrong-pass' } });
    assert.equal(bad.status, 401);
    const good = await c.post('/login', { form: { email: 'LOGIN@example.com', password: 'correct-horse', next: '/app/history' } });
    assert.equal(good.status, 303);
    assert.equal(good.headers.get('location'), '/app/history');
    assert.equal((await c.get('/app')).status, 200);
    await c.post('/logout');
    assert.equal((await c.get('/app')).status, 303);
  });

  test('login refuses off-site redirects', async () => {
    await t.client().signup('redir@example.com', 'password123');
    const res = await t.client().post('/login', {
      form: { email: 'redir@example.com', password: 'password123', next: '//evil.com' },
    });
    assert.equal(res.headers.get('location'), '/app');
  });

  test('password reset works once and signs out old sessions', async () => {
    const old = t.client();
    await old.signup('reset@example.com', 'old-password');
    const c = t.client();
    const res = await c.post('/forgot', { form: { email: 'reset@example.com' } });
    assert.equal(res.status, 200);
    const mail = t.sent.find((m) => m.to === 'reset@example.com');
    const token = mail.text.match(/token=([\w-]+)/)[1];

    const reset = await c.post('/reset', { form: { token, password: 'new-password' } });
    assert.equal(reset.status, 303);
    assert.equal((await old.get('/app')).status, 303, 'old session revoked');

    const again = await t.client().post('/reset', { form: { token, password: 'another-one' } });
    assert.equal(again.status, 400, 'token is single-use');

    const login = await t.client().post('/login', { form: { email: 'reset@example.com', password: 'new-password' } });
    assert.equal(login.status, 303);
  });

  test('forgot password does not reveal whether an email exists', async () => {
    const res = await t.client().post('/forgot', { form: { email: 'nobody@example.com' } });
    assert.equal(res.status, 200);
    assert.match(await res.text(), /If that email has an account/);
  });
});

describe('generating listings', () => {
  let t;
  let failNext = false;
  const generator = {
    mode: 'test',
    async generate(input) {
      if (failNext) {
        failNext = false;
        throw new GenerationError('Provider down, credit refunded.', { status: 503 });
      }
      return {
        listing: {
          title: `${input.productName} title`,
          description: 'A description.',
          bullets: ['One', 'Two', 'Three', 'Four', 'Five'],
          tags: ['=cmd|calc', 'this tag is definitely too long', 'ok tag'],
          meta_description: 'Meta.',
          seo_keywords: ['mug'],
          seller_tips: [],
        },
        model: 'claude-opus-5',
        inputTokens: 1000,
        outputTokens: 800,
      };
    },
  };
  before(async () => (t = await startTestApp({ generator })));
  after(() => t.close());

  test('spends one credit per listing and stops at zero', async () => {
    const c = t.client();
    const email = await c.signup();
    for (const expected of [2, 1, 0]) {
      const res = await c.post('/api/generate', { json: validInput });
      assert.equal(res.status, 200);
      const data = await res.json();
      assert.equal(data.credits, expected);
      assert.match(data.html, /Handmade ceramic mug title/);
    }
    const broke = await c.post('/api/generate', { json: validInput });
    assert.equal(broke.status, 402);
    assert.equal((await broke.json()).outOfCredits, true);
    assert.equal(t.store.getUserByEmail(email).credits, 0);
  });

  test('flags tags over the marketplace limit', async () => {
    const c = t.client();
    await c.signup();
    const data = await (await c.post('/api/generate', { json: validInput })).json();
    assert.ok(data.warnings.some((w) => w.includes('over 20 characters')));
  });

  test('refunds the credit when generation fails', async () => {
    const c = t.client();
    const email = await c.signup();
    failNext = true;
    const res = await c.post('/api/generate', { json: validInput });
    assert.equal(res.status, 503);
    const data = await res.json();
    assert.equal(data.error, 'Provider down, credit refunded.');
    assert.equal(data.credits, 3);
    assert.equal(t.store.getUserByEmail(email).credits, 3);
  });

  test('validates input without charging', async () => {
    const c = t.client();
    const email = await c.signup();
    const res = await c.post('/api/generate', { json: { ...validInput, platform: 'myspace' } });
    assert.equal(res.status, 400);
    const res2 = await c.post('/api/generate', { json: { ...validInput, details: 'x'.repeat(5000) } });
    assert.equal(res2.status, 400);
    assert.equal(t.store.getUserByEmail(email).credits, 3);
  });

  test('blocks cross-site requests', async () => {
    const c = t.client();
    await c.signup();
    const res = await c.post('/api/generate', { json: validInput, origin: 'https://evil.example' });
    assert.equal(res.status, 403);
    const noOrigin = await c.post('/api/generate', { json: validInput, origin: null });
    assert.equal(noOrigin.status, 403);
  });

  test('history, listing pages and CSV export are private to the owner', async () => {
    const owner = t.client();
    await owner.signup();
    const { id } = await (await owner.post('/api/generate', { json: validInput })).json();

    assert.match(await (await owner.get('/app/history')).text(), new RegExp(`/app/listing/${id}`));
    assert.equal((await owner.get(`/app/listing/${id}`)).status, 200);

    const csv = await (await owner.get('/app/history.csv')).text();
    assert.match(csv, /"'=cmd\|calc/, 'formula injection is neutralized');

    const stranger = t.client();
    await stranger.signup();
    assert.equal((await stranger.get(`/app/listing/${id}`)).status, 404);
  });
});

describe('payments', () => {
  let t;
  before(async () => (t = await startTestApp({ withStripe: true })));
  after(() => t.close());

  function signedEvent(session, type = 'checkout.session.completed') {
    const payload = JSON.stringify({ id: `evt_${Math.random()}`, object: 'event', type, data: { object: session } });
    const signature = t.stripe.webhooks.generateTestHeaderString({ payload, secret: WEBHOOK_SECRET });
    return { payload, signature };
  }

  test('webhook credits a paid checkout exactly once', async () => {
    const c = t.client();
    const email = await c.signup();
    const user = t.store.getUserByEmail(email);
    const session = {
      id: 'cs_test_123',
      object: 'checkout.session',
      payment_status: 'paid',
      client_reference_id: String(user.id),
      metadata: { pack: 'growth', user_id: String(user.id) },
      amount_total: 3900,
      currency: 'usd',
    };
    const { payload, signature } = signedEvent(session);
    for (let i = 0; i < 2; i++) {
      const res = await fetch(`${t.baseUrl}/webhooks/stripe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Stripe-Signature': signature },
        body: payload,
      });
      assert.equal(res.status, 200);
    }
    assert.equal(t.store.getUserByEmail(email).credits, 3 + 200);
    assert.equal(t.store.listPurchases(user.id).length, 1);
    assert.equal(t.store.stats().revenueCents, 3900);
  });

  test('webhook ignores unpaid sessions', async () => {
    const c = t.client();
    const email = await c.signup();
    const user = t.store.getUserByEmail(email);
    const { payload, signature } = signedEvent({
      id: 'cs_test_unpaid',
      payment_status: 'unpaid',
      client_reference_id: String(user.id),
      metadata: { pack: 'pro' },
    });
    const res = await fetch(`${t.baseUrl}/webhooks/stripe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Stripe-Signature': signature },
      body: payload,
    });
    assert.equal(res.status, 200);
    assert.equal(t.store.getUserByEmail(email).credits, 3);
  });

  test('webhook rejects bad signatures', async () => {
    const res = await fetch(`${t.baseUrl}/webhooks/stripe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Stripe-Signature': 't=1,v1=deadbeef' },
      body: JSON.stringify({ type: 'checkout.session.completed' }),
    });
    assert.equal(res.status, 400);
  });

  test('unknown packs are rejected before reaching Stripe', async () => {
    const c = t.client();
    await c.signup();
    const res = await c.post('/billing/checkout', { form: { pack: 'free-money' } });
    assert.equal(res.status, 303);
    assert.equal(res.headers.get('location'), '/app?error=unknown_pack#buy');
    const page = await c.get('/app?error=unknown_pack');
    assert.match(await page.text(), /That credit pack does not exist/);
    const crafted = await c.get('/app?error=Send%20your%20password%20to%20evil');
    assert.doesNotMatch(await crafted.text(), /Send your password/);
  });
});

describe('payments not configured', () => {
  let t;
  before(async () => (t = await startTestApp()));
  after(() => t.close());

  test('checkout explains that payments are off', async () => {
    const c = t.client();
    await c.signup();
    const res = await c.post('/billing/checkout', { form: { pack: 'starter' } });
    assert.equal(res.headers.get('location'), '/app?error=payments_off#buy');
  });
});

describe('fake payments for local testing', () => {
  let t;
  before(async () => (t = await startTestApp({ config: { devFakePayments: true } })));
  after(() => t.close());

  test('adds credits without Stripe', async () => {
    const c = t.client();
    const email = await c.signup();
    const res = await c.post('/billing/checkout', { form: { pack: 'starter' } });
    assert.equal(res.headers.get('location'), '/app?purchased=50');
    assert.equal(t.store.getUserByEmail(email).credits, 53);
  });
});

describe('admin', () => {
  let t;
  before(async () => (t = await startTestApp()));
  after(() => t.close());

  test('is hidden from regular users and lets admins grant credits', async () => {
    const user = t.client();
    await user.signup('customer@example.com');
    assert.equal((await user.get('/admin')).status, 404);
    assert.equal((await user.post('/admin/grant', { form: { email: 'customer@example.com', credits: '100' } })).status, 404);

    const admin = t.client();
    await admin.signup('admin@example.com');
    assert.equal((await admin.get('/admin')).status, 200);
    const res = await admin.post('/admin/grant', { form: { email: 'customer@example.com', credits: '25' } });
    assert.equal(res.status, 303);
    assert.equal(t.store.getUserByEmail('customer@example.com').credits, 28);
  });
});
