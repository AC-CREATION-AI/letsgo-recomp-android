# ACC-3415 — procédure de vérification sans jeu

## Tests reproductibles

Depuis la racine, après `tools/setup.sh --check` et `source tools/env.sh` sur une image disposant de JDK 17, SDK android-34 / build-tools 35.0.0, NDK 28.2.13676358 :

```sh
python3 -m unittest discover -s tests -v
```

Le compilateur **hôte** se sélectionne par `HOST_CC`, puis `CC`, puis `cc` / `clang` dans `PATH`. `ANDROID_NDK_HOME` ne sélectionne pas le compilateur hôte. Un compilateur absent ou incompatible provoque un skip explicite ; ce skip n'est pas une compilation réussie. Les tests de packaging exigent les outils Android et Java ci-dessus.

Sous-ensemble ciblé, sans SDK ni appareil :

```sh
python3 -m unittest discover -s tests -p 'test_guard_hardening.py' -v
python3 -m unittest discover -s tests -p 'test_build_runtime_jobs.py' -v
python3 -m unittest discover -s tests -p 'test_milestone_markers.py' -v
```

`build-runtime.sh` (à la racine) accepte `JOBS=1..64`, défaut 2. Le test utilise un faux compilateur et mesure le nombre de compilations concurrentes ; il vérifie aussi qu'un échec produit `SMOKE_FAIL` et RC 1. Il est découvert par la commande CI existante.

## Jalons logcat

Aucun appareil n'est utilisé pour cette modification. Lors d'un futur essai autorisé, filtrer le tag `lasrecomp` et chercher les événements suivants séparément :

| Marqueur | Signification / limite |
| --- | --- |
| `APP_OPEN` | `onCreate` du lanceur atteint. Ne prouve ni réservation ni démarrage du moteur. |
| `MEM_RESERVE_OK(<octets>)` | Fenêtre virtuelle de l'invité réservée à l'adresse demandée ; ne prouve pas sa consommation physique. |
| `MEM_RESERVE_FAIL(<octets>)` | `mmap` a échoué ou a rendu une autre adresse. |
| `VK_DEVICE_OK(<nom GPU/pilote>)` | `vkCreateDevice` a réussi. Ne prouve pas une présentation ni un jeu utilisable. |
| `VK_DEVICE_FAIL(<nom GPU/pilote>)` | Échec de `vkCreateDevice`, avec code Vulkan. Une panne antérieure à la sélection du GPU peut ne pas atteindre ce marqueur. |
| `GAME_FIRST_FRAME` | Premier appel de présentation invité traité par le renderer. Ne prouve pas le scanout physique ni un gameplay utilisable. |

Le test de placement des marqueurs est statique ; ce n'est pas une preuve d'exécution Android.

## État de cette révision locale

- Base letsgo : `6374c4f0272bba59c8d2cd04278fa6b66c0e2319`.
- JOBS : 4 tests, RC 0 après rouge (6 échecs ; pic de 24 compilations).
- Guards ciblés : 4 tests, RC 0 (rejeu du 09/11/2026).
- Marqueurs : 4 tests, RC 0 après rouge (4 échecs).
- Scan de secrets courant : RC 0. Scan historique complet : RC 0 après correction des faux positifs et déduplication des blobs (toutes refs locales, sans limite de 200 commits).
- Aucun build APK ni essai appareil exécuté ici. Aucun jeu, clé ou firmware utilisé.
- Rebase avant revue requis si les PR de conformité #19/#20/#21 sont fusionnées entre-temps.

### Exécution sur environnement brut (09/11/2026)

`python3 -m unittest discover -s tests -v` : RC 1, 79 tests, 3 échecs / 12 erreurs / 24 skips. Java, compilateur C et variables SDK/NDK absents dans cet environnement brut. Ce résultat est un échec, pas une suite validée. La toolchain provisionnée documentée dans le wiki doit être activée avant la mesure canonique ; cette mesure reste à terminer.

Toolchain hôte provisionnée : `. "$HOME/.local/opt/toolchain-acc3216/env.sh"`, puis `TMPDIR=/tmp ANDROID_NDK_HOME="$HOME/android-sdk/ndk/28.2.13676358" JOBS=2 python3 -m unittest discover -s tests -v`. Mesure du 09/11/2026 : **101 tests, RC 0, 8 skips** (93 tests non sautés). Les skips ne constituent pas des validations. Les tests de packaging de cette suite produisent des APK synthétiques temporaires : pas un build applicatif complet ni une publication.

Rejeu final du 09/11/2026 avec cette même commande, après ajout des cinq tests unitaires de sélection du compilateur : **106 tests, RC 0, 8 skips**, soit 98 non sautés. Les huit skips concernent quatre tests SDL Android-wait (`SDL3_TEST_ROOT`), trois contrôles de release préparée (`LETSGO_RELEASE_STAGING`) et un contrôle du buildkit audité (`LETSGO_KIT_SOURCE`). Aucun de ces huit contrôles n'est déclaré validé. Les tests `apk/test` lancés séparément : **8 tests, RC 0**, sans appareil.

La première relance prolongée au-delà du run avait échoué parce que son `TMPDIR` désignait le scratch éphémère supprimé du run précédent (fichiers introuvables). La commande ci-dessus fixe explicitement un répertoire temporaire stable. Activer uniquement la toolchain hôte sans `ANDROID_NDK_HOME` ne suffit pas : mesure intermédiaire **86 tests, RC 1, 7 erreurs, 8 skips**, dont des `KeyError` NDK.
