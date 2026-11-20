# Annulation des tickets et remboursements

## Règles métier V0.7

- Seuls les rôles `company_admin` et `station_manager` peuvent annuler un ticket.
- Le motif est obligatoire (5 à 250 caractères).
- Un ticket déjà annulé ne peut pas être annulé une seconde fois.
- Les paiements d'origine restent immuables : aucun paiement n'est supprimé ou modifié.
- Un enregistrement `ticket_refunds` est créé pour chaque paiement d'origine, avec le montant, le mode, la référence, le motif, l'utilisateur et la date.
- Les commissions non réglées liées au ticket passent au statut `cancelled` et sont exclues des soldes à payer.
- Si une commission a déjà reçu un règlement, l'annulation est bloquée (HTTP 409) jusqu'à une régularisation comptable distincte.
- Un ticket annulé ne peut plus recevoir de paiement.

## Effets sur les rapports

- Le chiffre d'affaires exclut les tickets annulés.
- Les encaissements sont calculés nets des remboursements enregistrés sur la période.
- Les créances clients excluent les tickets annulés.
- Les rapports de station appliquent les mêmes règles.
- La caisse déduit les remboursements du mode de paiement correspondant.

## API

`POST /api/v1/tickets/{ticket_id}/cancel`

Corps JSON :

```json
{
  "reason": "Prestation non réalisée"
}
```

La réponse du ticket expose `refunds` et `refunded_amount`.

## Point de contrôle opérationnel

L'enregistrement d'un remboursement dans l'application constitue une écriture de remboursement. L'équipe de caisse doit vérifier que le remboursement a effectivement été remis au client via le moyen indiqué. La prochaine évolution devra permettre de distinguer explicitement remboursement préparé, exécuté et validé, ainsi que les remboursements partiels.
