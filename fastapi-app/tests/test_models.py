"""The database tables compile to valid PostgreSQL DDL. No database needed: this renders the
CREATE TABLE / CREATE INDEX statements that a migration would run, and checks the key rules."""
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlmodel import SQLModel

import models  # noqa: F401  (registers the tables)

DIALECT = postgresql.dialect()
TABLES = SQLModel.metadata.tables


def ddl(table_name: str) -> str:
    table = TABLES[table_name]
    parts = [str(CreateTable(table).compile(dialect=DIALECT))]
    parts += [str(CreateIndex(index).compile(dialect=DIALECT)) for index in table.indexes]
    return "\n".join(parts)


def test_every_table_compiles():
    expected = {
        "boxes", "cameras", "contacts", "push_inbox", "ingest_cursors", "events", "stranger_profiles",
        "sightings", "count_buckets", "alarm_rules", "alarm_rule_cameras", "alarm_rule_windows",
        "alarm_rule_targets", "alarm_rule_recipients", "alarm_rule_state", "incidents",
        "incident_events", "notifications", "app_settings", "audit_log",
    }
    assert expected <= set(TABLES)
    for name in TABLES:
        assert "CREATE TABLE" in ddl(name)


def test_creation_order_resolves_every_foreign_key():
    # sorted_tables raises / warns on unresolvable cycles; every FK must point at a known table.
    for table in SQLModel.metadata.sorted_tables:
        for fk in table.foreign_keys:
            assert fk.column is not None


def test_events_are_deduplicated_per_box_record():
    sql = ddl("events")
    assert "UNIQUE (box_id, kind, alarm_id)" in sql
    assert "USING brin (occurred_at)" in sql
    assert "kind IN ('matched', 'stranger', 'face_capture', 'body_capture')" in sql


def test_a_track_belongs_to_one_sighting_per_camera_and_day():
    sql = ddl("sightings")
    assert "UNIQUE INDEX uq_sightings_face_track ON sightings (camera_id, local_date, face_track_id) " \
           "WHERE face_track_id IS NOT NULL" in sql
    assert "UNIQUE INDEX uq_sightings_body_track" in sql
    assert "INCLUDE (person_key, person_source)" in sql
    assert "face_embedding REAL[]" in sql


def test_stranger_fingerprints_are_plain_arrays():
    # No pgvector for now: fingerprints are compared in Python, the database only stores them.
    sql = ddl("stranger_profiles")
    assert "embedding REAL[] NOT NULL" in sql
    assert "vector" not in sql.lower()


def test_cooldown_and_email_queue_keys():
    assert "PRIMARY KEY (rule_id, camera_id)" in ddl("alarm_rule_state")
    sql = ddl("notifications")
    assert "UNIQUE (incident_id, contact_id, channel)" in sql
    assert "WHERE status IN ('pending', 'sending')" in sql


def test_incidents_survive_rule_and_event_cleanup():
    sql = ddl("incidents")
    assert "FOREIGN KEY(rule_id) REFERENCES alarm_rules (id) ON DELETE SET NULL" in sql
    assert "FOREIGN KEY(trigger_event_id) REFERENCES events (id) ON DELETE SET NULL" in sql
    assert "DEFAULT gen_random_uuid()" in sql
