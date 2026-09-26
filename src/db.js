import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import path from 'node:path';

// Each entry runs once, in order. Append new migrations; never edit old ones.
const MIGRATIONS = [
  `
  CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    credits INTEGER NOT NULL DEFAULT 0 CHECK (credits >= 0),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );

  CREATE TABLE sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL
  );
  CREATE INDEX sessions_user ON sessions(user_id);

  CREATE TABLE password_resets (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL,
    used INTEGER NOT NULL DEFAULT 0
  );

  CREATE TABLE generations (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    product_name TEXT NOT NULL,
    input_json TEXT NOT NULL,
    output_json TEXT NOT NULL,
    model TEXT,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );
  CREATE INDEX generations_user ON generations(user_id, id DESC);

  CREATE TABLE purchases (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stripe_session_id TEXT NOT NULL UNIQUE,
    pack TEXT NOT NULL,
    credits INTEGER NOT NULL,
    amount_cents INTEGER NOT NULL,
    currency TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );
  CREATE INDEX purchases_user ON purchases(user_id);

  -- Audit trail of every credit change, for support questions and refunds.
  CREATE TABLE credit_events (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    delta INTEGER NOT NULL,
    reason TEXT NOT NULL,
    ref TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );
  CREATE INDEX credit_events_user ON credit_events(user_id);
  `,
];

export function openDatabase(file) {
  if (file !== ':memory:') {
    fs.mkdirSync(path.dirname(path.resolve(file)), { recursive: true });
  }
  const db = new DatabaseSync(file);
  db.exec('PRAGMA journal_mode = WAL');
  db.exec('PRAGMA foreign_keys = ON');
  db.exec('PRAGMA busy_timeout = 5000');

  const { user_version: version } = db.prepare('PRAGMA user_version').get();
  for (let i = version; i < MIGRATIONS.length; i++) {
    transaction(db, () => {
      db.exec(MIGRATIONS[i]);
      db.exec(`PRAGMA user_version = ${i + 1}`);
    });
  }
  return createStore(db);
}

function transaction(db, fn) {
  db.exec('BEGIN IMMEDIATE');
  try {
    const result = fn();
    db.exec('COMMIT');
    return result;
  } catch (err) {
    db.exec('ROLLBACK');
    throw err;
  }
}

