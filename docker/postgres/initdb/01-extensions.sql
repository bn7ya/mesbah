-- Runs once, on first initialisation of an empty data volume.
--
-- pgvector must exist before the first migration that declares a VectorField.
-- Creating it here rather than in a Django migration keeps the extension a
-- property of the database rather than of the application's history.

CREATE EXTENSION IF NOT EXISTS vector;

-- Trigram matching, for the ILIKE-style search repositories tend to grow.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Server-side UUID generation, so a DEFAULT can exist independently of Django.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
