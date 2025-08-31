# core/management/commands/ensure_test_users.py
from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from core.models import User

TEST_SET = [
    ("admin1", "admin"),
    ("core1", "core"),
    ("super", "super"),
    ("patient1", "patient"),
]

class Command(BaseCommand):
    help = "Ensure test users exist and password=123456 (idempotent)."

    def handle(self, *args, **opts):
        for username, role in TEST_SET:
            u, created = User.objects.get_or_create(
                username=username,
                defaults={"role": role, "password": make_password("123456"), "is_active": True},
            )
            if not created:
                # 强制校正密码与激活状态、角色
                u.password = make_password("123456")
                u.role = role
                u.is_active = True
                u.save(update_fields=["password", "role", "is_active"])
            self.stdout.write(self.style.SUCCESS(f"ok: {username} ({role})"))
        self.stdout.write(self.style.SUCCESS("All test users ensured."))
