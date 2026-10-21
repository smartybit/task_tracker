from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('timesheets', '0004_remove_timeentry_one_running_entry_and_more')]
    operations = [migrations.RunSQL('''
        CREATE FUNCTION timesheet_entry_agreement() RETURNS trigger AS $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM timesheets_worksession
                           WHERE id = NEW.session_id AND timesheet_id = NEW.timesheet_id FOR SHARE) THEN
                RAISE EXCEPTION 'Entry and session timesheets must agree' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER timesheet_entry_agreement BEFORE INSERT OR UPDATE ON timesheets_timeentry
        FOR EACH ROW EXECUTE FUNCTION timesheet_entry_agreement();
        CREATE FUNCTION timesheet_session_agreement() RETURNS trigger AS $$
        BEGIN
            IF EXISTS (SELECT 1 FROM timesheets_timeentry
                       WHERE session_id = NEW.id AND timesheet_id <> NEW.timesheet_id) THEN
                RAISE EXCEPTION 'Session and entry timesheets must agree' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER timesheet_session_agreement BEFORE UPDATE ON timesheets_worksession
        FOR EACH ROW EXECUTE FUNCTION timesheet_session_agreement();
    ''', '''
        DROP TRIGGER timesheet_session_agreement ON timesheets_worksession;
        DROP FUNCTION timesheet_session_agreement();
        DROP TRIGGER timesheet_entry_agreement ON timesheets_timeentry;
        DROP FUNCTION timesheet_entry_agreement();
    ''')]
