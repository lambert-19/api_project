#!/bin/bash
# Sécurisation de la base, exécutée une seule fois à la première initialisation du conteneur
# (après la création de $APP_USER par l'image gvenzl/oracle-free).
#
#   $APP_USER  (BIBLIO)     : propriétaire du schéma, utilisé uniquement par Alembic
#   $API_USER  (BIBLIO_API) : utilisé par l'API, lecture/écriture des données seulement
#
# Le script est rejouable : les objets déjà existants sont ignorés.
set -euo pipefail

sqlplus -s / as sysdba <<EOF
WHENEVER SQLERROR EXIT FAILURE
SET SERVEROUTPUT ON FEEDBACK OFF
ALTER SESSION SET CONTAINER = FREEPDB1;

-- ---------------------------------------------------------------------------
-- 1. Profil de mots de passe
-- ---------------------------------------------------------------------------
DECLARE
  e_existe EXCEPTION;
  PRAGMA EXCEPTION_INIT(e_existe, -2379);
BEGIN
  EXECUTE IMMEDIATE q'[
    CREATE PROFILE biblio_profile LIMIT
      FAILED_LOGIN_ATTEMPTS 5         -- verrouillage après 5 échecs
      PASSWORD_LOCK_TIME    15/1440   -- déverrouillage automatique après 15 min
      PASSWORD_REUSE_MAX    5         -- pas de réutilisation des 5 derniers mots de passe
      PASSWORD_REUSE_TIME   365
      PASSWORD_LIFE_TIME    UNLIMITED -- comptes de service : pas d'expiration qui casserait l'API
  ]';
EXCEPTION WHEN e_existe THEN NULL;
END;
/

-- ---------------------------------------------------------------------------
-- 2. Propriétaire du schéma : droits minimaux pour les migrations
-- ---------------------------------------------------------------------------
-- L'image donne DB_DEVELOPER_ROLE (trop large) et un quota illimité : on restreint
DECLARE
  e_pas_accorde EXCEPTION;
  PRAGMA EXCEPTION_INIT(e_pas_accorde, -1951);
BEGIN
  EXECUTE IMMEDIATE 'REVOKE DB_DEVELOPER_ROLE FROM ${APP_USER}';
EXCEPTION WHEN e_pas_accorde THEN NULL;
END;
/
GRANT CREATE SESSION, CREATE TABLE, CREATE SEQUENCE, CREATE VIEW TO ${APP_USER};
ALTER USER ${APP_USER} QUOTA 100M ON USERS PROFILE biblio_profile;

-- ---------------------------------------------------------------------------
-- 3. Rôle applicatif : reçoit SELECT/INSERT/UPDATE/DELETE sur chaque table
--    (accordés par Alembic après chaque migration, les tables n'existant pas encore)
-- ---------------------------------------------------------------------------
DECLARE
  e_existe EXCEPTION;
  PRAGMA EXCEPTION_INIT(e_existe, -1921);
BEGIN
  EXECUTE IMMEDIATE 'CREATE ROLE biblio_api_role';
EXCEPTION WHEN e_existe THEN NULL;
END;
/

-- ---------------------------------------------------------------------------
-- 4. Utilisateur de l'API : connexion + rôle, rien d'autre (pas de DDL, pas de quota)
-- ---------------------------------------------------------------------------
DECLARE
  e_existe EXCEPTION;
  PRAGMA EXCEPTION_INIT(e_existe, -1920);
BEGIN
  EXECUTE IMMEDIATE 'CREATE USER ${API_USER} IDENTIFIED BY "${API_USER_PASSWORD}" PROFILE biblio_profile';
EXCEPTION WHEN e_existe THEN NULL;
END;
/
GRANT CREATE SESSION, biblio_api_role TO ${API_USER};

-- ---------------------------------------------------------------------------
-- 5. Audit (Unified Auditing) : consultable dans UNIFIED_AUDIT_TRAIL (en SYSTEM)
-- ---------------------------------------------------------------------------
DECLARE
  e_existe EXCEPTION;
  PRAGMA EXCEPTION_INIT(e_existe, -46358);
BEGIN
  EXECUTE IMMEDIATE 'CREATE AUDIT POLICY biblio_echecs_connexion ACTIONS LOGON';
EXCEPTION WHEN e_existe THEN NULL;
END;
/
DECLARE
  e_existe EXCEPTION;
  PRAGMA EXCEPTION_INIT(e_existe, -46358);
BEGIN
  EXECUTE IMMEDIATE 'CREATE AUDIT POLICY biblio_modifs_schema ACTIONS CREATE TABLE, ALTER TABLE, DROP TABLE, TRUNCATE TABLE, GRANT, REVOKE';
EXCEPTION WHEN e_existe THEN NULL;
END;
/
AUDIT POLICY biblio_echecs_connexion WHENEVER NOT SUCCESSFUL;
AUDIT POLICY biblio_modifs_schema BY ${APP_USER}, ${API_USER};

BEGIN DBMS_OUTPUT.PUT_LINE('Securisation terminee : ${APP_USER} (proprietaire), ${API_USER} (API)'); END;
/
EXIT
EOF
