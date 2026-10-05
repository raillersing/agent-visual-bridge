# Plan d’implémentation — Agent Visual Bridge

Date : 2 octobre 2026. Statut : implémentation locale livrée; qualification externe partielle.

## État de livraison — 2 octobre 2026

Les lots L0 à L7 et les outils de qualification L8 sont implémentés dans cette version locale. Les cases cochées indiquent une fonctionnalité ou une vérification technique livrée; elles ne prouvent pas son efficacité ergonomique auprès de participants.

- **A : livré et testé** — contrats, stockage, reçus et interfaces locales.
- **B : livré et testé** — pilotage coopératif et lecture réelle d’un reçu par Codex CLI; l’exécution extérieure au connecteur reste hors de son contrôle.
- **C : qualification technique livrée, validation produit partielle** — SDK officiel, elicitation, Apps dans un hôte de référence et repli testés. Qualification des clients commerciaux et pilote humain à réaliser.
- **L6.3 : limite de cette version** — préférences persistées et contrôles statiques traduits en anglais; les messages dynamiques restent en français.
- **L7.6 : périmètre qualifié** — client SDK stdio sans Apps et hôte Apps de référence Chromium. Aucun résultat commercial Claude Desktop/Cursor n’est revendiqué.
- **L8.2 : préparé, non exécuté** — protocole, collecte et rapports prêts; aucun participant humain inventé.
- **L8.6 : préparation livrée** — notes et artefacts vérifiés. Publication différée à une décision de diffusion.

Voir [QUALIFICATION.md](QUALIFICATION.md) pour les preuves, versions et limites; [PILOT.md](PILOT.md) pour les trois tâches d’évaluation.

L’évolution vers une installation et une qualification indépendantes de Codex est suivie dans [AGENT_AGNOSTIC_PLAN.md](AGENT_AGNOSTIC_PLAN.md), avec recherche des clients, lots et critères d’acceptation. Sa section d’avancement distingue les fonctions livrées dans 0.3.0.dev1 des qualifications et intégrations restantes.

## 1. Résultat attendu

Permettre à un développeur de comprendre une proposition, guider l’agent, autoriser des actions précises et vérifier leur résultat avec peu d’interruptions.

Trois parcours doivent être livrés de bout en bout :

1. **Question contextualisée** : l’agent expose une question et ses conséquences; l’humain répond ou diffère; l’agent reçoit fidèlement cette réponse.
2. **Plan révisable** : l’humain ajuste une proposition; l’agent présente une nouvelle version; les décisions applicables sont conservées et les points modifiés sont réexaminés.
3. **Exécution suivie** : l’agent consomme les décisions, confirme les contraintes reçues, expose sa progression et restitue résultats et preuves.

## 2. Point de départ vérifié

Le dépôt v0.1.0 contient un SDK Python, une CLI, un générateur HTML, un lecteur HTML, un serveur HTTP éphémère et une façade MCP stdio. Les 10 tests existants et Ruff passent lors de la revue locale. La CI teste Python 3.9 à 3.13; le manifeste annonce aussi Python 3.14.

Défauts observés à prendre en charge :

- Un délai serveur expiré renvoie la lecture du fichier initial.
- Le POST accepte un JSON vide et une origine étrangère; l’état du handler est partagé entre sessions.
- Une remarque sur un point en attente le classe dans les ajustements approuvés.
- Les remarques des points validés sont absentes du mandat Markdown produit par le lecteur HTML.
- La CLI ne restitue pas les consignes détaillées par défaut après soumission.
- Les identifiants sont interpolés dans les événements JavaScript inline.
- Les champs `options`, `diff`, `dependencies` et `scope` ne sont pas rendus.
- L’option MCP `type` est exposée mais ignorée; les erreurs et notifications demandent une qualification du protocole.
- Les formats des retours serveur et fichier divergent; les exports Markdown sont produits séparément en Python et en JavaScript.

## 3. Choix d’architecture

