from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_REQUESTS_PATH = Path("data/access_requests.json")
VALID_ROLES = frozenset({"caregiver", "family", "staff"})
VALID_STATUS = frozenset({"pending", "approved", "rejected"})


@dataclass
class AccessRequest:
    id: str
    full_name: str
    email: str
    phone: str
    role: str
    message: str
    status: str
    created_at: str
    reviewed_at: str | None = None
    review_note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_raw(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("requests"), list):
        return [item for item in data["requests"] if isinstance(item, dict)]
    return []


def _save_raw(items: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"requests": items}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _resolve_path(path: Path | None) -> Path:
    return path if path is not None else DEFAULT_REQUESTS_PATH


def list_requests(
    *,
    status: str | None = None,
    path: Path | None = None,
) -> list[AccessRequest]:
    items = _load_raw(_resolve_path(path))
    requests = [_parse_request(item) for item in items]
    if status:
        target = status.strip().lower()
        requests = [req for req in requests if req.status == target]
    return sorted(requests, key=lambda req: req.created_at, reverse=True)


def create_request(
    *,
    full_name: str,
    email: str,
    phone: str,
    role: str,
    message: str = "",
    path: Path | None = None,
) -> AccessRequest:
    store = _resolve_path(path)
    name = full_name.strip()
    mail = email.strip()
    tel = phone.strip()
    role_key = role.strip().lower()
    if not name:
        raise ValueError("Nhap ho ten.")
    if not mail and not tel:
        raise ValueError("Nhap email hoac so dien thoai.")
    if role_key not in VALID_ROLES:
        raise ValueError("Vai tro khong hop le.")

    for existing in list_requests(path=path):
        if existing.status == "pending" and existing.email == mail and mail:
            raise ValueError("Email nay da co yeu cau dang cho duyet.")

    entry = AccessRequest(
        id=uuid.uuid4().hex[:12],
        full_name=name,
        email=mail,
        phone=tel,
        role=role_key,
        message=message.strip(),
        status="pending",
        created_at=_utc_now(),
    )
    items = _load_raw(store)
    items.append(entry.to_dict())
    _save_raw(items, store)
    return entry


def update_request_status(
    request_id: str,
    *,
    status: str,
    review_note: str = "",
    path: Path | None = None,
) -> AccessRequest:
    store = _resolve_path(path)
    target_status = status.strip().lower()
    if target_status not in VALID_STATUS:
        raise ValueError("Trang thai khong hop le.")
    items = _load_raw(store)
    updated: AccessRequest | None = None
    for index, item in enumerate(items):
        if str(item.get("id")) != request_id:
            continue
        item = dict(item)
        item["status"] = target_status
        item["reviewed_at"] = _utc_now()
        item["review_note"] = review_note.strip() or None
        items[index] = item
        updated = _parse_request(item)
        break
    if updated is None:
        raise ValueError("Khong tim thay yeu cau.")
    _save_raw(items, store)
    return updated


def _parse_request(raw: dict[str, Any]) -> AccessRequest:
    return AccessRequest(
        id=str(raw.get("id", "")),
        full_name=str(raw.get("full_name", "")),
        email=str(raw.get("email", "")),
        phone=str(raw.get("phone", "")),
        role=str(raw.get("role", "caregiver")),
        message=str(raw.get("message", "")),
        status=str(raw.get("status", "pending")),
        created_at=str(raw.get("created_at", "")),
        reviewed_at=raw.get("reviewed_at"),
        review_note=raw.get("review_note"),
    )