// All SQL lives here so the rest of the app deals in plain functions.
function createStore(db) {
  const q = (sql) => db.prepare(sql);
  const tx = (fn) => transaction(db, fn);

  const addCreditEvent = (userId, delta, reason, ref = null) =>
    q('INSERT INTO credit_events (user_id, delta, reason, ref) VALUES (?, ?, ?, ?)').run(
      userId,
      delta,
      reason,
      ref,
    );

  return {
    raw: db,
    close: () => db.close(),

    // --- users ---
    createUser(email, passwordHash, freeCredits) {
      return tx(() => {
        const { lastInsertRowid } = q(
          'INSERT INTO users (email, password_hash, credits) VALUES (?, ?, ?)',
        ).run(email, passwordHash, freeCredits);
        const id = Number(lastInsertRowid);
        if (freeCredits > 0) addCreditEvent(id, freeCredits, 'signup_bonus');
        return id;
      });
    },
    getUserByEmail: (email) => q('SELECT * FROM users WHERE email = ?').get(email),
    getUserById: (id) => q('SELECT * FROM users WHERE id = ?').get(id),
    setPassword: (userId, passwordHash) =>
      q('UPDATE users SET password_hash = ? WHERE id = ?').run(passwordHash, userId),

    // --- sessions ---
    createSession: (tokenHash, userId, expiresAt) =>
      q('INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)').run(
        tokenHash,
        userId,
        expiresAt,
      ),
    getSessionUser(tokenHash, now) {
      return q(
        `SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id
         WHERE sessions.token_hash = ? AND sessions.expires_at > ?`,
      ).get(tokenHash, now);
    },
    deleteSession: (tokenHash) => q('DELETE FROM sessions WHERE token_hash = ?').run(tokenHash),
    deleteUserSessions: (userId) => q('DELETE FROM sessions WHERE user_id = ?').run(userId),
    purgeExpired(now) {
      q('DELETE FROM sessions WHERE expires_at <= ?').run(now);
      q('DELETE FROM password_resets WHERE expires_at <= ? OR used = 1').run(now);
    },

    // --- password resets ---
    createPasswordReset: (tokenHash, userId, expiresAt) =>
      q('INSERT INTO password_resets (token_hash, user_id, expires_at) VALUES (?, ?, ?)').run(
        tokenHash,
        userId,
        expiresAt,
      ),
    // Marks the token used and returns its user id, or null if invalid/expired.
    consumePasswordReset(tokenHash, now) {
      return tx(() => {
        const row = q(
          'SELECT user_id FROM password_resets WHERE token_hash = ? AND used = 0 AND expires_at > ?',
        ).get(tokenHash, now);
        if (!row) return null;
        q('UPDATE password_resets SET used = 1 WHERE token_hash = ?').run(tokenHash);
        return row.user_id;
      });
    },

    // --- credits ---
    // Atomically takes one credit. Returns false when the balance is empty.
    reserveCredit(userId) {
      return tx(() => {
        const { changes } = q(
          'UPDATE users SET credits = credits - 1 WHERE id = ? AND credits >= 1',
        ).run(userId);
        if (changes !== 1) return false;
        addCreditEvent(userId, -1, 'generation');
        return true;
      });
    },
    refundCredit(userId, why) {
      tx(() => {
        q('UPDATE users SET credits = credits + 1 WHERE id = ?').run(userId);
        addCreditEvent(userId, 1, 'refund', why);
      });
    },
    grantCredits(userId, amount, reason, ref = null) {
      tx(() => {
        q('UPDATE users SET credits = credits + ? WHERE id = ?').run(amount, userId);
        addCreditEvent(userId, amount, reason, ref);
      });
    },

    // Idempotent: a Stripe session id is only ever fulfilled once, no matter
    // how many times the webhook or the success redirect reports it.
    fulfillPurchase({ userId, stripeSessionId, pack, credits, amountCents, currency }) {
      return tx(() => {
        const existing = q('SELECT id FROM purchases WHERE stripe_session_id = ?').get(
          stripeSessionId,
        );
        if (existing) return false;
        q(
          `INSERT INTO purchases (user_id, stripe_session_id, pack, credits, amount_cents, currency)
           VALUES (?, ?, ?, ?, ?, ?)`,
        ).run(userId, stripeSessionId, pack, credits, amountCents, currency);
        q('UPDATE users SET credits = credits + ? WHERE id = ?').run(credits, userId);
        addCreditEvent(userId, credits, 'purchase', stripeSessionId);
        return true;
      });
    },
    listPurchases: (userId) =>
      q('SELECT * FROM purchases WHERE user_id = ? ORDER BY id DESC').all(userId),

    // --- generations ---
    saveGeneration(g) {
      const { lastInsertRowid } = q(
        `INSERT INTO generations
          (user_id, platform, product_name, input_json, output_json, model, input_tokens, output_tokens)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      ).run(
        g.userId,
        g.platform,
        g.productName,
        JSON.stringify(g.input),
        JSON.stringify(g.output),
        g.model,
        g.inputTokens,
        g.outputTokens,
      );
      return Number(lastInsertRowid);
    },
    listGenerations: (userId, limit = 100) =>
      q(
        `SELECT id, platform, product_name, created_at FROM generations
         WHERE user_id = ? ORDER BY id DESC LIMIT ?`,
      ).all(userId, limit),
    allGenerations: (userId) =>
      q('SELECT * FROM generations WHERE user_id = ? ORDER BY id DESC').all(userId),
    getGeneration: (userId, id) =>
      q('SELECT * FROM generations WHERE user_id = ? AND id = ?').get(userId, id),

    // --- admin ---
    stats() {
      return {
        users: q('SELECT COUNT(*) AS n FROM users').get().n,
        payingUsers: q('SELECT COUNT(DISTINCT user_id) AS n FROM purchases').get().n,
        revenueCents: q('SELECT COALESCE(SUM(amount_cents), 0) AS n FROM purchases').get().n,
        generations: q('SELECT COUNT(*) AS n FROM generations').get().n,
        generations7d: q(
          "SELECT COUNT(*) AS n FROM generations WHERE created_at >= datetime('now', '-7 days')",
        ).get().n,
        signups7d: q(
          "SELECT COUNT(*) AS n FROM users WHERE created_at >= datetime('now', '-7 days')",
        ).get().n,
        tokensByModel: q(
          `SELECT model, COUNT(*) AS n, SUM(input_tokens) AS input_tokens,
                  SUM(output_tokens) AS output_tokens
           FROM generations GROUP BY model`,
        ).all(),
        recentPurchases: q(
          `SELECT purchases.*, users.email FROM purchases JOIN users ON users.id = purchases.user_id
           ORDER BY purchases.id DESC LIMIT 20`,
        ).all(),
        recentUsers: q(
          'SELECT id, email, credits, created_at FROM users ORDER BY id DESC LIMIT 20',
        ).all(),
      };
    },
  };
}
