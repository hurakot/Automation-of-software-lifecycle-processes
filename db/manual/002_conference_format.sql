BEGIN;

-- Running upgrade 7d643ecb0fe6 -> b3f1c2d4e5a6

ALTER TABLE conferences ADD COLUMN format TEXT DEFAULT 'offline' NOT NULL;

UPDATE alembic_version SET version_num='b3f1c2d4e5a6' WHERE alembic_version.version_num = '7d643ecb0fe6';

COMMIT;

