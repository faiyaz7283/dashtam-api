#!/bin/bash
# PostgreSQL test database initialization script
# This script creates the test database and user when PostgreSQL starts in test mode
# It's executed automatically by the PostgreSQL Docker container

set -e

# Check if we're in test mode
if [ "$POSTGRES_DB" = "dashtam_test" ] || [ -n "$TEST_POSTGRES_DB" ]; then
    echo "🧪 Initializing PostgreSQL for test environment..."
    
    # Use the test credentials if provided, otherwise use defaults
    TEST_DB="${TEST_POSTGRES_DB:-dashtam_test}"
    TEST_USER="${TEST_POSTGRES_USER:-dashtam_test_user}"
    TEST_PASSWORD="${TEST_POSTGRES_PASSWORD:-test_password}"
    
    echo "📝 Creating test database: $TEST_DB"
    echo "👤 Creating test user: $TEST_USER"
    
    # Create test user if it doesn't exist
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
        DO \$\$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = '$TEST_USER') THEN
                CREATE USER $TEST_USER WITH PASSWORD '$TEST_PASSWORD';
                RAISE NOTICE 'Created test user: $TEST_USER';
            ELSE
                RAISE NOTICE 'Test user already exists: $TEST_USER';
            END IF;
        END
        \$\$;
        
        -- Grant privileges to test user
        ALTER USER $TEST_USER CREATEDB;
        GRANT ALL PRIVILEGES ON DATABASE "$POSTGRES_DB" TO $TEST_USER;
        
        -- Enable UUID extension (required for our models)
        CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
        
        RAISE NOTICE '✅ Test database initialization complete';
EOSQL
    
    echo "✅ PostgreSQL test environment ready!"
else
    echo "ℹ️  Not in test mode, skipping test database initialization"
fi
