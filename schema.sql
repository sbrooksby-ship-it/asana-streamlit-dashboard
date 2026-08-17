CREATE TABLE IF NOT EXISTS tasks (
  gid TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT 'Uncategorized',
  asana_url TEXT,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  removed_at TIMESTAMPTZ,
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ,
  modified_at TIMESTAMPTZ,
  completed BOOLEAN NOT NULL DEFAULT FALSE,
  due_on DATE,
  due_at TIMESTAMPTZ,
  assignee_gid TEXT,
  assignee_name TEXT,
  projects JSONB NOT NULL DEFAULT '[]'::jsonb,
  tags JSONB NOT NULL DEFAULT '[]'::jsonb,
  raw JSONB NOT NULL,
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE tasks ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT '';
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'Uncategorized';
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS asana_url TEXT;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS removed_at TIMESTAMPTZ;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE INDEX IF NOT EXISTS tasks_modified_at_idx ON tasks (modified_at);
CREATE INDEX IF NOT EXISTS tasks_completed_idx ON tasks (completed);
CREATE INDEX IF NOT EXISTS tasks_category_idx ON tasks (category);
CREATE INDEX IF NOT EXISTS tasks_active_idx ON tasks (active);

CREATE TABLE IF NOT EXISTS sync_runs (
  id BIGSERIAL PRIMARY KEY,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ,
  status TEXT NOT NULL,
  task_count INTEGER NOT NULL DEFAULT 0,
  error_message TEXT
);

CREATE TABLE IF NOT EXISTS task_history (
  id BIGSERIAL PRIMARY KEY,
  task_gid TEXT NOT NULL REFERENCES tasks(gid) ON DELETE CASCADE,
  changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  change_type TEXT NOT NULL,
  details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS task_history_gid_idx ON task_history (task_gid, changed_at DESC);
