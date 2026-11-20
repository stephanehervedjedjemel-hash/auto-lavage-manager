# Architecture technique — AUTO LAVAGE MANAGER
- Frontend : React + Vite, responsive, PWA à finaliser.
- Backend : FastAPI, API REST /api/v1.
- Données : PostgreSQL, SQLAlchemy 2.
- Authentification : JWT HS256 et mots de passe hachés scrypt.
- Déploiement local : Docker Compose.

Company est le tenant racine. Station et User portent company_id. Chaque lecture métier doit filtrer sur le company_id de l'utilisateur authentifié. Les identifiants transmis par le navigateur ne remplacent jamais ce contrôle.

Routes livrées : POST /auth/register-owner (protégée par BOOTSTRAP_SECRET), POST /auth/login, GET /companies/me, GET /stations et POST /stations.

Limites : les tables automatiques ne servent qu'au développement. Alembic, les permissions par station, invitations, réinitialisation du mot de passe, limitation des tentatives, journal d'audit, sauvegardes et tests d'isolation complets restent à faire. Ne pas utiliser avec des données réelles avant audit.