| Sujet | Choix proposé | Motif |
|---|---|---|
| Cœur | Python standard, modèles explicites et validation déterministe | Préserver un petit paquet utilisable sans dépendance d’exécution |
| État durable | SQLite via `sqlite3`, migrations versionnées et transactions | Reprendre après interruption et isoler plusieurs revues |
| Interface locale | HTML/CSS/JavaScript embarqués, sans CDN | Préserver le fonctionnement local et l’export autonome |
| MCP | Adaptateur optionnel reposant sur le SDK officiel compatible | Réduire l’entretien d’un protocole écrit à la main |
| Interfaces natives | Elicitation et MCP Apps après négociation des capacités | Adapter la présentation au client disponible |
| LLM | Fourni par l’agent appelant | Questions et révisions circulent par événements; le bridge n’exige ni fournisseur ni clé LLM |
| Source des décisions | Documents JSON validés et reçus persistés | L’HTML est une vue et un artefact d’échange |
| Contrôle d’exécution | Contrat d’adaptateur avec capacités et accusés de réception | Un bouton ne prouve pas l’arrêt ou la reprise d’un agent externe |

Modules cibles, à créer progressivement :

```text
models.py / validation.py    propositions, décisions, preuves et contrôles
store.py                    SQLite, migrations, révisions et événements
sessions.py                 cycle des revues et reçus
policy.py                   permissions explicites et motifs de sollicitation
api.py                      transport HTTP local et authentification de session
rendering/                  interfaces audit, plan, review et decision
adapters/                   contrat moteur et intégration de référence
mcp/                        outils, elicitation et interfaces MCP Apps
metrics.py                  mesures locales de l’interaction
core.py / cli.py            façades publiques et compatibilité
```

La persistance SQLite ne constitue pas une protection contre un utilisateur local qui peut modifier le fichier. Le journal sert à la traçabilité opérationnelle; aucune immutabilité cryptographique n’est revendiquée.

## 4. Contrats à stabiliser avant les interfaces

### 4.1 Proposition

- `schema_version`, `review_id`, `revision`, `project_id`, `title`, `created_at`.
- `interaction_kind` : `inform`, `clarify` ou `authorize`, indépendant du type de rendu.
- `report_type` : `audit`, `plan`, `review` ou `decision`; le type explicite prime sur la détection.
- Chaque élément possède un identifiant unique, une question concrète, une recommandation, des alternatives, les conséquences du choix et les informations manquantes.
- Les preuves indiquent leur provenance et leur nature : observation de l’agent, résultat d’un outil, déclaration humaine ou référence documentaire. Leur présence ne signifie pas qu’elles ont été vérifiées indépendamment.
- Les actions portent leur périmètre, dépendances, effet attendu et critères de réussite.
- Empreinte déterministe par élément et par proposition; les champs influençant l’autorisation sont inclus. Une preuve ou une dépendance modifiée peut nécessiter une nouvelle décision.
- Les données fournies par l’agent ne peuvent pas marquer une décision comme soumise par l’humain.

### 4.2 Décision et reçu

- `decision_kind` : `approve`, `request_changes`, `reject`, `defer`, `answer` ou `choose` selon l’interaction.
- Commentaire indépendant du statut; un commentaire seul ne vaut jamais approbation.
- `request_changes` génère une proposition à réviser; elle n’autorise pas automatiquement l’exécution des changements demandés.
- Le choix d’une option ou la confirmation d’un constat ne vaut autorisation d’exécuter que si la demande précise explicitement les actions couvertes.
- Chaque décision référence l’élément, son empreinte et sa version; le reçu conserve commentaires, contraintes, auteur déclaré et provenance du canal.
- Un reçu n’est créé qu’après soumission explicite validée. Il contient un identifiant, une date et une clé d’idempotence.
- Soumission partielle autorisée : la sortie détaille les décisions reçues et les points restant en attente.
- Aucun élément n’est préapprouvé par le rendu ou par une recommandation de l’agent; une action groupée affiche explicitement les éléments concernés avant soumission.
- Les retours CLI, SDK, HTTP et MCP partagent le même JSON canonique; le Markdown est une présentation de ce JSON.

### 4.3 États séparés

| Objet | États principaux |
|---|---|
| Revue | `draft`, `awaiting_input`, `partially_submitted`, `submitted`, `expired`, `cancelled`, `superseded` |
| Élément à décider | `pending`, puis décision explicitement soumise |
| Action externe | `not_started`, `running`, `succeeded`, `failed`, `unknown`, `skipped` |
| Contrôle d’agent | `requested`, `acknowledged`, `applied`, `rejected`, `unsupported` |

Fermer une interface, annuler une revue et arrêter un agent sont trois événements distincts. Les points en attente restent sans autorisation. Une action avec une dépendance non satisfaite reste bloquée, même si elle est approuvée individuellement.

