from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def create_builtin(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    engine = apps.get_model("serving", "Engine")
    if not engine.objects.filter(kind="builtin", deleted_at__isnull=True).exists():
        engine.objects.create(name="Mesbah", kind="builtin", is_default=True)


class Migration(migrations.Migration):
    dependencies = [("serving", "0001_initial")]

    operations = [migrations.RunPython(create_builtin, migrations.RunPython.noop)]
