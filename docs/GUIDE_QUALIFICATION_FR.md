# Parcours de qualification dans notre interface

Le guide interactif pose une question à la fois pour préparer les prochains essais. Il conserve les réponses déjà envoyées et permet de laisser les autres questions pour plus tard. Les scénarios techniques ci-dessous sont une référence pour l'agent qui organise les essais. Chaque essai client crée une **revue de test distincte**. Aucune réponse du guide ne lance une exécution ni ne prouve automatiquement qu'un essai a réussi.

## Ouvrir et reprendre le guide

Depuis la racine du dépôt, Python 3.9 ou supérieur suffit :

```bash
python3 scripts/start_qualification_guide.py --open-browser
```

La commande affiche aussi l'URL locale. Dans WSL, ouvrez cette URL dans votre navigateur Windows si l'ouverture automatique ne fonctionne pas. L'accès dure 24 heures ; relancez la même commande pour le renouveler. Les décisions restent dans `reports/qualification-guide/reviews.sqlite3`. Relancer le guide conserve les réponses et les versions existantes.

Dans le guide :

1. Lire la question affichée.
2. Choisir une option ou écrire une réponse libre.
3. Cliquer **Envoyer ma réponse**. La question suivante apparaît après l'enregistrement durable.
4. Utiliser **Passer pour l'instant** pour laisser une question en attente.

**Mes réponses enregistrées** affiche les réponses soumises. Les détails restent repliés. Passer une question n'enregistre aucune réponse ; son brouillon reste dans la page jusqu'à son rechargement. Les réponses envoyées sont conservées après rechargement et relance. L'agent peut présenter une nouvelle version pour corriger une réponse ; le reçu initial est conservé. Le guide ne répond pas automatiquement à vos questions.

Cette présentation est réutilisable avec `metadata: {"presentation": "guided"}` dans une proposition composée uniquement de clarifications. Une revue comprenant une autorisation conserve l'interface complète et la prévisualisation des décisions. La vue complète reste utilisée pour les revues techniques de test décrites ci-dessous.

## Préparer un projet de test

Créer un dossier distinct du projet métier et un README contenant un titre connu. Installer le bridge dans un environnement Python dédié avec les extras `mcp,setup`, comme dans le README. Employer l'exécutable de cet environnement pour la configuration ; il doit rester disponible après le test.

Exemple avec le dossier WSL `/chemin/qualification-sandbox` et un bridge installé dans `/chemin/bridge-venv` :

```bash
/chemin/bridge-venv/bin/python -m agent_visual_bridge setup \
  --project /chemin/qualification-sandbox --client opencode --wsl-distro Ubuntu
/chemin/bridge-venv/bin/python -m agent_visual_bridge doctor \
  --project /chemin/qualification-sandbox --client opencode --wsl-distro Ubuntu --handshake
```

Remplacer les chemins et le nom de distribution par vos valeurs. L'option `--wsl-distro` s'applique à un client **Windows natif** avec Python dans WSL. Pour OpenCode exécuté dans WSL, omettre cette option. Pour Antigravity Windows, remplacer `opencode` par `antigravity`. Consulter `docs/AGENT_INTEGRATION.md` si un client doit importer son profil manuellement. Le handshake confirme le protocole ; les prompts ci-dessous vérifient l'agent réel. Ne recopier aucune clé dans la configuration du projet.

Ouvrir ce dossier dans le client et vérifier que le serveur `visual-bridge` est connecté. Employer des permissions ciblées pour les outils de revue et, si nécessaire, pour la lecture de ce seul README. Ne pas activer des permissions universelles pour contourner un refus. La base de projet créée par setup reste séparée du guide et d'ERP.

## Prompts à copier dans OpenCode ou Antigravity

### A — Créer la revue de test

```text
Nous testons Agent Visual Bridge dans ce projet de test. Ne modifie aucun fichier.
Appelle réellement visual_bridge_create_review pour créer une revue de type plan :
- readme : autorisation pour lire uniquement README.md, opération read,
  scope README.md, réversible, contraintes « Lecture seule » et « Aucune migration ».
- environment : clarification demandant le client, le fournisseur et le modèle.
- followup : seconde lecture de README.md, autorisation distincte dépendant de readme.
Ne fais encore aucune lecture ni exécution. Appelle visual_bridge_open_review
et donne-moi le review_id et l'URL pour décider dans le navigateur.
Si un outil manque ou échoue, indique précisément l'erreur ; n'invente aucun résultat.
```

Dans la revue obtenue : autoriser seulement `readme`, ajouter la remarque **Conserver l'API publique**, saisir les deux contraintes **Lecture seule** et **Aucune migration**, et laisser `followup` en attente. Répondre éventuellement à `environment`. Envoyer, confirmer et noter le reçu.

### B — Lire le reçu et respecter la décision partielle