### 4.4 API cible

API de cycle de revue : `create_review`, `get_review`, `submit_decisions`, `get_receipt`, `revise_review`, `cancel_review`.

API de collaboration : `ask_item_question`, `publish_item_reply`, `request_control`, `acknowledge_control`, `publish_progress`, `publish_result`.

Le SDK fournit ces opérations; les transports réutilisent le même service. `ask_human` devient une façade synchrone sur ce cycle. La lecture non bloquante permet à un moteur de poursuivre des tâches indépendantes.

## 5. Lots et dépendances

Les cases ci-dessous désignent des travaux à réaliser. Chaque lot inclut sa documentation et ses tests ciblés.

Les tailles S/M/L expriment une complexité relative : correction localisée, évolution de plusieurs modules, ou parcours impliquant persistance/concurrence/intégration externe. Elles ne correspondent pas à une estimation en jours.

### L0 — Corriger les défauts actuels

Prérequis : aucun. Taille relative : S.

- [x] L0.1 Retourner une expiration explicite et un code CLI distinct; ne jamais présenter un délai expiré comme un retour humain.
- [x] L0.2 Conserver tous les commentaires et leur statut exact dans JSON et Markdown; afficher les consignes complètes dans la CLI.
- [x] L0.3 Ajouter validation minimale du POST, jeton temporaire, contrôle d’origine et de Host, limites de taille et délais de lecture; isoler l’état de chaque serveur.
- [x] L0.4 Retirer les événements JavaScript inline et vérifier les identifiants dupliqués ou malformés.
- [x] L0.5 Corriger le paramètre MCP `type`, les erreurs de résultat d’outil et le traitement des notifications; vérifier aussi les sauts de ligne des exports JavaScript.

**Livrable :** version corrective utilisable avec les commandes existantes. **Critère de sortie :** les défauts reproduits ne se reproduisent plus; payload vide, requête étrangère et deux sessions concurrentes sont couverts.

### L1 — Définir les contrats communs

Prérequis : L0. Taille relative : M.

- [x] L1.1 Créer les modèles, schémas JSON et règles de validation; rejeter les données invalides avec des erreurs exploitables.
- [x] L1.2 Séparer type de rapport, intention de l’interaction, décision, commentaire et état d’exécution.
- [x] L1.3 Définir normalisation, empreintes, révisions et invalidation des décisions après changement.
- [x] L1.4 Centraliser la production des reçus et du Markdown; garantir les mêmes données sur tous les canaux.
- [x] L1.5 Définir la conversion des anciens rapports et fournir des exemples complets pour les quatre types.

**Livrable :** contrats versionnés et fixtures de référence. **Critère de sortie :** une question, un choix et une autorisation sont distingués; commentaires, contraintes et décisions partielles restent identiques après aller-retour.

### L2 — Persister les revues et permettre la reprise

Prérequis : L1. Taille relative : L.

- [x] L2.1 Implémenter SQLite, migrations, transactions, journal d’événements, droits de fichier et répertoire configurable.
- [x] L2.2 Créer le service de session et l’API non bloquante; ajouter listage, reprise, récupération du reçu et annulation à la CLI.
- [x] L2.3 Ajouter contrôle de version à la soumission, unicité des reçus et gestion des doublons; protéger contre deux onglets qui écrivent des décisions incompatibles.
- [x] L2.4 Authentifier les canaux HTTP; séparer les opérations humaines des mises à jour envoyées par l’agent; ne pas placer les secrets dans les exports.
- [x] L2.5 Exporter/importer un JSON lié à la revue; conserver la lecture HTML historique comme import de provenance déclarée, sans prétendre identifier son auteur.
- [x] L2.6 Utiliser le cycle de session depuis `ask_human` et le MCP de base; conserver la réactivité aux demandes d’état et à l’annulation.

**Livrable :** revoir maintenant, répondre plus tard, reprendre après redémarrage. **Critère de sortie :** reçu relu après redémarrage; soumission obsolète rejetée; répétition d’une soumission ne crée pas de seconde décision.

### L3 — Construire les interfaces de décision

Prérequis : L1 et L2. Taille relative : L.

