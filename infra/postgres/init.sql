-- Runs once when the Postgres container initializes.
-- The POSTGRES_USER (thinkfirst) owns the schema and runs migrations.
-- The app connects as thinkfirst_app: NOT a superuser and NOT BYPASSRLS, so row-level security applies.
CREATE ROLE thinkfirst_app LOGIN PASSWORD 'thinkfirst_app_dev' NOSUPERUSER NOBYPASSRLS;
GRANT CONNECT ON DATABASE thinkfirst TO thinkfirst_app;
CREATE EXTENSION IF NOT EXISTS vector;
