# Module des commissions — V0.6

## Affectation des laveurs
Chaque ligne de ticket peut être affectée à un salarié actif de la même entreprise et de la même station. L'affectation est facultative pour permettre l'enregistrement d'un ticket avant de connaître l'opérateur; une ligne sans laveur n'engendre pas de commission.

## Barèmes
Un administrateur d'entreprise ou responsable de station peut créer un barème avec :
- portée facultative par station, salarié et prestation;
- type `fixed` ou `percent`;
- montant fixe en FCFA par unité de prestation, ou taux en points de base;
- dates de début et de fin d'application.

Pour le taux en points de base : 100 = 1 %, 500 = 5 %, 1 000 = 10 %, 10 000 = 100 %. Le montant est arrondi à l'unité FCFA la plus proche.

Priorité de sélection : barème ciblant à la fois le salarié et la prestation, puis barème ciblant l'un des deux, puis barème général. À priorité égale, le barème de station est préféré, puis la date d'effet la plus récente.

## Calcul
- Fixe : valeur du barème × quantité de la ligne.
- Pourcentage : montant de la ligne × taux / 10 000.
- La commission est calculée lors de la création du ticket et enregistrée avec une copie du nom du salarié, du service, de la base, du type et de la valeur du barème.
- Une modification ultérieure du tarif ou du barème ne modifie jamais une commission déjà enregistrée.

## API V0.6
- `POST /api/v1/commission-rules` : créer un barème.
- `GET /api/v1/commission-rules` : consulter les barèmes.
- `GET /api/v1/commissions` : consulter les commissions et les totaux; filtres `start_date`, `end_date`, `station_id`, `employee_id`.
- `POST /api/v1/commissions/{entry_id}/payments` : enregistrer un règlement total ou partiel.

Un règlement est limité au solde restant. Les écritures de règlement sont conservées dans un journal et ne sont pas écrasées.

## Limites à traiter avant la mise en production
- Prévoir un workflow d'annulation/contrepassation des commissions si un ticket est annulé.
- Ajouter un contrôle d'audit des changements de barèmes et des règlements.
- Compléter les tests API d'isolation multi-entreprises, de concurrence et de permissions.
- Exécuter les migrations et l'ensemble de la suite Pytest dans l'environnement CI.
