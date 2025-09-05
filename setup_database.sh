#!/bin/bash

# Script to create PostgreSQL database and import schema
# Run this script with sudo
# This script sets up the Musically database with all required tables

echo "========================================"
echo "PostgreSQL Database Setup for Musically"
echo "========================================"
echo "Setting up database with schema..."

# Create the database as postgres user
sudo -u postgres psql <<EOF
-- Check if database exists and drop if needed (optional)
-- DROP DATABASE IF EXISTS musically;

-- Create the database
CREATE DATABASE musically;

-- Create a user for the application (optional - customize as needed)
-- CREATE USER musically_user WITH PASSWORD 'your_password_here';
-- GRANT ALL PRIVILEGES ON DATABASE musically TO musically_user;

\q
EOF

if [ $? -eq 0 ]; then
    echo "Database 'musically' created successfully!"
    
    echo "Importing schema..."
    # Import the schema file
    sudo -u postgres psql -d musically < /home/softroniclabs012/PycharmProjects/musically-backend/schema_modified.sql
    
    if [ $? -eq 0 ]; then
        echo "Schema imported successfully!"
        
        # List tables to verify
        echo -e "\nTables created:"
        sudo -u postgres psql -d musically -c "\dt"
        
        # Grant permissions to application user if exists
        echo -e "\nSetting up permissions (if user exists)..."
        sudo -u postgres psql -d musically <<PERMISSIONS
-- Grant permissions to application user (will fail silently if user doesn't exist)
GRANT ALL ON ALL TABLES IN SCHEMA public TO musically_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO musically_user;
GRANT USAGE, CREATE ON SCHEMA public TO musically_user;
\q
PERMISSIONS
    else
        echo "Error importing schema!"
        exit 1
    fi
else
    echo "Error creating database!"
    exit 1
fi

echo -e "\n========================================"
echo "Database setup complete!"
echo "========================================"
echo ""
echo "Tables created:"
echo "  - users (user accounts and profiles)"
echo "  - content (musical content/compositions)"
echo "  - playlists (collections of content)"
echo "  - playlist_content (playlist-content relationships)"
echo "  - creator_subscriptions (creator subscription tiers)"
echo "  - user_subscriptions (user-to-creator subscriptions)"
echo "  - playlist_access (user access to playlists)"
echo "  - game_sessions (game play tracking)"
echo "  - note_attempts (detailed note performance)"
echo "  - reviews (creator reviews)"
echo "  - marketplace_listings (content for sale)"
echo ""
echo "To connect to the database:"
echo "  As postgres user: psql -U postgres -d musically"
echo "  As app user: psql -U musically_user -d musically"