- [x] L3.1 Afficher un résumé : objectif, vrais arbitrages, raison de l’interruption et conséquences de la réponse; distinguer information et action requise.
- [x] L3.2 Créer une carte de décision avec recommandation motivée, alternatives, inconnues et preuves accessibles progressivement.
- [x] L3.3 Rendre les quatre interfaces : constats d’audit; lots et dépendances de plan; diffs et vérifications de review; options de décision.
- [x] L3.4 Permettre l’édition structurée des options, du périmètre et de l’ordre; produire une demande de révision explicite.
- [x] L3.5 Ajouter soumission partielle, sélection explicite des actions, aperçu du mandat et récapitulatif des points laissés en attente.
- [x] L3.6 Isoler les brouillons par revue et version; confirmer la persistance côté serveur; différencier brouillon local et réponse soumise.
- [x] L3.7 Prévoir navigation clavier, libellés accessibles, focus visible, annonces d’état, écrans étroits et texte agrandi; éviter une dépendance à la couleur.

**Livrable :** question contextualisée et plan arbitrable. **Critère de sortie :** le navigateur affiche les champs réellement soumis; JSON persistant et état après rechargement correspondent aux choix humains.

### L4 — Converser et réviser par élément

Prérequis : L2 et L3. Taille relative : M.

- [x] L4.1 Ajouter un fil attaché à l’élément avec auteur, date et version; proposer « pourquoi ? », « preuve ? », « alternative ? » et question libre.
- [x] L4.2 Publier les demandes sous forme d’événements consommables par l’agent; permettre des réponses asynchrones et une indisponibilité explicite.
- [x] L4.3 Afficher côte à côte ou sous forme de diff les éléments modifiés entre deux propositions.
- [x] L4.4 Conserver les décisions applicables aux éléments inchangés; invalider celles affectées par une action, une contrainte ou une dépendance modifiée.
- [x] L4.5 Tracer la prise en compte de chaque correction : intégrée, à clarifier ou impossible avec explication; distinguer les faits des hypothèses.

**Livrable :** réviser un plan sans recommencer toute la revue. **Critère de sortie :** une correction humaine produit une version distincte et aucun élargissement du périmètre ne conserve une autorisation obsolète.

### L5 — Intégrer le suivi et le pilotage d’un agent

Prérequis : L2 et L4. Taille relative : L.

- [x] L5.1 Définir l’adaptateur : identité de l’exécution, capacités, réception des décisions, contraintes, événements, résultats et contrôles.
- [x] L5.2 Ajouter pause, reprise, arrêt, priorité et contrainte, avec accusé de réception et motif des commandes refusées ou indisponibles.
- [x] L5.3 Montrer actions terminées, action courante, prochain jalon, tâches indépendantes et dépendances bloquantes.
- [x] L5.4 Afficher résultat par action, vérifications, preuve, limites restantes et possibilité de demander une nouvelle revue.
- [x] L5.5 Dédupliquer les messages et reçus côté bridge; utiliser les clés d’idempotence du moteur; traiter une exécution dont le résultat est inconnu sans réessai automatique d’une action sensible.
- [x] L5.6 Fournir un adaptateur de référence déterministe pour tester le contrat, puis qualifier une intégration avec un agent réellement disponible.

**Livrable :** exécution guidée avec preuve de prise en compte. **Critère de sortie :** pause affichée comme appliquée après confirmation du moteur; une contrainte modifie réellement le travail; le résultat est relu après redémarrage. Le simulateur seul ne qualifie pas un agent réel.

### L6 — Réduire les interruptions et gérer les préférences

Prérequis : L1, L2 et L5. Taille relative : M.

- [x] L6.1 Ajouter des règles explicites par projet, catégorie d’action, périmètre, effet externe et réversibilité; préciser le motif de chaque demande humaine.
- [x] L6.2 Regrouper les questions liées, conserver les autorisations encore applicables et poursuivre les tâches indépendantes dans les moteurs qui le permettent.
- [x] L6.3 Ajouter notifications locales configurables, préférences de langue/détail et aide à la reprise après absence.
- [x] L6.4 Séparer préférences de présentation et permissions; permettre de consulter, modifier et révoquer les règles explicites; ne pas déduire une permission d’une habitude de clic.
- [x] L6.5 Tester que le moteur vérifie les règles au point d’exécution; annoncer une capacité de conseil seulement pour les moteurs sans enforcement.

**Livrable :** moins de sollicitations inutiles, périmètre des accords lisible. **Critère de sortie :** une règle de présentation ne change jamais une permission; une révocation bloque les futures actions concernées sans prétendre annuler celles déjà réalisées.