Remplacer les deux identifiants avant envoi :

```text
Pour la revue REVIEW_ID, appelle réellement visual_bridge_get_receipt avec RECEIPT_ID.
Montre dans le résultat de l'outil la révision, les décisions, la remarque
« Conserver l'API publique » et les contraintes « Lecture seule » et « Aucune migration ».
Vérifie avec visual_bridge_get_review que le périmètre et l'autorisation sont encore actuels.
Si readme est autorisé et actuel, lis uniquement README.md et restitue son titre.
N'exécute pas followup qui est en attente. Aucune écriture, commande de migration
ou modification des permissions. En cas d'incohérence, arrête ce test et explique-la.
```

Comparer les résultats **des outils**, le fichier réel et le reçu persistant. Une phrase de l'agent affirmant respecter les contraintes ne prouve pas à elle seule que son moteur les transporte dans son entrée d'exécution.

### C — Reconnexion et nouvelle version

Fermer et rouvrir le client, puis ouvrir explicitement le même projet :

```text
Reprends uniquement le test de la revue REVIEW_ID.
Appelle visual_bridge_get_receipt pour RECEIPT_ID et visual_bridge_get_review pour REVIEW_ID.
Compare le reçu avec celui du premier essai : mêmes identifiant, révision et décisions.
Présente ensuite une nouvelle version de readme avec le périmètre README.md et SECOND.md,
sans lire SECOND.md. Conserve les autres éléments. Utilise la révision actuelle.
Relis la revue et montre que l'accord précédent sur readme a été invalidé.
N'exécute aucune action sans nouvelle autorisation.
```

Copier les IDs, erreurs éventuelles et preuves expurgées dans la carte du guide correspondant au client. Le jeu d'entrée équivalent est disponible dans `examples/qualification/client-test.json`.

## Pause et reprise : connecter un moteur coopératif

Le MCP d'un client permet de créer/lire les revues ; il ne branche pas automatiquement les appels LLM de ce client au moteur coopératif. Pour valider la pause appliquée, utiliser l'adaptateur décrit dans `docs/EXECUTION.md` et l'exemple `examples/cooperative.py` avec une base de test. Enregistrer la session, puis la sélectionner dans **Pilotage de l'agent**.

Demander **Pause** avant le prochain checkpoint, observer successivement l'état demandé puis appliqué, ajouter une contrainte et demander **Reprendre**. Comparer le reçu, l'entrée réelle d'exécution et les événements de cette même session. Une pause ne garantit pas l'interruption d'un appel LLM déjà en cours. Si aucun moteur n'est connecté, conserver ce sous-test comme non réalisé.

## ERP Hospitality

Lancer le premier essai dans le projet existant avec un **audit en lecture seule** d'un parcours métier, et demander une revue de trois constats avec preuves. Faire une décision partielle, poser une question, recharger, redémarrer le client puis vérifier le reçu et les contraintes.

Effectuer les essais d'écriture uniquement sur une copie dédiée avec une sauvegarde et un périmètre explicite. Pour vérifier une modification métier, relire l'API ou la base de cette copie après rechargement ; une notification d'interface ne suffit pas. Préserver le travail concurrent et les services existants. Renseigner la carte ERP du guide.

## Interface intégrée et pilote humain

Pour Apps, suivre la carte 5 : noter l'hôte et ses capacités, observer une vraie interface intégrée, soumettre puis vérifier le reçu après reconnexion. Si le client ouvre uniquement un navigateur, enregistrer ce résultat comme repli, sans valider Apps.

Pour le pilote, suivre `docs/PILOT.md`. Après consentement, enregistrer uniquement les observations réelles dans un fichier `observation.json` avec les champs décrits dans ce document :

```bash
agent-bridge --db /chemin/base-pilote.sqlite3 pilot-record REVIEW_ID observation.json
agent-bridge --db /chemin/base-pilote.sqlite3 pilot-report REVIEW_ID
```

Ne pas compter les essais automatisés comme des participants humains. Documenter les corrections et refaire les essais concernés. La publication stable fera l'objet d'une revue distincte présentant version, preuves et limites ; le guide ne publie rien. L'adaptateur ACP reste facultatif.

## Relire les résultats enregistrés

Depuis la racine du dépôt :

```bash
PYTHONPATH=src python3 -m agent_visual_bridge \
  --db reports/qualification-guide/reviews.sqlite3 get qualification-guide-v1
PYTHONPATH=src python3 -m agent_visual_bridge \
  --db reports/qualification-guide/reviews.sqlite3 events qualification-guide-v1
```

Ces lectures permettent à l'agent de reprendre vos réponses depuis SQLite. Aucune synchronisation automatique avec cette conversation n'est mise en place : après votre envoi, dites simplement « J'ai répondu dans le guide ».
