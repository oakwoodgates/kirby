-- Create trigger function for funding_rates table
CREATE OR REPLACE FUNCTION notify_funding_update()
RETURNS TRIGGER AS $$
DECLARE
    payload TEXT;
BEGIN
    -- Build JSON payload with minimal data (listener will query full record)
    payload := json_build_object(
        'starlisting_id', NEW.starlisting_id,
        'time', to_char(NEW.time, 'YYYY-MM-DD"T"HH24:MI:SS"+00"')
    )::TEXT;

    -- Send notification on 'funding_updates' channel
    PERFORM pg_notify('funding_updates', payload);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger on funding_rates table
CREATE TRIGGER funding_update_notify_trigger
AFTER INSERT OR UPDATE ON funding_rates
FOR EACH ROW
EXECUTE FUNCTION notify_funding_update();

-- Create trigger function for open_interest table
CREATE OR REPLACE FUNCTION notify_oi_update()
RETURNS TRIGGER AS $$
DECLARE
    payload TEXT;
BEGIN
    -- Build JSON payload with minimal data (listener will query full record)
    payload := json_build_object(
        'starlisting_id', NEW.starlisting_id,
        'time', to_char(NEW.time, 'YYYY-MM-DD"T"HH24:MI:SS"+00"')
    )::TEXT;

    -- Send notification on 'oi_updates' channel
    PERFORM pg_notify('oi_updates', payload);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger on open_interest table
CREATE TRIGGER oi_update_notify_trigger
AFTER INSERT OR UPDATE ON open_interest
FOR EACH ROW
EXECUTE FUNCTION notify_oi_update();