### L7 — Ajouter elicitation et MCP Apps

Prérequis : L1, L2 et L3; L4/L5 pour leurs fonctions natives. Taille relative : L.

- [x] L7.1 Choisir et verrouiller une version compatible du SDK MCP officiel dans un extra optionnel; expliciter les versions Python réellement supportées par cet extra.
- [x] L7.2 Exposer les outils de cycle de revue et leurs retours structurés; négocier protocole et capacités avec repli explicite.
- [x] L7.3 Utiliser l’elicitation pour les questions simples; distinguer réponse acceptée, refus et fermeture sans décision selon la version négociée.
- [x] L7.4 Fournir une ressource d’interface MCP Apps pour les revues riches, avec CSP, communication contrôlée et mêmes reçus que le navigateur local.
- [x] L7.5 Adapter thème et dimensions au client; maintenir HTML/JSON/texte lorsque l’interface native est indisponible.
- [x] L7.6 Qualifier un client compatible et un client sans extension; consigner leurs versions et les capacités réellement exercées.

**Livrable :** interactions natives dans les clients qualifiés. **Critère de sortie :** même décision et même reçu sur les différents canaux; fermeture, refus et absence de capacité ont un comportement testé. L’absence d’un client compatible reste un statut de qualification partielle explicite.

### L8 — Évaluer, documenter et préparer la diffusion

Prérequis : instrumentation à partir de L2; qualification finale après L3 à L7. Taille relative : M.

- [x] L8.1 Instrumenter localement délais, nombre d’interruptions, demandes d’explication, révisions, contraintes perdues et succès des reprises; définir les événements et dénominateurs.
- [ ] L8.2 Tester avec des utilisateurs des tâches comparables : une question, un plan multi-lots et une correction pendant l’exécution; recueillir compréhension et effort perçu.
- [x] L8.3 Couvrir les parcours navigateur, HTTP, processus CLI et MCP stdio; vérifier stockage et rechargement.
- [x] L8.4 Aligner matrice CI, Python annoncé, extras, installation minimale, wheel et sdist; garder les tests navigateur dans les dépendances de développement.
- [x] L8.5 Mettre à jour README, guide de migration, exemples exécutables, limites des adaptateurs et matrice des clients qualifiés.
- [ ] L8.6 Préparer les notes de version et les artefacts vérifiés; publier après qualification et décision de diffusion.

**Livrable :** résultats inspectables et paquet installable. **Critère de sortie :** les trois parcours sont démontrés; les métriques mesurent la compréhension et la fidélité des décisions, avec le taux d’approbation comme observation seulement.

## 6. Jalons de livraison

| Jalon | Lots | Résultat concret |
|---|---|---|
| A — Revue fiable | L0 à L3 | Décisions exactes, reprise durable, quatre rendus et retour complet à l’appelant |
| B — Collaboration | L4 à L6 | Questions par point, versions, commandes confirmées et intégration d’agent qualifiée |
| C — Interfaces natives et qualification | L7 et clôture L8 | Elicitation, MCP Apps, replis testés et mesures d’usage |

Ordre conseillé : L0 → L1 → L2 → L3 → L4 → L5 → L6. L7 peut démarrer après L3; l’instrumentation L8 commence avec L2. Les lots sont des unités de revue avec leurs validations, pas des dates promises. Chiffrer le calendrier après L1 et après identification du moteur et des clients disponibles.

## 7. Scénarios d’acceptation transversaux

