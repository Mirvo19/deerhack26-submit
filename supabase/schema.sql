create extension if not exists "pgcrypto";

create table if not exists rooms (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  team_code text not null unique,
  track text not null default 'open',
  room text not null default '',
  created_at timestamptz not null default now()
);

alter table rooms add column if not exists room text not null default '';

create table if not exists submissions (
  id uuid primary key default gen_random_uuid(),
  room_id uuid not null references rooms(id) on delete cascade,
  title text not null default '',
  tagline text not null default '',
  description text not null default '',
  description_html text not null default '',
  github_url text not null default '',
  demo_url text default '',
  presentation_type text not null default 'link',
  presentation_file text not null default '',
  presentation_link text not null default '',
  tech_stack text[] not null default '{}',
  members text[] not null default '{}',
  problem_statement text not null default '',
  thumbnail_url text default '',
  status text not null default 'draft' check (status in ('draft','final')),
  submitted_at timestamptz,
  updated_at timestamptz not null default now(),
  unique(room_id)
);

create table if not exists github_cache (
  submission_id uuid primary key references submissions(id) on delete cascade,
  repo_full_name text,
  readme_html text default '',
  commit_count int,
  last_commit_message text,
  last_commit_author text,
  last_commit_at timestamptz,
  primary_language text,
  stars int,
  repo_updated_at timestamptz,
  fetch_error text,
  fetched_at timestamptz not null default now()
);

create table if not exists judges (
  uid uuid primary key,
  name text not null,
  email text not null unique,
  password_hash text,
  created_by uuid,
  created_at timestamptz not null default now(),
  active boolean not null default true
);
create table if not exists mentors (
  uid uuid primary key,
  name text not null,
  email text not null unique,
  password_hash text,
  created_by uuid,
  created_at timestamptz not null default now(),
  active boolean not null default true
);
create table if not exists admins (
  uid uuid primary key,
  name text not null,
  email text not null unique,
  password_hash text,
  created_by uuid,
  created_at timestamptz not null default now(),
  active boolean not null default true
);
create table if not exists superadmins (
  uid uuid primary key,
  name text not null,
  email text not null unique,
  password_hash text,
  created_by uuid,
  created_at timestamptz not null default now(),
  active boolean not null default true
);

create table if not exists scores (
  id uuid primary key default gen_random_uuid(),
  submission_id uuid not null references submissions(id) on delete cascade,
  judge_uid uuid not null,
  innovation int check (innovation between 1 and 10),
  execution int check (execution between 1 and 10),
  impact int check (impact between 1 and 10),
  presentation int check (presentation between 1 and 10),
  notes text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table scores drop constraint if exists scores_submission_id_judge_uid_key;

drop table if exists mentor_notes;

create table if not exists audit_log (
  id uuid primary key default gen_random_uuid(),
  actor_uid uuid,
  actor_role text,
  action text not null,
  target text,
  meta jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table if not exists settings (
  key text primary key,
  value jsonb not null default '""',
  updated_at timestamptz not null default now()
);
insert into settings (key, value) values
  ('submission_deadline', '"2030-01-01T00:00:00+00:00"'),
  ('fields_deadline', '"2030-01-01T00:00:00+00:00"'),
  ('presentation_deadline', '"2030-02-01T00:00:00+00:00"'),
  ('tracks', '["open", "ai & data", "web & apps", "hardware & iot", "social good"]'),
  ('event_name', '"deerhack school edition 2026"')
on conflict (key) do nothing;

alter table rooms enable row level security;
alter table submissions enable row level security;
alter table github_cache enable row level security;
alter table judges enable row level security;
alter table mentors enable row level security;
alter table admins enable row level security;
alter table superadmins enable row level security;
alter table scores enable row level security;
alter table audit_log enable row level security;
alter table settings enable row level security;

create index if not exists idx_scores_sub on scores(submission_id);
create index if not exists idx_audit_created on audit_log(created_at);
create index if not exists idx_sub_updated on submissions(updated_at);
create index if not exists idx_rooms_created on rooms(created_at);
