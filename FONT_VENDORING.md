# Typographie originale — finalisation 0.2.1

Décision d'auteur : conserver la spécification visuelle originale **Spectral / Albert Sans / Spline Sans Mono**.

Le code source référence désormais des fichiers locaux sous `web/assets/fonts/` et son miroir packagé. Aucune police distante/CDN n'est utilisée au runtime.

Pour finaliser localement la release, exécuter `FINALISER_POLICES_ET_RELEASE.command`. Le finaliseur :

1. récupère les fontes depuis le dépôt officiel `google/fonts` au commit gelé `ade3d1533e06b2b1462ffcde8e08b129627ca360` ;
2. valide chaque fichier par son Git blob SHA-1 attendu ;
3. installe les mêmes bytes dans la source web et le miroir packagé ;
4. récupère les textes OFL exacts ;
5. vérifie la parité source/package ;
6. rejoue pytest si disponible ;
7. régénère `RC_0.2.1_SHA256.json` avec l'état `TAG_READY_FONTS_RESTORED` ;
8. produit le ZIP tag-ready.

Les fontes sont sous **SIL Open Font License 1.1**. Le runtime reste air-gap après vendoring.
