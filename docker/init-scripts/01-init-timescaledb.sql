-- Initialize TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create a custom function to ensure TimescaleDB is ready
CREATE OR REPLACE FUNCTION ensure_timescaledb_ready()
RETURNS void AS $$
BEGIN
    -- Verify TimescaleDB extension is loaded
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        RAISE EXCEPTION 'TimescaleDB extension is not installed';
    END IF;

    RAISE NOTICE 'TimescaleDB is ready';
END;
$$ LANGUAGE plpgsql;

SELECT ensure_timescaledb_ready();
