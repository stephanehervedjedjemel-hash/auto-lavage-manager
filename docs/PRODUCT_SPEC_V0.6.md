# AUTO WASH MANAGER — Spécification fonctionnelle v0.6

## 1. Produit
Application SaaS multi-entreprises et multi-stations pour centres de lavage automobile. Langue initiale : français. Devise par défaut : XOF (FCFA). Interface responsive installable en PWA.

## 2. Profils et droits
- Plateforme (super-admin SaaS) : gestion des entreprises clientes, abonnements, suspension et indicateurs globaux sans accès ordinaire aux opérations financières des clients.
- Propriétaire / administrateur d'entreprise : accès à toutes les stations de son entreprise, paramétrage, utilisateurs, tarifs, rapports et validation des opérations sensibles.
- Responsable de station : opérations de sa station, équipe, caisse, stocks et rapports de station.
- Caissier : création des tickets, encaissements et clôture de caisse; pas de modification des tarifs ou des écritures validées.
- Laveur / opérateur : consultation des prestations assignées et enregistrement de l'exécution si cette fonction est activée; pas d'accès aux données financières globales.

Toute requête métier doit être filtrée par company_id. Les utilisateurs rattachés à une station sont également limités à station_id. Les contrôles doivent être effectués côté API, jamais uniquement dans l'interface.

## 3. Cycle d'un lavage
1. Choisir la station, le type de véhicule et une ou plusieurs prestations.
2. Sélectionner ou saisir le laveur responsable.
3. Le serveur calcule les montants à partir des tarifs actifs enregistrés; le navigateur ne fait jamais autorité sur les prix.
4. Créer un ticket avec numéro unique par entreprise, date/heure, lignes et copie historique des libellés/prix.
5. Enregistrer un ou plusieurs paiements (espèces, Wave, Orange Money, MTN Money, Moov Money, carte, virement ou autre).
6. Produire un ticket imprimable 58/80 mm et un PDF partageable.
7. Une annulation ou correction après validation doit être tracée, justifiée et réservée aux rôles autorisés. Aucun paiement ne doit être effacé.

## 4. Recettes et caisse
- Les recettes sont calculées à partir des paiements effectivement enregistrés, pas du seul montant des tickets.
- Un ticket peut être impayé, partiellement payé, payé ou annulé.
- Plusieurs moyens de paiement peuvent régler un ticket; chaque paiement conserve son montant, sa méthode, sa référence, son auteur et son horodatage.
- Une session de caisse est ouverte et clôturée par station. Le système calcule le solde théorique et l'écart avec le comptage physique.
- Les tableaux de bord distinguent chiffre d'affaires des prestations, encaissements, créances clients et mouvements de trésorerie.

## 5. Dépenses et charges
Catégories initiales : eau, électricité, produits de lavage, salaires, commissions, loyer, entretien/réparation, carburant, transport, frais administratifs et autres.
Une dépense comprend la station, catégorie, libellé, bénéficiaire/fournisseur, date, montant engagé, paiements, moyen de paiement et justificatif.
Les rapports distinguent charges engagées et décaissements.

## 6. Stocks
- Catalogue de produits avec unité, seuil d'alerte et statut.
- Fournisseurs et tarifs d'achat historisés par couple produit/fournisseur.
- Chaque entrée de stock conserve le coût unitaire réellement payé; une modification de tarif ne réécrit jamais les achats passés.
- Sorties de stock pour consommation, pertes ou ajustements avec motif, utilisateur et date.
- Valorisation du stock selon une méthode définie et documentée; aucune consommation automatique sans règle de dosage configurée.

## 7. Personnel, rémunération et commissions
- Fiche employé : matricule, nom, contact, poste, station, date d'embauche, statut et base de rémunération (journalière, hebdomadaire ou mensuelle).
- Paie : période, éléments de rémunération, avances, retenues, paiements et statut de validation.
- Commissions paramétrables par station, prestation, laveur ou équipe : montant fixe ou pourcentage; règle enregistrée avec date d'effet.
- Une commission est calculée sur les tickets éligibles selon la règle active au moment de la prestation. Elle ne doit pas être recalculée rétroactivement si le tarif ou le barème change.
- Prévenir les doubles paiements et conserver l'historique de validation/règlement.

## 8. Immobilisations et amortissements
- Registre des équipements et investissements : coût d'acquisition, date de mise en service, valeur résiduelle, durée d'utilisation et méthode.
- Calcul de la dotation mensuelle linéaire par défaut, avec prorata de mise en service selon la règle retenue.
- Les amortissements sont des charges calculées, pas des sorties de trésorerie.
- Les factures récurrentes (eau, électricité, loyer) restent des charges d'exploitation et ne sont pas des immobilisations.
- Les rapports présentent séparément dépenses payées, charges engagées et dotations aux amortissements.

## 9. Rapports
Filtres : station, période personnalisée, jour, semaine, mois et année.
États : recettes par période, nombre de véhicules, prestations les plus vendues, recettes par moyen de paiement, dépenses par catégorie, mouvements de stock, masse salariale, commissions dues/payées, amortissements et résultat de gestion.
Exports PDF et XLSX. Les chiffres doivent provenir des données validées et afficher la période, la station et la date de génération.

## 10. Règles de calcul du résultat
Résultat de gestion = chiffre d'affaires acquis - charges d'exploitation de la période - dotations aux amortissements.
Les encaissements ne sont pas assimilés automatiquement au chiffre d'affaires si des tickets restent impayés. Les achats de produits stockés ne sont pas tous consommés immédiatement : distinguer achats, variation de stock et consommation pour éviter de fausser la marge.
Afficher séparément le flux de trésorerie : encaissements réels - décaissements réels.

## 11. Sécurité, audit et fiabilité
- Isolation stricte multi-tenant et contrôle station.
- Mots de passe hachés, jetons sécurisés, limitation des accès et validation des rôles.
- Journal d'audit des créations, validations, annulations, changements de tarifs, mouvements de stock et clôtures.
- Identifiants de tickets uniques, contraintes en base, transactions atomiques et prévention des doublons.
- Sauvegardes testées, migrations versionnées et tests d'accès croisés entre entreprises.
- Données fictives uniquement dans les tests.
- Aucune déclaration de mise en production avant revue de sécurité, tests de restauration et tests fonctionnels complets.

## 12. Périmètre de livraison progressive
- V0.6 : consolider les fondations, modèle de permissions, tickets, paiements, caisse et règles d'audit.
- V0.7 : commissions des laveurs et rapprochement des paiements de commissions.
- V0.8 : stocks avancés, consommation et coût des produits par prestation.
- V0.9 : rapports de gestion et exports PDF/XLSX.
- V1.0 : PWA finalisée, impressions testées sur appareils réels, sécurité, sauvegardes et validation pilote.
