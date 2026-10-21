import uuid

from django.db import migrations


def seed_statuses(apps, schema_editor):
    Status = apps.get_model('tasks', 'TaskStatus')
    for name, final in [('In Progress', False), ('Postponed', False),
                        ('Waiting for Customer Response', False), ('Canceled', True), ('Completed', True)]:
        Status.objects.create(id=uuid.uuid5(uuid.NAMESPACE_URL, 'task-tracker/status/' + name), name=name, final=final)


FORWARD = """
CREATE FUNCTION protect_used_task_status() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.first_used_at IS NOT NULL THEN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'A used task status cannot be deleted' USING ERRCODE = '23514';
        END IF;
        IF NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'A used task status cannot be changed' USING ERRCODE = '23514';
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER protect_used_task_status BEFORE UPDATE OR DELETE ON tasks_taskstatus
    FOR EACH ROW EXECUTE FUNCTION protect_used_task_status();
CREATE FUNCTION mark_task_status_used() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    UPDATE tasks_taskstatus SET first_used_at = statement_timestamp()
        WHERE id = NEW.status_id AND first_used_at IS NULL;
    RETURN NEW;
END;
$$;
CREATE TRIGGER mark_task_status_used BEFORE INSERT OR UPDATE OF status_id ON tasks_task
    FOR EACH ROW EXECUTE FUNCTION mark_task_status_used();
"""
REVERSE = """
DROP TRIGGER mark_task_status_used ON tasks_task;
DROP FUNCTION mark_task_status_used();
DROP TRIGGER protect_used_task_status ON tasks_taskstatus;
DROP FUNCTION protect_used_task_status();
"""


class Migration(migrations.Migration):
    dependencies = [('tasks', '0001_initial')]
    operations = [migrations.RunPython(seed_statuses, migrations.RunPython.noop), migrations.RunSQL(FORWARD, REVERSE)]
