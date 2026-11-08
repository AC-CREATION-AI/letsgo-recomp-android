# Circuit de fusion de ce dépôt

`master` n'accepte que des PR. Une PR est fusionnée seulement quand :

1. elle n'est plus en brouillon ;
2. une identité **différente de l'auteur** l'a approuvée au head exact (un agent ne fusionne jamais sa propre PR,
   voir [`AGENTS.md`](../AGENTS.md)) ;
3. la CI est verte et l'historique reste linéaire (squash ou rebase).

Personne ne fusionne à la main depuis une tâche d'agent. La publication (tag `v*`, release,
`LETSGO_RELEASE_APPROVED`) reste la décision du propriétaire du dépôt.

Côté AC-Création, l'ouverture d'une PR crée automatiquement une tâche de revue pour une identité de revue, et la
fusion est faite par une identité dédiée une fois les conditions ci-dessus réunies. Le détail de cette automatisation
(adresses, comptes, fichiers de configuration) est interne et n'est pas publié ici : il ne change rien aux règles
pour un contributeur.
