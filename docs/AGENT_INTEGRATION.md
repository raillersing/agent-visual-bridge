# Intégration d’un agent — contrat commun

Le bridge organise les revues et conserve les décisions. Le modèle et ses credentials restent configurés dans votre agent. Ce document est la source commune à référencer depuis les instructions du projet.

## Installer dans un projet

La version `0.3.0.dev1` n’est pas publiée. Depuis le dépôt :

```bash
pip install -e '.[mcp,setup]'
agent-bridge setup --project /chemin/projet --client gemini-cli --dry-run
agent-bridge setup --project /chemin/projet --client gemini-cli
agent-bridge doctor --project /chemin/projet --client gemini-cli --handshake
```

Clients : `codex`, `claude-code`, `cursor`, `vscode`, `gemini-cli`, `opencode`, `antigravity`, `cline`, `hermes`. L’installation utilise le Python courant et `.agent-visual-bridge/reviews.sqlite3` dans le projet. Elle ne configure aucun fournisseur, aucune confiance globale et aucune permission automatique. Les chemins sont absolus : relancer après déplacement du projet ou remplacement du Python.

Ignorer `.agent-visual-bridge/` et `.avb-runtime/` dans Git : ces fichiers contiennent des données locales et des credentials d’accès. Les configurations ne contiennent pas les clés LLM; elles peuvent être locales selon les conventions du projet.

Les éditions JSON/JSONC conservent commentaires et réglages étrangers; une modification crée une sauvegarde. TOML existant exige l’extra `setup`. Une entrée `visual-bridge` appartenant à une autre commande est refusée. `--output` permet l’export vers un autre fichier. Cline et Hermes retournent par défaut un fragment à importer manuellement; aucun fichier global n’est modifié. Le fragment Hermes utilise du JSON valide en YAML.

`doctor --handshake` teste le serveur avec le SDK officiel, sans modèle ni client commercial. Il peut créer la base vide du projet. Il ne prouve pas l’authentification du fournisseur, les capacités de l’hôte ou une inférence réussie. Un exécutable CLI absent ne signifie pas que le client graphique est absent.

## Instructions communes pour l’agent

1. Présenter une proposition avec `visual_bridge_create_review`. Distinguer information, clarification et autorisation; inclure périmètre, conséquences, dépendances et preuves.
2. Appeler `visual_bridge_open_review`. Présenter l’URL de `browser` si le client ne dispose pas d’Apps; `prefer_browser: true` force ce repli si l’interface native ne fonctionne pas. Une URL `server-loopback` concerne la machine du serveur; une machine distante exige une correspondance de ports configurée.
3. Attendre une soumission explicite. Relire `visual_bridge_get_review`, puis `visual_bridge_get_receipt` avec l’identifiant reçu. Conserver contraintes, commentaires et points en attente.
4. Ne jamais convertir commentaire, déconnexion, timeout ou `authorized: false` en permission. Une clarification ne permet pas d’exécuter des actions.
5. Réviser avec `visual_bridge_revise_review` et la révision actuelle; examiner les invalidations. Un ancien mandat ne couvre pas un nouveau périmètre.
6. Publier uniquement des résultats vérifiés. Déclarer pause/stop appliqué seulement après confirmation du moteur. Les actions hors de l’adaptateur restent sous la responsabilité de l’agent et de ses permissions natives.

Référencer ce contrat depuis AGENTS.md, CLAUDE.md ou GEMINI.md selon le client. `setup` ne remplace pas ces fichiers ni leurs règles métier.

## Navigateur indépendant de MCP

`visual_bridge_ask_human` retourne rapidement la revue et son URL. `wait: true` attend un reçu dans le même appel; choisir un `timeout` compatible avec le client. `open_browser: true` est explicite et ouvre le navigateur sur la machine du serveur.

Un superviseur détaché par base gère au plus 32 listeners de revue. L’accès expire après une heure par défaut; rouvrir renouvelle l’accès. L’expiration ferme l’accès mais conserve la revue et les reçus dans SQLite. Le superviseur s’arrête quand tous ses accès ont expiré. Ce service loopback n’est ni un transport MCP HTTP ni une authentification multi-utilisateur.

