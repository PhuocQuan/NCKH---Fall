import json
from pathlib import Path
import libsql_client
from libsql_client.client import LibsqlError

# Monkey patch libsql_client to prevent KeyError: 'result' when queries fail on Turso HTTP API
try:
    import libsql_client.http
    original_execute = libsql_client.http.HttpClient.execute

    async def patched_execute(self, stmt, args=None):
        request = {
            "stmt": libsql_client.http._stmt_to_proto(stmt, args),
        }
        response = await self._send("POST", "v1/execute", request)
        if "result" not in response:
            if "message" in response:
                raise LibsqlError(response["message"], response.get("code") or "UNKNOWN")
            raise LibsqlError(f"Unexpected response format: {response}", "UNKNOWN")
        proto_res = response["result"]
        return libsql_client.http._result_set_from_proto(proto_res)

    libsql_client.http.HttpClient.execute = patched_execute
except Exception as patch_err:
    print(f"[Monkey Patch Warning] Failed to patch libsql_client: {patch_err}")

DB_CONFIG_PATH = Path("configs/db.json")

_DB_INITIALIZED = False

def get_db_client():
    if not DB_CONFIG_PATH.exists():
        raise RuntimeError("db.json not found!")
    with DB_CONFIG_PATH.open(encoding="utf-8") as f:
        config = json.load(f).get("turso", {})
    url = config.get("url")
    if not url:
        raise RuntimeError("Turso URL not configured in db.json!")
    if url.startswith("libsql://"):
        url = url.replace("libsql://", "https://")
    auth_token = config.get("auth_token")
    
    client = libsql_client.create_client_sync(url=url, auth_token=auth_token)
    
    global _DB_INITIALIZED
    if not _DB_INITIALIZED:
        _DB_INITIALIZED = True
        try:
            _init_db_schema(client)
        except Exception as e:
            print(f"[DB Init Error] Khong the khoi tao DB schema: {e}")
            
    return client

def _init_db_schema(client):
    client.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password TEXT,
            name TEXT,
            role TEXT,
            status TEXT,
            assigned_cameras TEXT,
            phone TEXT,
            monitored_profile_json TEXT DEFAULT '{}',
            emergency_contacts_json TEXT DEFAULT '[]',
            user_notifications_json TEXT DEFAULT '[]',
            age INTEGER,
            gender TEXT,
            address TEXT
        )
    """)
    # Add new columns if table already existed without them
    res = client.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in res.rows]
    if "age" not in columns:
        try:
            client.execute("ALTER TABLE users ADD COLUMN age INTEGER")
            client.execute("ALTER TABLE users ADD COLUMN gender TEXT")
            client.execute("ALTER TABLE users ADD COLUMN address TEXT")
        except Exception as e:
            print(f"[DB Migration Error] Khong the them cot vao bang users: {e}")
            
    client.execute("""
        CREATE TABLE IF NOT EXISTS cameras (
            id TEXT PRIMARY KEY,
            name TEXT,
            ip TEXT,
            rtsp TEXT,
            area TEXT,
            target TEXT,
            state TEXT,
            status TEXT,
            fps INTEGER,
            resolution TEXT,
            threshold INTEGER
        )
    """)
    client.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY,
            time TEXT,
            camera TEXT,
            person TEXT,
            confidence INTEGER,
            status TEXT,
            level TEXT,
            media TEXT,
            state TEXT,
            cloud_img_url TEXT,
            cloud_video_url TEXT,
            deleted_by_users TEXT DEFAULT '[]'
        )
    """)
    client.execute("""
        CREATE TABLE IF NOT EXISTS app_state (
            id TEXT PRIMARY KEY,
            api_keys_json TEXT NOT NULL DEFAULT '[]',
            settings_json TEXT NOT NULL DEFAULT '{}',
            monitored_profile_json TEXT NOT NULL DEFAULT '{}',
            emergency_contacts_json TEXT NOT NULL DEFAULT '[]',
            user_notifications_json TEXT NOT NULL DEFAULT '[]'
        )
    """)
    client.execute("""
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT,
            type TEXT,
            user TEXT,
            content TEXT
        )
    """)
    # Tạo user admin mặc định nếu bảng users trống
    res = client.execute("SELECT 1 FROM users LIMIT 1")
    if not res.rows:
        client.execute(
            "INSERT INTO users (email, password, name, role, status, assigned_cameras, phone) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ["admin@nckh.vn", "nckh2025", "Quản trị viên", "Admin", "Đang hoạt động", "[]", "0901234567"]
        )


def log_action(log_type: str, user: str, content: str) -> None:
    try:
        with get_db_client() as client:
            client.execute("""
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    time TEXT,
                    type TEXT,
                    user TEXT,
                    content TEXT
                )
            """)
            import datetime
            now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            client.execute(
                "INSERT INTO system_logs (time, type, user, content) VALUES (?, ?, ?, ?)",
                [now_str, log_type, user, content]
            )
            # Keep only the latest 50 logs in the database to prevent accumulation
            client.execute(
                "DELETE FROM system_logs WHERE id NOT IN (SELECT id FROM system_logs ORDER BY id DESC LIMIT 50)"
            )
    except Exception as e:
        print(f"[Database Logging Error] {e}")

