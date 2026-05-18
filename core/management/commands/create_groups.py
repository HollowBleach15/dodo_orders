from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission

GROUPS = {
    "admin_staff":      [],
    "ops_manager":      ["view_order", "change_order", "view_client", "view_branch"],
    "branch_employee":  ["view_order", "add_order", "change_order"],
    "franchise_owner":  ["view_order", "view_client"],
}

class Command(BaseCommand):
    help = "Создаёт стандартные группы Django"

    def handle(self, *args, **kwargs):
        for name, perm_codenames in GROUPS.items():
            group, created = Group.objects.get_or_create(name=name)
            for codename in perm_codenames:
                try:
                    perm = Permission.objects.get(codename=codename)
                    group.permissions.add(perm)
                except Permission.DoesNotExist:
                    self.stderr.write(f"Permission not found: {codename}")
            action = "создана" if created else "обновлена"
            self.stdout.write(self.style.SUCCESS(f"Группа '{name}' {action}"))