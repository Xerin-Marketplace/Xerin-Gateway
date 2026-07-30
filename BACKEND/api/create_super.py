from __future__ import annotations

import getpass
import os
import sys
from email.utils import parseaddr

from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from api.config import settings
from api.database import SessionLocal
from api.models import Role, User, UserRole, UserStatus
from api.security import hash_password


def _read_value(env_name: str, prompt: str, current: str | None = None) -> str:
    value = os.getenv(env_name) or current
    if value:
        return value.strip()
    return input(prompt).strip()


def _read_password() -> str:
    password = os.getenv("SUPER_ADMIN_PASSWORD") or settings.SUPER_ADMIN_PASSWORD
    if not password:
        password = getpass.getpass("Super-admin password: ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            raise ValueError("Passwords do not match")

    if len(password) < 12:
        raise ValueError("Super-admin password must contain at least 12 characters")

    return password


def _is_valid_email(value: str) -> bool:
    _, parsed = parseaddr(value)
    return parsed == value and "@" in parsed


def create_super_admin() -> None:
    email = _read_value("SUPER_ADMIN_EMAIL", "Super-admin email: ", settings.SUPER_ADMIN_EMAIL).lower()
    phone = _read_value("SUPER_ADMIN_PHONE", "Super-admin phone: ", settings.SUPER_ADMIN_PHONE)
    first_name = _read_value(
        "SUPER_ADMIN_FIRST_NAME",
        "First name [Super]: ",
        settings.SUPER_ADMIN_FIRST_NAME,
    ) or "Super"
    last_name = _read_value(
        "SUPER_ADMIN_LAST_NAME",
        "Last name [Admin]: ",
        settings.SUPER_ADMIN_LAST_NAME,
    ) or "Admin"
    password = _read_password()

    if not _is_valid_email(email):
        raise ValueError("A valid email address is required")

    db = SessionLocal()
    try:
        existing = db.query(User).filter(
            or_(User.email == email, User.phone == phone)
        ).first()
        if existing:
            raise ValueError("A user with that email address or phone number already exists")

        role = db.query(Role).filter(Role.name == "super_admin").first()
        if role is None:
            role = Role(name="super_admin", description="Full system owner")
            db.add(role)
            db.flush()

        super_admin = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            password_hash=hash_password(password),
            status=UserStatus.active,
            is_verified=True,
        )
        db.add(super_admin)
        db.flush()

        db.add(UserRole(user_id=super_admin.id, role_id=role.id))
        db.commit()

        print("Super admin created successfully")
        print(f"Email: {email}")
        print("Password: [not displayed]")

    except (ValueError, SQLAlchemyError) as exc:
        db.rollback()
        print(f"Failed to create super admin: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        db.close()


if __name__ == "__main__":
    create_super_admin()
