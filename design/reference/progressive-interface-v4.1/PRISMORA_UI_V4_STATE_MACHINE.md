# Prismora Interface v4 — source de vérité

## Principe directeur

**L’interface évolue selon ce qu’elle a à dire.**

Ce n’est pas seulement une divulgation progressive par niveau d’utilisateur. Le chrome, les menus et les contrôles gagnent de l’ampleur au fur et à mesure que Prismora reçoit du contenu mesuré.

## États du niveau Lire

### 1. État vide / arrivée

- écran calme ;
- glyphe Prismora au centre, pièce maîtresse ;
- titre et sous-titre ;
- sélecteur de modèle ;
- champ de conversation ;
- barre supérieure volontairement sobre ;
- navigation permanente : Chat, Conversations, Importer, Modèles, Réglages ;
- la fenêtre Réglages et compte peut être proposée, mais n’est jamais bloquante ;
- sortie visible : « Continuer sans clé — démo et imports ».

### 2. Conversation envoyée

- la demande utilisateur apparaît ;
- le glyphe commence à céder le centre ;
- Prismora indique que la réponse et les mesures arrivent ;
- aucune donnée J-Lens n’est inventée pendant l’attente.

### 3. Première réponse mesurée

- le glyphe se range à droite et diminue ;
- la conversation prend le centre ;
- les tokens réels deviennent cliquables ;
- le panneau J-Lens apparaît ;
- les contrôles de statut, de thème et de langue deviennent visibles dans la barre supérieure ;
- le top-8 et la trajectoire utilisent uniquement les couches réellement mesurées ;
- les trous restent des trous.

## Principe de provenance des données

Le même artifact alimente Lire, Explorer et Contrôler. Changer de profondeur ne relance pas l’analyse.

## Import Neuronpedia

Importer est présent dès le premier écran et dans tous les niveaux. Il doit accepter les anciens exports sans exiger de clé API ni de connexion réseau.

## Clés API

- jamais dans localStorage ;
- jamais dans les logs ;
- jamais dans les exports ;
- mémoire de session serveur seulement pour la première version ;
- l’interface ne reçoit qu’un état connecté / non connecté.

## Rôle de Codex

Codex ne redessine pas l’interface. Il :
- remplace les données de démonstration par les artifacts réels ;
- branche les événements et endpoints ;
- synchronise les copies web ;
- ajoute les tests ;
- conserve les états et les règles scientifiques.
