DO
$$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'prepsuite_app') THEN
        CREATE ROLE prepsuite_app LOGIN PASSWORD 'prepsuite_app';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE prepsuite TO prepsuite_app;
GRANT USAGE ON SCHEMA public TO prepsuite_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO prepsuite_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO prepsuite_app;
