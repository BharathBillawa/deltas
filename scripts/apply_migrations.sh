#!/bin/bash
# Apply database migrations
# Usage: ./scripts/apply_migrations.sh

set -e

DB_FILE="${DB_FILE:-deltas.db}"
MIGRATIONS_DIR="migrations"

echo "Applying migrations to: $DB_FILE"

for migration in "$MIGRATIONS_DIR"/*.sql; do
    if [ -f "$migration" ]; then
        echo "Applying: $(basename "$migration")"
        sqlite3 "$DB_FILE" < "$migration"
        echo "✓ Applied: $(basename "$migration")"
    fi
done

echo "All migrations applied successfully"
