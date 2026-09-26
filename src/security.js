// Small, dependency-free security middleware.

export function securityHeaders(config) {
  const csp = [
    "default-src 'self'",
    "img-src 'self' data:",
    "style-src 'self'",
    "script-src 'self'",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    // Checkout redirects to Stripe after a form post.
    "form-action 'self' https://checkout.stripe.com",
  ].join('; ');

  return (_req, res, next) => {
    res.set({
      'Content-Security-Policy': csp,
      'X-Content-Type-Options': 'nosniff',
      'X-Frame-Options': 'DENY',
      'Referrer-Policy': 'strict-origin-when-cross-origin',
      'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
    });
    if (config.isProduction) {
      res.set('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
    }
    next();
  };
}

// CSRF defense: state-changing requests must come from our own pages.
// Works alongside SameSite=Lax session cookies.
export function sameOriginOnly(config, { exempt = [] } = {}) {
  const allowed = new Set([new URL(config.baseUrl).origin]);
  return (req, res, next) => {
    if (['GET', 'HEAD', 'OPTIONS'].includes(req.method)) return next();
    if (exempt.some((p) => req.path.startsWith(p))) return next();

    const origin = req.get('origin') || originOf(req.get('referer'));
    const selfOrigin = `${req.protocol}://${req.get('host')}`;
    if (origin && (allowed.has(origin) || origin === selfOrigin)) return next();
    return res.status(403).send('Cross-site request blocked.');
  };
}

function originOf(url) {
  try {
    return url ? new URL(url).origin : null;
  } catch {
    return null;
  }
}

// Fixed-window in-memory limiter. Good enough for a single instance; swap for
// Redis if you ever run several.
export function rateLimit({ windowMs, max, key = (req) => req.ip, message = 'Too many requests. Please slow down.' }) {
  const hits = new Map();
  const timer = setInterval(() => {
    const now = Date.now();
    for (const [k, v] of hits) if (v.resetAt <= now) hits.delete(k);
  }, windowMs);
  timer.unref();

  return (req, res, next) => {
    const k = key(req);
    const now = Date.now();
    let entry = hits.get(k);
    if (!entry || entry.resetAt <= now) {
      entry = { count: 0, resetAt: now + windowMs };
      hits.set(k, entry);
    }
    entry.count++;
    if (entry.count > max) {
      res.set('Retry-After', String(Math.ceil((entry.resetAt - now) / 1000)));
      if (req.path.startsWith('/api/')) return res.status(429).json({ error: message });
      return res.status(429).send(message);
    }
    next();
  };
}
