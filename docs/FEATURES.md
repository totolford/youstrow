# État des fonctionnalités

Légende : ✅ fait et testé (sans matériel) · 🟡 fait, à valider avec du matériel · ⬜ pas encore reconstruit (prévu)

| Fonction | État | Notes |
|---|---|---|
| Sortie ENTTEC Open DMX USB (D2XX + COM) | 🟡 | protocole testé octet par octet ; timing réel à valider |
| Sortie ENTTEC DMX USB PRO | 🟡 | paquets 7E/label 6/E7 testés ; non vérifié sur matériel |
| Sortie Art-Net (ArtDMX, ArtPoll) | ✅/🟡 | paquets conformes, test UDP loopback ; découverte de nodes non testée sur un vrai node |
| Assistant de connexion + diagnostic + test 100 % | ✅ | |
| 4 univers, patch, bibliothèque ~1800 appareils, anti-chevauchement | ✅ | |
| Pads couleurs par groupe, niveaux de groupes, master, blackout, CLEAR | ✅ | sémantique des pads **réinterprétée** (voir ci-dessous) |
| Plan de feu 2D live (sélection, déplacement) | ✅ | |
| Couleur / luminosité / strobe / Pan-Tilt (16 bits) | ✅ | |
| Effets par couches + éditeur | ✅ | 8 effets intégrés, effets perso |
| DMX Tester 512 faders, DMX Monitor | ✅ | |
| Shows .ysshow, récents, réglages | ✅ | |
| Exécutable Windows (PyInstaller) | ✅ | `dist\youstrow\youstrow.exe` |
| Playlist média + lecteur audio/vidéo | ✅ | volume par piste, effet lumineux par piste, vidéo détachable ; testé avec WAV/MP4 réels |
| Timeline lumière / REC lumière / séquenceur LIVE / cue list | ⬜ | gros modules (`light_timeline`, `sequencer`) |
| MIDI : profil AKAI APC mini + apprentissage + retour LED | ✅/🟡 | logique testée sans matériel ; le profil APC suit la disposition publiée, à valider sur un vrai APC mini. Launchpad/MIDImix : via apprentissage |
| Splitter Showtec DB-1-8 (sorties 1-8, fiche de câblage) | ✅ | matériel passif : documenté/contrôlé, pas piloté |
| Pied Stairville BLS-315 Pro (hauteur 150–310 cm) | ✅ | passif ; ce n'est pas une lumière (aucun canal DMX) |
| Plan 3D, pixel map, fixtures à pixels | ⬜ | |
| Éditeur de fixtures, import QLC+/GrandMA | ⬜ | la bibliothèque QLC+ intégrée est utilisée en lecture |
| IA Lumière (audio réactif), assistant vocal/NLU | ⬜ | |
| DMX entrant (Art-Net in), manette, Stream Deck, tablette, vMix, OBS | ⬜ | |
| Comptes, licence, cloud, mises à jour automatiques | ✗ | hors périmètre |

## Choix de conception
- Pads : chaque colonne = un groupe d'appareils (1-8), chaque ligne = une couleur ; un clic applique la couleur au groupe, le voyant de ligne l'applique à tous.
- Un appareil sans mélange de couleurs (lyre à roue, gradateur) est « allumé » par la couleur choisie ; sa roue de couleur n'est pas pilotée automatiquement.
- Le canal Strobe suppose 0 = fermé/off et 16-255 = vitesse croissante : les plages réelles varient selon les appareils.
- Le Showtec DB-1-8 et le pied Stairville BLS-315 Pro sont passifs : YouStrow les documente et contrôle (sorties, limite de 32 appareils, hauteur), il ne les pilote pas.