| Scénario | Preuve attendue |
|---|---|
| Point en attente avec commentaire | Reste sans autorisation dans UI, JSON, Markdown et retour à l’agent |
| Approbation avec restriction | Restriction conservée à la lecture et confirmée par l’adaptateur |
| Requête vide, étrangère ou identifiants inconnus | Erreur contrôlée; revue toujours ouverte; aucun reçu créé |
| Absence de réponse et fermeture | Expiration/fermeture explicite; aucune action nouvellement autorisée |
| Soumission partielle avec dépendances | Actions indépendantes autorisées poursuivies; dépendances non satisfaites bloquées |
| Deux onglets et deux revues | Pas de mélange de brouillons, commentaires, reçus ou contrôles |
| Redémarrage entre réponse et récupération | Même reçu récupéré; livraison répétée dédupliquée |
| Changement du périmètre ou d’une dépendance | Nouvelle version; décision affectée invalidée; changement visible |
| Révision sans changement d’action | Décisions applicables conservées; seules les différences utiles sont présentées |
| Question et réponse asynchrones | Auteur/version conservés; reprise après interruption sans perdre le fil |
| Pause demandée pendant une action | État demandé puis confirmé; action déjà terminée signalée honnêtement |
| Résultat externe inconnu | État `unknown`; rapprochement avant toute relance susceptible de doubler l’effet |
| HTML exporté et JSON importé | Pas de secret exporté; version contrôlée; provenance d’import explicite |
| Affichage natif indisponible | Repli utilisable avec décisions et contraintes identiques |
| Clavier, petit écran, texte agrandi | Actions accessibles; contenu et contrôle principal lisibles |

### Mesures du pilote

| Mesure | Définition |
|---|---|
| Temps de décision | Temps actif entre ouverture et réponse explicite, avec périodes d’absence séparées; médiane et 90e percentile |
| Interruptions | Nombre de sollicitations nécessitant une réponse par tâche terminée; comparer des tâches de portée équivalente |
| Compréhension | Proportion des décisions pour lesquelles le participant décrit correctement l’effet et le périmètre autorisés |
| Fidélité | Nombre de décisions, commentaires ou contraintes altérés/perdus entre soumission, reçu et consommation par l’agent |
| Reprise | Proportion de reprises réussies parmi les reprises tentées, en séparant interruption du bridge et interruption du moteur |

Comparer le parcours terminal actuel au nouveau parcours sur des tâches comparables. Chercher une baisse du temps actif et des interruptions sans dégrader compréhension ou fidélité. Les scénarios déterministes exigent zéro décision perdue et zéro action nouvellement autorisée par une absence de réponse. Les mesures restent locales et exportables volontairement; les métriques n’enregistrent pas le contenu des consignes par défaut.

## 8. Compatibilité et décisions à vérifier pendant l’implémentation

- Conserver `auto`, `read`, `watch`, `serve` et `ask_human` avec documentation des corrections de sémantique. Les sorties JSON nouvelles portent une version; les conversions historiques ont leurs tests.
- Le mode `watch` historique doit vérifier une soumission explicite au lieu de considérer toute modification de fichier comme un accord. Expliquer que le navigateur télécharge un artefact et ne remplace pas nécessairement le fichier surveillé.
- La normalisation préserve les données utiles et signale les champs non pris en charge; un type inconnu ne doit pas produire silencieusement une revue vide.
- Retenir un agent et un client MCP disponibles pour la qualification des lots L5/L7. Ce choix ne bloque pas les contrats, la persistance ou l’interface locale.
- Mesurer les besoins avant d’ajouter collaboration multi-utilisateur, hébergement distant ou éditeur de workflow généraliste. Ces extensions restent des décisions distinctes.
- Aucun accès réseau ou stockage de secrets n’est nécessaire pour consulter un rapport local; documenter les effets propres à chaque intégration optionnelle.

## 9. Références de conception

Ces sources ont été consultées pour la revue. Les choix précis de ce plan sont des propositions adaptées au dépôt; leur efficacité doit être mesurée sur les parcours réels.

- [Microsoft — Guidelines for human-AI interaction](https://www.microsoft.com/en-us/research/blog/guidelines-for-human-ai-interaction-design/) : contexte pertinent, correction, conséquences et contrôle utilisateur.
- [Anthropic — Trustworthy agents in practice](https://www.anthropic.com/research/trustworthy-agents) : arbitrage du plan et intervention pendant l’exécution.
- [Anthropic — Claude Code auto mode, mars 2026](https://www.anthropic.com/engineering/claude-code-auto-mode) : fatigue d’approbation et limites de l’automatisation des permissions.
- [LangChain — Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop) : décisions explicites, persistance et reprise.
- [MCP — Elicitation, spécification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation) : capacités négociées, acceptation, refus et annulation; vérifier la version cible à L7.
- [MCP Apps — Overview](https://apps.extensions.modelcontextprotocol.io/api/documents/overview.html) : interfaces intégrées, échanges et repli progressif.
- [Human oversight of agentic systems in practice, juin 2026](https://arxiv.org/abs/2606.05391) : étude exploratoire auprès de 17 développeurs sur les différentes formes de supervision.
