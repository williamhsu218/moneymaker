import { loadConfig } from './config.js';
import { openDatabase } from './db.js';
import { createGenerator } from './generator.js';
import { createBilling } from './billing.js';
import { createMailer } from './mailer.js';
import { createApp } from './app.js';

const config = loadConfig();
const store = openDatabase(config.databasePath);
const generator = createGenerator(config);
const billing = createBilling({ store, config });
const mailer = createMailer(config);
const app = createApp({ config, store, generator, billing, mailer });

// Hourly cleanup of expired sessions and reset tokens.
setInterval(() => store.purgeExpired(Date.now()), 60 * 60 * 1000).unref();

const server = app.listen(config.port, () => {
  console.log(`${config.appName} running at ${config.baseUrl} (port ${config.port})`);
  console.log(`  AI:       ${generator.mode === 'demo' ? 'DEMO MODE (set ANTHROPIC_API_KEY)' : `${config.claudeModel}, effort ${config.claudeEffort}`}`);
  console.log(`  Payments: ${billing.enabled ? 'Stripe' : billing.devFakePayments ? 'FAKE (DEV_FAKE_PAYMENTS)' : 'not configured (set STRIPE_SECRET_KEY)'}`);
  if (billing.enabled && !config.stripeWebhookSecret) {
    console.log('  Warning:  STRIPE_WEBHOOK_SECRET is not set; purchases are credited only via the success redirect.');
  }
  console.log(`  Email:    ${mailer.enabled ? 'Resend' : 'console log (set RESEND_API_KEY and EMAIL_FROM)'}`);
});

function shutdown() {
  server.close(() => {
    store.close();
    process.exit(0);
  });
  setTimeout(() => process.exit(0), 10_000).unref();
}
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
