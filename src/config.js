// Central place for every environment variable the app reads.
// Loads .env automatically when present (Node 22 built-in, no dotenv needed).

try {
  process.loadEnvFile();
} catch {
  // No .env file: fine, rely on the real environment.
}

const env = process.env;

function bool(value, fallback = false) {
  if (value === undefined || value === '') return fallback;
  return ['1', 'true', 'yes', 'on'].includes(String(value).toLowerCase());
}

function int(value, fallback) {
  const n = Number.parseInt(value, 10);
  return Number.isFinite(n) ? n : fallback;
}

export function loadConfig(overrides = {}) {
  const port = int(env.PORT, 3000);
  const config = {
    appName: env.APP_NAME || 'ListingSpark',
    baseUrl: (env.BASE_URL || `http://localhost:${port}`).replace(/\/$/, ''),
    port,
    isProduction: env.NODE_ENV === 'production',
    databasePath: env.DATABASE_PATH || './data/app.db',
    trustProxy: bool(env.TRUST_PROXY, false),
    supportEmail: env.SUPPORT_EMAIL || 'support@example.com',
    adminEmails: (env.ADMIN_EMAILS || '')
      .split(',')
      .map((e) => e.trim().toLowerCase())
      .filter(Boolean),

    freeCredits: int(env.FREE_CREDITS, 5),

    anthropicApiKey: env.ANTHROPIC_API_KEY || '',
    claudeModel: env.CLAUDE_MODEL || 'claude-opus-5',
    claudeEffort: env.CLAUDE_EFFORT || 'low',

    stripeSecretKey: env.STRIPE_SECRET_KEY || '',
    stripeWebhookSecret: env.STRIPE_WEBHOOK_SECRET || '',
    currency: (env.CURRENCY || 'usd').toLowerCase(),
    // Lets you click through the purchase flow locally without Stripe.
    // Never enable this in production.
    devFakePayments: bool(env.DEV_FAKE_PAYMENTS, false),

    resendApiKey: env.RESEND_API_KEY || '',
    emailFrom: env.EMAIL_FROM || '',

    ...overrides,
  };

  if (config.isProduction && config.devFakePayments) {
    throw new Error('DEV_FAKE_PAYMENTS must not be enabled when NODE_ENV=production');
  }
  return config;
}
