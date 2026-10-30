from src.web.shared.db import get_db_client

print("Testing DB Migration...")
try:
    client = get_db_client()
    res = client.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in res.rows]
    print("Current users table columns:", columns)
    if "age" in columns:
        print("Migration successful: age, gender, address are in the database.")
    else:
        print("Migration failed: columns not found!")
except Exception as e:
    print("Error:", e)
