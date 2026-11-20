# Administration des entreprises, stations et utilisateurs

## Rôles applicatifs
- company_admin : administration de l'entreprise, de ses stations et utilisateurs.
- station_manager : responsable de station (permissions fines à compléter).
- operator : opérateur de lavage.
- cashier : caissier.

## Utilisateurs
Les administrateurs peuvent lister les comptes, créer un utilisateur et activer/désactiver un compte. Le mot de passe doit contenir au moins 12 caractères. Un utilisateur peut être rattaché à une station de sa propre entreprise uniquement. Il faut conserver au moins un administrateur actif par entreprise; un administrateur ne peut pas désactiver son propre compte.

## Migrations
Depuis le dossier backend : alembic upgrade head. Pour générer une migration après modification des modèles : alembic revision --autogenerate -m "description", puis vérifier le fichier avant application.

La migration initiale est fournie. L'application ne lance plus automatiquement create_all hors environnement de développement.