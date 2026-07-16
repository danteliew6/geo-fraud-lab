-- geo-fraud-lab :: teardown — drop the entire lab schema (all tables + views).
-- Used by uninstall.sh. The catalog itself is left intact.
DROP SCHEMA IF EXISTS {{CATALOG}}.{{SCHEMA}} CASCADE;
