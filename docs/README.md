# Documentation

## `releases/`

Journal des modifications, une entrée par date de travail : `releases/AAAA-MM-JJ.md`.

Chaque entrée suit le même format :

- **Résumé** — ce qui a changé et pourquoi, en une ou deux phrases.
- **Ajouté / Modifié / Corrigé** — le détail, groupé par domaine (auth, stockage, email, module concerné, etc.).
- **Notes de déploiement** — tout ce qu'il faut faire manuellement en plus du déploiement habituel : nouvelles variables d'environnement, migrations, commandes `manage.py` à lancer, nouveaux services à démarrer.

But : garder une trace lisible de l'évolution du projet, et surtout une check-list fiable de ce qu'il faut faire pour déployer chaque lot de changements — pas un historique Git brut.

Pour voir les releases, parcourir `releases/` par ordre chronologique (le nom de fichier trie naturellement).
