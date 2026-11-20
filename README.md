# AUTO LAVAGE MANAGER
Logiciel SaaS multi-entreprises et multi-stations pour centres de lavage automobile.

## Stack
React + Vite; API Python/FastAPI; PostgreSQL + SQLAlchemy; JWT; Docker Compose.

## Démarrage
1. Copier .env.example vers .env et remplacer tous les secrets d'exemple.
2. Lancer docker compose up --build.
3. Interface : http://localhost:5173 ; API : http://localhost:8000 ; documentation : http://localhost:8000/docs.
4. En production ou préproduction, appliquer les migrations depuis le dossier backend avec alembic upgrade head.

## Première connexion
L'interface permet de créer le premier espace entreprise. Le code d'initialisation correspond à BOOTSTRAP_SECRET dans le fichier .env. La création initialise l'entreprise, une première station et son administrateur. Les connexions suivantes se font avec l'e-mail et le mot de passe.

Les administrateurs d'entreprise peuvent consulter/ajouter des stations, créer des comptes utilisateurs et activer/désactiver ces comptes. Les utilisateurs sont rattachés à leur entreprise; un utilisateur de station ne voit que sa station dans la liste des stations.

## Tests
Depuis backend/ : pytest -q.

## Statut
Version de développement 0.6.0. Le module de commissions V0.6 permet d'affecter un laveur à une ligne de ticket, de paramétrer des barèmes fixes ou en pourcentage, de figer les commissions calculées et d'enregistrer des règlements partiels ou totaux. La migration Alembic `20261120_commissions` ajoute l'affectation du salarié et le registre des commissions. Le produit n'est pas prêt pour la production : les annulations/contrepassations, l'audit complet, les tests d'intégration et la validation CI restent obligatoires.
