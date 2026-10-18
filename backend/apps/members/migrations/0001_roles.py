from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

ROLES: tuple[str, ...] = ("viewers", "reviewers", "trainers", "admins")


def create_roles(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    group = apps.get_model("auth", "Group")
    for name in ROLES:
        group.objects.get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [("auth", "0012_alter_user_first_name_max_length")]

    operations = [migrations.RunPython(create_roles, migrations.RunPython.noop)]
