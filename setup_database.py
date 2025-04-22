#!/usr/bin/env python3
"""
Database Table Setup Script for AI Log System

This script creates the necessary tables in Supabase, Neon, or PostgreSQL
databases for the log ingestion system. It automatically detects the database
type from the connection URI and creates the appropriate table structure.

Usage:
    python setup_database.py --uri "postgresql://user:password@host:port/dbname"
    
    or set environment variables:
    DATABASE_URI="postgresql://user:password@host:port/dbname" python setup_database.py
"""

import asyncio
import argparse
import os
from urllib.parse import urlparse
from typing import Dict, Any, Optional

# Import required database libraries
try:
    import asyncpg
except ImportError:
    print("Error: asyncpg library not found. Please install it with 'pip install asyncpg'")
    exit(1)

# SQL statements for creating the logs table
CREATE_TABLE_SUPABASE = """
CREATE TABLE IF NOT EXISTS logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    service TEXT,
    metadata JSONB
);
"""

CREATE_TABLE_NEON = """
CREATE TABLE IF NOT EXISTS logs (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    service_name TEXT,
    metadata JSONB
);
"""

CREATE_TABLE_POSTGRES = """
CREATE TABLE IF NOT EXISTS logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    service TEXT,
    metadata JSONB
);
"""

# Default sample data
SAMPLE_DATA_SUPABASE = """
INSERT INTO logs (timestamp, level, message, service, metadata)
VALUES 
    (NOW(), 'INFO', 'Application started', 'api-server', '{"version": "1.0.0", "environment": "development"}'),
    (NOW() - INTERVAL '5 minutes', 'ERROR', 'Database connection failed', 'db-service', '{"error_code": "DB-001", "retries": 3}'),
    (NOW() - INTERVAL '10 minutes', 'WARNING', 'High memory usage detected', 'monitoring', '{"memory_usage": 85, "threshold": 80}'),
    (NOW() - INTERVAL '1 hour', 'INFO', 'User login successful', 'auth-service', '{"user_id": "user-123", "login_method": "oauth"}'),
    (NOW() - INTERVAL '2 hours', 'DEBUG', 'Cache miss for key: user-profile', 'cache-service', '{"key": "user-profile", "cache_size": 1024}');
"""

SAMPLE_DATA_NEON = """
INSERT INTO logs (created_at, level, message, service_name, metadata)
VALUES 
    (NOW(), 'INFO', 'Application started', 'api-server', '{"version": "1.0.0", "environment": "development"}'),
    (NOW() - INTERVAL '5 minutes', 'ERROR', 'Database connection failed', 'db-service', '{"error_code": "DB-001", "retries": 3}'),
    (NOW() - INTERVAL '10 minutes', 'WARNING', 'High memory usage detected', 'monitoring', '{"memory_usage": 85, "threshold": 80}'),
    (NOW() - INTERVAL '1 hour', 'INFO', 'User login successful', 'auth-service', '{"user_id": "user-123", "login_method": "oauth"}'),
    (NOW() - INTERVAL '2 hours', 'DEBUG', 'Cache miss for key: user-profile', 'cache-service', '{"key": "user-profile", "cache_size": 1024}');
"""

async def detect_db_type(uri: str) -> str:
    """
    Detect database type from a connection URI.
    
    Args:
        uri: Database connection URI
        
    Returns:
        str: Database type (supabase, neon, or postgresql)
    """
    parsed = urlparse(uri)
    hostname = parsed.hostname if parsed.hostname else ""
    
    if 'supabase.co' in hostname:
        return 'supabase'
    elif 'neon.tech' in hostname or '.neon.' in hostname:
        return 'neon'
    else:
        return 'postgresql'

async def create_tables(uri: str, db_type: Optional[str] = None, add_sample_data: bool = True) -> None:
    """
    Create necessary tables in the database.
    
    Args:
        uri: Database connection URI
        db_type: Database type (supabase, neon, or postgresql)
        add_sample_data: Whether to add sample data
    """
    if not db_type:
        db_type = await detect_db_type(uri)
    
    print(f"Detected database type: {db_type}")
    
    # Choose the appropriate table creation SQL
    if db_type == 'supabase':
        create_table_sql = CREATE_TABLE_SUPABASE
        sample_data_sql = SAMPLE_DATA_SUPABASE if add_sample_data else None
    elif db_type == 'neon':
        create_table_sql = CREATE_TABLE_NEON
        sample_data_sql = SAMPLE_DATA_NEON if add_sample_data else None
    else:  # postgresql
        create_table_sql = CREATE_TABLE_POSTGRES
        sample_data_sql = SAMPLE_DATA_SUPABASE if add_sample_data else None
    
    # Connect to the database
    print(f"Connecting to {db_type} database...")
    try:
        conn = await asyncpg.connect(uri)
        
        # Create the logs table
        print("Creating logs table...")
        await conn.execute(create_table_sql)
        
        # Add sample data if requested
        if add_sample_data and sample_data_sql:
            print("Adding sample data...")
            await conn.execute(sample_data_sql)
        
        # Check if table was created successfully
        if db_type == 'neon':
            table_check = await conn.fetchval("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'logs')")
        else:
            table_check = await conn.fetchval("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'logs')")
        
        if table_check:
            print("✅ Success: Database tables created successfully!")
            
            # Show table count
            if db_type == 'neon':
                count = await conn.fetchval("SELECT COUNT(*) FROM logs")
            else:
                count = await conn.fetchval("SELECT COUNT(*) FROM logs")
            print(f"The logs table contains {count} records.")
            
            # Show how to connect
            if db_type == 'supabase':
                print("\nTo connect to this database in the AI Log System, use:")
                print(f"  - Database Type: supabase")
                print(f"  - Connection URI: {uri}")
            elif db_type == 'neon':
                print("\nTo connect to this database in the AI Log System, use:")
                print(f"  - Database Type: neon")
                print(f"  - Connection URI: {uri}")
            else:
                print("\nTo connect to this database in the AI Log System, use:")
                print(f"  - Database Type: postgresql")
                print(f"  - Connection URI: {uri}")
        else:
            print("❌ Error: Failed to create database tables.")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Setup database tables for AI Log System')
    parser.add_argument('--uri', type=str, help='Database connection URI')
    parser.add_argument('--type', type=str, choices=['supabase', 'neon', 'postgresql'], 
                        help='Database type (default: auto-detect)')
    parser.add_argument('--no-sample-data', action='store_true', 
                        help='Do not add sample data')
    
    args = parser.parse_args()
    
    # Get the URI from arguments or environment
    uri = args.uri or os.environ.get('DATABASE_URI')
    if not uri:
        parser.print_help()
        print("\nError: Database URI not provided. Use --uri or set DATABASE_URI environment variable.")
        return
    
    await create_tables(uri, args.type, not args.no_sample_data)

if __name__ == "__main__":
    asyncio.run(main())