import crypto from 'node:crypto';
import { promisify } from 'node:util';

const scrypt = promisify(crypto.scrypt);

const SESSION_COOKIE = 'sid';
const SESSION_TTL_MS = 30 * 24 * 60 * 60 * 1000;
export const RESET_TTL_MS = 60 * 60 * 1000;

export async function hashPassword(password) {
  const salt = crypto.randomBytes(16);
  const key = await scrypt(password, salt, 64);
  return `scrypt$${salt.toString('hex')}$${key.toString('hex')}`;
}

export async function verifyPassword(password, stored) {
  const [scheme, saltHex, keyHex] = String(stored).split('$');
  if (scheme !== 'scrypt' || !saltHex || !keyHex) return false;
  const expected = Buffer.from(keyHex, 'hex');
  const actual = await scrypt(password, Buffer.from(saltHex, 'hex'), expected.length);
  return crypto.timingSafeEqual(expected, actual);
}

export const newToken = () => crypto.randomBytes(32).toString('base64url');
export const hashToken = (token) => crypto.createHash('sha256').update(token).digest('hex');

export function validateCredentials(email, password) {
  if (typeof email !== 'string' || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 254) {
    return 'Enter a valid email address.';
  }
  if (typeof password !== 'string' || password.length < 8) {
    return 'Password must be at least 8 characters.';
  }
  if (password.length > 200) return 'Password is too long.';
  return null;
}

export function parseCookies(header = '') {
  const out = {};
  for (const part of header.split(';')) {
    const i = part.indexOf('=');
    if (i < 0) continue;
    const key = part.slice(0, i).trim();
    if (!key) continue;
    try {
      out[key] = decodeURIComponent(part.slice(i + 1).trim());
    } catch {
      // Ignore malformed cookie values.
    }
  }
  return out;
}

export function createAuth({ store, config }) {
  const cookieBase = `Path=/; HttpOnly; SameSite=Lax${config.isProduction ? '; Secure' : ''}`;

  return {
    startSession(res, userId) {
      const token = newToken();
      store.createSession(hashToken(token), userId, Date.now() + SESSION_TTL_MS);
      res.append(
        'Set-Cookie',
        `${SESSION_COOKIE}=${token}; ${cookieBase}; Max-Age=${SESSION_TTL_MS / 1000}`,
      );
    },

    endSession(req, res) {
      const token = parseCookies(req.headers.cookie)[SESSION_COOKIE];
      if (token) store.deleteSession(hashToken(token));
      res.append('Set-Cookie', `${SESSION_COOKIE}=; ${cookieBase}; Max-Age=0`);
    },

    // Attaches req.user (or null) on every request.
    loadUser(req, _res, next) {
      const token = parseCookies(req.headers.cookie)[SESSION_COOKIE];
      req.user = token ? store.getSessionUser(hashToken(token), Date.now()) || null : null;
      next();
    },
  };
}

export function requireUser(req, res, next) {
  if (req.user) return next();
  if (req.path.startsWith('/api/')) return res.status(401).json({ error: 'Please log in.' });
  return res.redirect(303, `/login?next=${encodeURIComponent(req.originalUrl)}`);
}

export function requireAdmin(config) {
  return (req, res, next) => {
    if (req.user && config.adminEmails.includes(req.user.email.toLowerCase())) return next();
    return res.status(404).send('Not found');
  };
}

// Only allow redirects back into this site after login.
export function safeNext(value) {
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//')
    ? value
    : '/app';
}
