-- Create test database alongside the main one.
-- The main database (idealens) is created automatically by POSTGRES_DB.
SELECT 'CREATE DATABASE idealens_test OWNER idealens'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'idealens_test')\gexec
