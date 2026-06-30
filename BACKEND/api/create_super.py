from api.database import SessionLocal
from api.models import User, Role, UserRole, UserStatus
from api.security import hash_password


db = SessionLocal()

email = "superadmin@xerin.com"
phone = "255767939809"

existing_user = db.query(User).filter(User.email == email).first()

if existing_user:
    print("Super admin already exists")
    exit()

super_admin = User(
    first_name="Super",
    last_name="Admin",
    email=email,
    phone=phone,
    password_hash=hash_password("SuperAdmin123"),
    status=UserStatus.active,
    is_verified=True,
)

db.add(super_admin)
db.commit()
db.refresh(super_admin)

role = db.query(Role).filter(Role.name == "super_admin").first()

if not role:
    role = Role(
        name="super_admin",
        description="Full system owner"
    )
    db.add(role)
    db.commit()
    db.refresh(role)

user_role = UserRole(
    user_id=super_admin.id,
    role_id=role.id
)

db.add(user_role)
db.commit()

print("Super admin created successfully")
print("Email:", email)
print("Password: SuperAdmin123")

db.close()