#!/bin/sh
# On first run, seed the database from the baked-in copy.
# On subsequent runs, the volume already has the DB with chat/notes data.
if [ ! -f /data/pf2e.db ]; then
    echo "First run — seeding database..."
    cp /app/pf2e.db.seed /data/pf2e.db
fi

exec .venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 5000
