-- schema.sql — 360 Degree House Videos
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL DEFAULT '',
  slug TEXT UNIQUE,
  api_key TEXT UNIQUE,
  stripe_customer_id TEXT,
  trial_used INTEGER NOT NULL DEFAULT 0,
  member_status INTEGER NOT NULL DEFAULT 0, -- 0=none 1=trial 2=member
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS listings (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  address TEXT NOT NULL,
  price INTEGER,
  beds INTEGER,
  baths REAL,
  mls_number TEXT,
  exterior_panorama TEXT,
  interior_panorama TEXT,
  is_private INTEGER NOT NULL DEFAULT 0,
  is_trial INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  listing_id TEXT NOT NULL,
  job_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending', -- pending|partial|completed|failed
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  completed_at TEXT,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS free_tokens (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token TEXT UNIQUE NOT NULL,
  email TEXT NOT NULL,
  address TEXT NOT NULL,
  used INTEGER NOT NULL DEFAULT 0,
  expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_listings_user ON listings(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_listing ON jobs(listing_id);
CREATE INDEX IF NOT EXISTS idx_users_slug ON users(slug);
