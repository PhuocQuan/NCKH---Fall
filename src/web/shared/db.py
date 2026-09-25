import json
from pathlib import Path
import sqlite3
from typing import Any
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


class SqliteResultSet:
    """Result set wrapper matching libsql_client ResultSet interface."""
    def __init__(self, rows: list[tuple[Any, ...]], columns: list[str] | None = None) -> None:
        self.rows = rows
        self.columns = columns or []


class SqliteLocalClient:
    """Local SQLite client matching libsql_client synchronous interface."""
    def __init__(self, db_path: str = "data/local.db") -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)

    def __enter__(self) -> "SqliteLocalClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is None:
            try:
                self.conn.commit()
            except Exception:
                pass
        self.close()

    def execute(self, stmt: str, args: Any = None) -> SqliteResultSet:
        cur = self.conn.cursor()
        if args:
            cur.execute(stmt, args)
        else:
            cur.execute(stmt)
        rows = cur.fetchall()
        self.conn.commit()
        return SqliteResultSet(rows)

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass


class ResilientDbClient:
    """DB client wrapper ensuring zero downtime and offline persistence by bridging Turso with SQLite."""
    def __init__(self, turso_client: Any | None = None, local_path: str = "data/local.db") -> None:
        self._turso_client = turso_client
        self._local_client = SqliteLocalClient(local_path)
        self._use_local = (turso_client is None)

    def __enter__(self) -> "ResilientDbClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._turso_client is not None:
            try:
                self._turso_client.close()
            except Exception:
                pass
        self._local_client.close()

    def execute(self, stmt: str, args: Any = None) -> Any:
        if not self._use_local and self._turso_client is not None:
            try:
                res = self._turso_client.execute(stmt, args)
                # Đồng bộ thao tác ghi vào SQLite cục bộ để đảm bảo dữ liệu luôn sẵn sàng khi offline
                s = stmt.strip().upper()
                if s.startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER")):
                    try:
                        self._local_client.execute(stmt, args)
                    except Exception:
                        pass
                return res
            except Exception as e:
                # Turso không thể kết nối -> tự động chuyển sang SQLite cục bộ
                self._use_local = True

        return self._local_client.execute(stmt, args)

    def close(self) -> None:
        if self._turso_client is not None:
            try:
                self._turso_client.close()
            except Exception:
                pass
        self._local_client.close()


def get_db_client(local_path: str = "data/local.db") -> ResilientDbClient:
    turso_client = None
    if DB_CONFIG_PATH.exists():
        try:
            with DB_CONFIG_PATH.open(encoding="utf-8") as f:
                config = json.load(f).get("turso", {})
            url = config.get("url")
            if url:
                if url.startswith("libsql://"):
                    url = url.replace("libsql://", "https://")
                auth_token = config.get("auth_token")
                turso_client = libsql_client.create_client_sync(url=url, auth_token=auth_token)
        except Exception:
            turso_client = None

    client = ResilientDbClient(turso_client=turso_client, local_path=local_path)
    
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
    # Khởi tạo camera mặc định nếu bảng cameras trống
    res_cams = client.execute("SELECT 1 FROM cameras LIMIT 1")
    if not res_cams.rows:
        client.execute(
            """INSERT INTO cameras (id, name, ip, rtsp, area, target, state, status, fps, resolution, threshold)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ["CAM-011", "Camera Imou Phòng Chính", "192.168.1.18", "rtsp://admin:L223Xr!w@192.168.1.18:554/cam/realmonitor?channel=1&subtype=1", "Phòng chính", "Nguy cơ cao", "normal", "online", 25, "1920x1080", 80]
        )


OFFLINE_LOG_PATH = Path("data/system_logs_offline.csv")


def log_action(log_type: str, user: str, content: str) -> None:
    import datetime
    now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
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
            client.execute(
                "INSERT INTO system_logs (time, type, user, content) VALUES (?, ?, ?, ?)",
                [now_str, log_type, user, content]
            )
            # Keep only the latest 50 logs in the database to prevent accumulation
            client.execute(
                "DELETE FROM system_logs WHERE id NOT IN (SELECT id FROM system_logs ORDER BY id DESC LIMIT 50)"
            )
    except Exception as e:
        print(f"[Database Logging Warning - Falling back to offline log] {e}")
        try:
            OFFLINE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with OFFLINE_LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(f'"{now_str}","{log_type}","{user}","{content}"\n')
        except Exception as file_err:
            print(f"[Offline Log Error] {file_err}")

