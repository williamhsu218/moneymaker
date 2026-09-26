import Stripe from 'stripe';

// One-time credit packs. Credits never expire, which converts better than a
// subscription for sellers with bursty listing needs. Prices are in cents.
export const PACKS = {
  starter: { name: 'Starter', credits: 50, priceCents: 1200, blurb: 'Try it on a batch of products' },
  growth: { name: 'Growth', credits: 200, priceCents: 3900, blurb: 'For active shops', popular: true },
  pro: { name: 'Pro', credits: 600, priceCents: 9900, blurb: 'For big catalogs and agencies' },
};

export function formatMoney(cents, currency = 'usd') {
  const whole = cents % 100 === 0;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency.toUpperCase(),
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: whole ? 0 : 2,
  }).format(cents / 100);
}

// Messages the app page may show after a failed checkout, keyed by the code in
// the redirect URL (so a crafted link can't put arbitrary text on the page).
export const CHECKOUT_ERRORS = {
  payments_off: 'Payments are not configured yet.',
  unknown_pack: 'That credit pack does not exist.',
  checkout_failed: 'Could not start checkout. Please try again.',
};

export function createBilling({ store, config, stripe }) {
  const client =
    stripe || (config.stripeSecretKey ? new Stripe(config.stripeSecretKey) : null);
  const enabled = Boolean(client);

  // Credits a paid Checkout Session to its user. Safe to call repeatedly.
  function fulfill(session) {
    if (session.payment_status !== 'paid') return false;
    const userId = Number(session.client_reference_id || session.metadata?.user_id);
    const pack = PACKS[session.metadata?.pack];
    if (!userId || !pack || !store.getUserById(userId)) {
      console.error(`[billing] Cannot fulfill session ${session.id}: bad metadata`);
      return false;
    }
    const added = store.fulfillPurchase({
      userId,
      stripeSessionId: session.id,
      pack: session.metadata.pack,
      credits: pack.credits,
      amountCents: session.amount_total ?? pack.priceCents,
      currency: session.currency || config.currency,
    });
    if (added) console.log(`[billing] +${pack.credits} credits for user ${userId} (${session.id})`);
    return added;
  }

  return {
    enabled,
    devFakePayments: config.devFakePayments && !enabled,

    async createCheckout(user, packId) {
      const pack = PACKS[packId];
      if (!pack) throw Object.assign(new Error('Unknown pack'), { code: 'unknown_pack' });

      if (!enabled) {
        if (!config.devFakePayments) {
          throw Object.assign(new Error('Payments are not configured'), { code: 'payments_off' });
        }
        // Local testing only: pretend Stripe charged the card.
        const fakeId = `dev_${Date.now()}_${Math.random().toString(36).slice(2)}`;
        fulfill({
          id: fakeId,
          payment_status: 'paid',
          client_reference_id: String(user.id),
          metadata: { pack: packId, user_id: String(user.id) },
          amount_total: pack.priceCents,
          currency: config.currency,
        });
        return `/app?purchased=${pack.credits}`;
      }

      const session = await client.checkout.sessions.create({
        mode: 'payment',
        line_items: [
          {
            quantity: 1,
            price_data: {
              currency: config.currency,
              unit_amount: pack.priceCents,
              product_data: {
                name: `${config.appName} ${pack.name} – ${pack.credits} listings`,
                description: 'AI-written product listings. Credits never expire.',
              },
            },
          },
        ],
        customer_email: user.email,
        client_reference_id: String(user.id),
        metadata: { pack: packId, user_id: String(user.id) },
        allow_promotion_codes: true,
        success_url: `${config.baseUrl}/billing/success?session_id={CHECKOUT_SESSION_ID}`,
        cancel_url: `${config.baseUrl}/app#buy`,
      });
      return session.url;
    },

    // Called when Stripe redirects the buyer back. Fulfills immediately so the
    // credits show up even if the webhook is slow or misconfigured.
    async handleSuccessRedirect(user, sessionId) {
      if (!enabled || typeof sessionId !== 'string' || !sessionId.startsWith('cs_')) return null;
      const session = await client.checkout.sessions.retrieve(sessionId);
      if (String(session.client_reference_id) !== String(user.id)) return null;
      // Delayed payment methods (e.g. bank debits) arrive later via webhook.
      if (session.payment_status !== 'paid') return null;
      fulfill(session);
      return PACKS[session.metadata?.pack]?.credits ?? null;
    },

    handleWebhook(rawBody, signature) {
      if (!enabled || !config.stripeWebhookSecret) {
        throw Object.assign(new Error('Webhook not configured'), { status: 503 });
      }
      let event;
      try {
        event = client.webhooks.constructEvent(rawBody, signature, config.stripeWebhookSecret);
      } catch (err) {
        throw Object.assign(new Error(`Invalid signature: ${err.message}`), { status: 400 });
      }
      if (
        event.type === 'checkout.session.completed' ||
        event.type === 'checkout.session.async_payment_succeeded'
      ) {
        fulfill(event.data.object);
      }
      return event.type;
    },
  };
}
