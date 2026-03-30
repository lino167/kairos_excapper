-- kairos_excapper schema for Supabase/Postgres

create table if not exists public.kairos_matches (
  id text primary key,
  home_team text not null,
  away_team text not null,
  excapper_link text,
  dropping_odds_id text,
  status text default 'pending' check (status in ('pending','notified','rejected','verified')),
  ai_analysis text,
  should_notify boolean,
  prediction jsonb,
  final_score text,
  final_data jsonb,
  was_correct boolean,
  verified_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists kairos_matches_status_idx on public.kairos_matches (status);

create table if not exists public.kairos_market_data (
  id bigserial primary key,
  match_id text not null references public.kairos_matches(id) on delete cascade,
  market_name text not null,
  source text not null check (source in ('dropping_odds','excapper')),
  data jsonb not null,
  created_at timestamptz default now()
);

create index if not exists kairos_market_data_match_idx on public.kairos_market_data (match_id);
create index if not exists kairos_market_data_source_idx on public.kairos_market_data (source);
create index if not exists kairos_market_data_data_gin on public.kairos_market_data using gin (data);

create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists t_kairos_matches_updated on public.kairos_matches;
create trigger t_kairos_matches_updated
before update on public.kairos_matches
for each row execute function public.set_updated_at();
