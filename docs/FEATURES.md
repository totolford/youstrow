# État des fonctionnalités

Légende : ✅ fait et testé (sans matériel) · 🟡 fait, à valider avec du matériel · ⬜ pas encore reconstruit

| Fonction | État | Notes |
|---|---|---|
| Sortie ENTTEC Open DMX USB (D2XX + COM) | 🟡 | protocole testé octet par octet ; timing réel à valider |
| Sortie ENTTEC DMX USB PRO | 🟡 | paquets testés ; non vérifié sur matériel |
| Sortie Art-Net (ArtDMX, ArtPoll) | ✅/🟡 | paquets conformes, test UDP loopback |
| Assistant de connexion + diagnostic + test 100 % | ✅ | |
| 4 univers, patch, bibliothèque ~1800 appareils, anti-chevauchement | ✅ | |
| **Mémoires (pads)** : grille 8×8, REC, pages, exclusivité par colonne, mémoires par défaut | ✅ | comportement repris de l'original |
| **Surface EXT** (exécuteurs façon grandMA) : couleurs, strobe, effets, mémoires, faders, blackout, horloge | ✅ | disposition enregistrée dans le show |
| **Plan 3D** (Three.js dans QtWebEngine) : faisceaux volumétriques, brouillard, bloom, caméras | ✅ | alimenté en direct par le DMX réellement émis |
| **8 décors 3D** : concert (modèle 3D), scène 6×5 m, festival, discothèque, DJ mobile, conférence, sapin de Noël, nu | ✅ | hauteur d'accroche par décor ; import `.glb/.gltf` |
| Édition du positionnement 3D (X, Z, hauteur) | ✅ | onglet « Plan » |
| **Plein écran vidéo sur l'écran choisi**, fenêtre vidéo, retour | ✅ | vérifié sur 3 écrans réels |
| **Panneaux détachables** sur d'autres écrans (fenêtre / plein écran) via Affichage ▸ Fenêtres externes | ✅ | plan de feu, mémoires, effets, journal, 3D, média, EXT |
| Lecteur audio/vidéo, volume par piste, effet lumineux par piste | ✅ | |
| MIDI : profil AKAI APC mini + apprentissage + retour LED | ✅/🟡 | logique testée ; à valider sur un vrai APC mini |
| Splitter Showtec DB-1-8 (sorties 1-8, fiche de câblage) | ✅ | matériel passif : documenté/contrôlé, pas piloté |
| Pied Stairville BLS-315 Pro (150–310 cm) | ✅ | passif ; ce n'est pas une lumière (aucun canal DMX) |
| Plan de feu 2D live, testeur DMX, moniteur DMX, effets par couches, shows `.ysshow` | ✅ | |
| Interface redessinée depuis Figma (rail, barre supérieure, 6 espaces de travail) | ✅ | voir docs/FIGMA.md |
| Exécutable Windows + installeur | ✅ | |
| Timeline lumière / REC lumière / séquenceur LIVE / cue list | ⬜ | gros modules de l'original |
| Pixel map, fixtures à pixels, éditeur de fixtures, import QLC+/GrandMA | ⬜ | |
| IA Lumière, assistant vocal | ⬜ | exclus pour l'instant |
| DMX entrant, manette, Stream Deck, tablette, vMix, OBS | ⬜ | |
| Comptes, licence, cloud, mises à jour automatiques | ✗ | hors périmètre |

## Fichiers 3D
Le moteur 3D (`index.html`), les 2 modèles `.glb` et les vignettes des décors proviennent de l'application d'origine :
ils sont **présents en local** mais **non versionnés** (voir `.gitignore`) tant que leur publication n'est pas confirmée.
Sans eux, l'application fonctionne et l'espace « 3D » affiche un message explicatif. Les bibliothèques Three.js (MIT) sont versionnées.

## Choix de conception
- Pads : une colonne = un groupe d'appareils ; REC puis clic = enregistrer l'état courant ; re-clic = éteindre ; clic droit = vider.
- Un appareil sans mélange de couleurs (lyre à roue, gradateur) est « allumé » par la couleur choisie ; sa roue de couleur n'est pas pilotée automatiquement.
- Le canal Strobe suppose 0 = fermé/off et 16-255 = vitesse croissante : les plages réelles varient selon les appareils.
- Le Showtec DB-1-8 et le pied Stairville BLS-315 Pro sont passifs : YouStrow les documente et contrôle, il ne les pilote pas.
