import Stripe from 'stripe';
import { loadConfig } from '../src/config.js';
import { openDatabase } from '../src/db.js';
import { createDemoGenerator } from '../src/generator.js';
import { createBilling } from '../src/billing.js';
import { createApp } from '../src/app.js';

export const WEBHOOK_SECRET = 'whsec_test_secret';

// Boots a fully wired app on a random port with an in-memory database.
export async function startTestApp({ generator, config: overrides = {}, withStripe = false } = {}) {
  const config = loadConfig({
    databasePath: ':memory:',
    anthropicApiKey: '',
    stripeSecretKey: withStripe ? 'sk_test_dummy' : '',
    stripeWebhookSecret: withStripe ? WEBHOOK_SECRET : '',
    devFakePayments: false,
    freeCredits: 3,
    adminEmails: ['admin@example.com'],
    isProduction: false,
    ...overrides,
  });
  const store = openDatabase(':memory:');
  const stripe = withStripe ? new Stripe('sk_test_dummy') : undefined;
  const billing = createBilling({ store, config, stripe });
  const sent = [];
  const mailer = { enabled: true, send: async (msg) => sent.push(msg) };
  const app = createApp({ config, store, generator: generator || createDemoGenerator(), billing, mailer });

  const server = await new Promise((resolve) => {
    const s = app.listen(0, () => resolve(s));
  });
  const baseUrl = `http://127.0.0.1:${server.address().port}`;
  config.baseUrl = baseUrl;

  return {
    baseUrl,
    store,
    stripe,
    sent,
    client: () => createClient(baseUrl),
    close: () => new Promise((resolve) => server.close(() => { store.close(); resolve(); })),
  };
}

// Minimal browser-like client: keeps cookies and sends a same-site Origin.
function createClient(baseUrl) {
  const jar = new Map();
  async function request(path, { method = 'GET', form, json, headers = {}, origin = baseUrl, body } = {}) {
    const h = { ...headers };
    if (origin) h.Origin = origin;
    if (jar.size) h.Cookie = [...jar].map(([k, v]) => `${k}=${v}`).join('; ');
    if (form) {
      h['Content-Type'] = 'application/x-www-form-urlencoded';
      body = new URLSearchParams(form).toString();
    } else if (json) {
      h['Content-Type'] = 'application/json';
      body = JSON.stringify(json);
    }
    const res = await fetch(baseUrl + path, { method, headers: h, body, redirect: 'manual' });
    for (const c of res.headers.getSetCookie()) {
      const [pair, ...attrs] = c.split(';');
      const [k, v] = pair.split('=');
      if (attrs.some((a) => a.trim() === 'Max-Age=0')) jar.delete(k);
      else jar.set(k, v);
    }
    return res;
  }
  return {
    request,
    get: (path, opts) => request(path, opts),
    post: (path, opts) => request(path, { ...opts, method: 'POST' }),
    async signup(email = `user${Math.random().toString(36).slice(2)}@example.com`, password = 'password123') {
      const res = await request('/signup', { method: 'POST', form: { email, password } });
      if (res.status !== 303) throw new Error(`signup failed: ${res.status}`);
      return email;
    },
  };
}

export const validInput = {
  platform: 'etsy',
  productName: 'Handmade ceramic mug',
  details: 'Speckled white glaze, 12 oz, dishwasher safe, made in my studio.',
  tone: 'friendly',
  language: 'en',
};
