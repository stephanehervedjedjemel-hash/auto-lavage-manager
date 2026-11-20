# AUTO LAVAGE MANAGER
Logiciel SaaS de gestion multi-entreprises et multi-stations pour centres de lavage automobile.

## Stack
React + Vite; API Python/FastAPI; PostgreSQL + SQLAlchemy; JWT HS256 et hachage scrypt; Docker Compose.

## Démarrage local
1. Copier .env.example vers .env.
2. Remplacer les secrets POSTGRES_PASSWORD, JWT_SECRET et BOOTSTRAP_SECRET par des valeurs longues et aléatoires.
3. Lancer docker compose up --build.
4. API : http://localhost:8000 ; documentation : http://localhost:8000/docs.
5. En développement les tables sont créées automatiquement. En production, utiliser Alembic.

La route POST /api/v1/auth/register-owner initialise l'entreprise, la première station et le compte propriétaire avec BOOTSTRAP_SECRET. Puis POST /api/v1/auth/login permet de se connecter.

Tests : depuis backend/, exécuter pytest -q.

Socle de développement uniquement. Migrations, tests d'isolation, audit, journalisation, sauvegardes et déploiement restent à finaliser avant usage réel.
