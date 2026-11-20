# Administration des entreprises, stations et utilisateurs

## Rôles applicatifs
- company_admin : administration de l'entreprise et de ses stations/utilisateurs.
- station_manager : rôle de responsable de station (permissions fines à compléter).
- operator : opérateur de lavage.
- cashier : caissier.

## Utilisateurs
Les administrateurs peuvent lister les comptes, créer un utilisateur et activer/désactiver un compte. Le mot de passe doit contenir au moins 12 caractères. Un utilisateur peut être rattaché à une station de sa propre entreprise uniquement.

## Migrations
Depuis le dossier backend : alembic upgrade head. Pour générer une nouvelle migration après modification des modèles : alembic revision --autogenerate -m "description", puis vérifier le fichier produit avant de l'appliquer.

La migration initiale est fournie. L'application ne lance plus automatiquement create_all hors environnement de développement.