```bash
agent-bridge --db reviews.sqlite3 open REVIEW_ID
agent-bridge --db reviews.sqlite3 open REVIEW_ID --open-browser
agent-bridge --db reviews.sqlite3 browser-stop
```

`browser-stop` ferme les accès de cette base seulement. `resume` garde son comportement au premier plan. Après fermeture de l’agent ou du serveur MCP, les accès détachés restent utilisables jusqu’à expiration; une nouvelle ouverture recrée l’accès après redémarrage du superviseur.

## Agent sans MCP

```bash
agent-bridge --db reviews.sqlite3 create proposal.json
agent-bridge --db reviews.sqlite3 open REVIEW_ID
agent-bridge --db reviews.sqlite3 get REVIEW_ID
agent-bridge --db reviews.sqlite3 receipt RECEIPT_ID
```

Le SDK Python `ReviewService` fournit le même contrat. Sans navigateur accessible, utiliser les exports et imports explicitement soumis de la CLI; leur provenance reste non authentifiée. Aucun de ces parcours n’exige Codex.

## Limites actuelles

- MCP stdio par défaut; [HTTP local authentifié](MCP_HTTP.md) et [moteur JSON portable](EXECUTION.md) disponibles. Les interfaces HTTP des clients commerciaux restent à qualifier.
- SSH, WSL et conteneurs demandent un transfert de port explicite; aucun tunnel automatique n’est créé.
- Exporter une configuration ne qualifie ni le modèle ni toutes les interfaces natives.
- ERP Hospitality est migré vers `0.3.0.dev2`, avec conservation de sa base et de son travail métier. Les essais automatisés utilisent des bases séparées; le pilote humain et deux agents non Codex restent à qualifier.

## Installation existante

`setup` et `doctor` acceptent `--server-name NOM` pour conserver une ancienne entrée MCP. La fusion préserve ses permissions ciblées et les réglages étrangers; elle ne crée pas une deuxième entrée sous un autre nom. Sauvegarder SQLite avant mise à jour, conserver `AVB_DB` et vérifier la restauration sur une copie jetable.

## Client Windows et serveur dans WSL — 0.3.0.dev3

Depuis le projet dans WSL, exporter explicitement le lanceur pour un client **Windows natif** :

```bash
agent-bridge setup --project "$PWD" --client opencode --wsl-distro Ubuntu
agent-bridge setup --project "$PWD" --client antigravity --wsl-distro Ubuntu
agent-bridge doctor --project "$PWD" --client antigravity --wsl-distro Ubuntu --handshake
```

Utiliser le nom réel de la distribution. Le profil lance `wsl.exe`, sélectionne cette distribution, fixe le répertoire du projet et transmet les variables du bridge au Python Linux. Les arguments restent séparés, y compris pour les chemins contenant des espaces. Aucun tunnel, accès réseau public, réglage global ou identifiant fournisseur n’est ajouté. Un client exécuté **dans WSL** conserve le lanceur natif sans cette option.

Le diagnostic vérifie ce lanceur, et refuse un handshake lorsque la configuration installée diffère du profil sélectionné. Il ne remplace pas silencieusement une commande défaillante par le Python courant. Un handshake SDK réussi reste une preuve de transport, sans qualifier l’inférence ou l’interface commerciale.

OpenCode Zen utilise son propre fournisseur `opencode`, indépendant d’Ollama Cloud. L’essai gratuit du 6 octobre a reçu un HTTP 403; il ne qualifie pas l’offre Zen utilisée par l’utilisateur. Desktop est installé, mais le client Zen réellement authentifié reste à confirmer. Hermes a réussi la lecture réelle d’un reçu avec son fournisseur Codex; ces identifiants sont gérés par Hermes, sans export de clés dans le bridge. Antigravity reçoit un profil `.agents/mcp_config.json`; son chargement et son interface doivent être vérifiés dans la version installée.

Références : [OpenCode Zen](https://opencode.ai/docs/zen/), [Antigravity MCP](https://www.antigravity.google/docs/mcp).
