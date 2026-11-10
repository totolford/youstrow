# Interface ↔ Figma

L'interface de YouStrow est conçue dans Figma : **https://www.figma.com/design/Uni1cGyBPbIOogpQyuc17g** (fichier « YouStrow — UI »).
Vous modifiez la maquette dans Figma ; on ré-importe ensuite dans le code (variables, composants, écrans) — le moteur DMX n'est jamais concerné.

## Contenu du fichier Figma
| Page | Contenu |
|---|---|
| **Foundations** | variables `YouStrow/Tokens` (17 couleurs, rayons, espacements) et 7 styles de texte (`type/*`) |
| **Components** | Button (Primary/Secondary/Danger/Ghost), Status chip, Tab, Nav item, Pad, Fader, Section header, Scene card, Playlist row, 18 icônes `icon/*` |
| **Screens** | Live · Plan 3D · Média · Patch & Rig · Surface EXT |

## Correspondance maquette → code
| Figma | Code |
|---|---|
| variables `surface/*`, `border/*`, `text/*`, `accent/*`, `status/*`, `radius/*` | `youstrow/ui/theme.py` (constantes + feuille de style) |
| `Button`, `Status chip`, `Tab` | `QPushButton` (`objectName` : `primary`, `danger`, `ghost`), pastilles de `main_window._update_chips`, `QTabBar` |
| `Nav item`, rail + barre supérieure | `main_window._build_rail`, `_build_topbar` |
| `Pad`, grille de mémoires | `ui/memory_pads.py` (`PadSurface`) |
| `Fader`, curseurs dégradés | `ui/widgets.py` (`Fader`, `GradientSlider`) |
| `Scene card` | `ui/plan3d.py` (`SceneCard`) |
| `Playlist row`, carte « Sortie vidéo » | `ui/media_panel.py` |
| écran **Live** | `main_window._build_live` |
| écran **Plan 3D** | `ui/plan3d.py` (`Plan3DPanel`) |
| écran **Média** | `ui/media_panel.py` |
| écran **Patch & Rig** | `ui/patch_view.py` + `ui/rig_panel.py` |
| écran **Surface EXT** | `ui/ext_surface.py` |
| icônes `icon/*` | `ui/icons.py` (mêmes tracés SVG) |

## Procédure de ré-importation
1. Modifier le fichier dans Figma (couleurs = variables ; mises en page = écrans).
2. Dire « ré-importe le Figma » : je relis les variables (`get_variable_defs`) et les écrans (`get_design_context`), régénère `theme.py` et ajuste les mises en page Qt concernées, puis relance les tests et la capture d'écran de comparaison.

## À savoir
- **Pas encore dans Figma** : les dialogues (Sortie DMX, MIDI, choix de l'écran plein écran, éditeur d'effet), le menu Affichage et les fenêtres détachées. Ils existent dans le code avec le même thème ; ils seront ajoutés à Figma dès que la limite d'appels du plan gratuit Figma le permettra.
- Le plan gratuit de Figma limite à 3 pages et un nombre d'appels API : c'est pourquoi tout est regroupé dans 3 pages.
