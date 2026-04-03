-- ============================================================
-- ShieldTrade Audit Schema
-- ============================================================
-- Two tables, one relation:
--   policy_checks  → enforcement decisions (ALLOW / BLOCK)
--   trade_events   → Alpaca order submissions
--
-- A trade_event always links back to the policy_check that
-- approved it via policy_check_id (nullable for edge cases).
-- ============================================================


-- ------------------------------------------------------------
-- 1. policy_checks
--    One row per enforcement decision from policy_engine.py.
--    Written before any trade is attempted.
-- ------------------------------------------------------------

create table if not exists policy_checks (
    id               uuid        primary key default gen_random_uuid(),

    -- who / what was evaluated
    agent            text        not null,                 -- e.g. "trader"
    tool             text        not null,                 -- e.g. "place_order"
    ticker           text        not null default '',

    -- outcome
    decision         text        not null                  -- "ALLOW" | "BLOCK"
                                 check (decision in ('ALLOW', 'BLOCK', 'TEST')),
    blocked_reasons  jsonb       not null default '[]',   -- string[]
    checks           jsonb       not null default '[]',   -- CheckResult[]

    -- timing
    timestamp        timestamptz not null,                 -- when the check ran
    logged_at        timestamptz not null default now(),  -- when row was inserted

    -- optional extras
    error_message    text,                                 -- if engine itself errored
    metadata         jsonb                                 -- free-form agent context
);

-- Lookup: all decisions for a ticker over time
create index if not exists idx_policy_checks_ticker_ts
    on policy_checks (ticker, timestamp desc);

-- Lookup: all BLOCKs (for alerting / dashboards)
create index if not exists idx_policy_checks_decision
    on policy_checks (decision, logged_at desc);

-- Lookup: all actions by a specific agent
create index if not exists idx_policy_checks_agent
    on policy_checks (agent, logged_at desc);


-- ------------------------------------------------------------
-- 2. trade_events
--    One row per order submitted to Alpaca via alpaca_bridge.py.
--    Only written when a trade actually reaches Alpaca.
-- ------------------------------------------------------------

create table if not exists trade_events (
    id               uuid        primary key default gen_random_uuid(),

    -- link back to the policy approval that allowed this trade
    policy_check_id  uuid        references policy_checks (id) on delete set null,

    -- order identity
    order_id         text        not null unique,          -- Alpaca order UUID
    symbol           text        not null,
    side             text        not null                  -- "buy" | "sell"
                                 check (side in ('buy', 'sell')),
    qty              numeric     not null check (qty > 0),
    price            numeric,                              -- fill price (null until filled)
    order_type       text        not null default 'market',
    time_in_force    text        not null default 'day',

    -- lifecycle
    status           text        not null,                 -- e.g. "accepted", "filled", "rejected"
    submitted_at     timestamptz,                          -- from Alpaca response
    logged_at        timestamptz not null default now(),

    -- audit trail
    error_message    text,                                 -- set if Alpaca returned an error
    metadata         jsonb                                 -- raw Alpaca response fields
);

-- Lookup: all trades for a symbol over time
create index if not exists idx_trade_events_symbol_ts
    on trade_events (symbol, submitted_at desc);

-- Lookup: trades by status (e.g. find all "rejected")
create index if not exists idx_trade_events_status
    on trade_events (status, logged_at desc);

-- Lookup: trace a trade back to its policy approval
create index if not exists idx_trade_events_policy_check_id
    on trade_events (policy_check_id);


-- ============================================================
-- Security: RLS + append-only policies
-- Run this block after the tables exist.
-- ============================================================

-- Enable RLS (rows invisible to all by default)
alter table policy_checks enable row level security;
alter table trade_events  enable row level security;

-- Only the service_role backend can read/insert
create policy "backend insert" on policy_checks
    for insert with check (auth.role() = 'service_role');

create policy "backend select" on policy_checks
    for select using (auth.role() = 'service_role');

create policy "backend insert" on trade_events
    for insert with check (auth.role() = 'service_role');

create policy "backend select" on trade_events
    for select using (auth.role() = 'service_role');

-- Append-only: no one can update or delete audit rows
create policy "no updates" on policy_checks for update using (false);
create policy "no deletes" on policy_checks for delete using (false);
create policy "no updates" on trade_events  for update using (false);
create policy "no deletes" on trade_events  for delete using (false);

-- Tighten the side constraint now that we normalize before insert
alter table trade_events
    drop constraint if exists trade_events_side_check;

alter table trade_events
    add constraint trade_events_side_check
    check (side in ('buy', 'sell'));
