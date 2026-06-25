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
    return libsql_client.create_client_sync(url=url, auth_token=auth_token)


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

