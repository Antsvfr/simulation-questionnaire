# État des lieux — REV-EM (2026-11-06)

**Vérifié aujourd'hui :** 8 branches distantes ; `main` = 763ad74 (08/10/2026) ; `b7773d5` = tête de `claude/lexnote-sso-launch` ; copie de `main` : 228 fichiers, 2 marqueurs « à faire » ; `.claude/CLAUDE.md` et skills présents.

**Le zip du code source n'est pas égal à `main`.** Comparé fichier par fichier : environ 20 fichiers diffèrent (dont `index.html`, `sw.js`, `ai-engine.js`, `import-center.js`, `revision-bank.js`, `output-processor.js`, `.claude/CLAUDE.md`), `macos/` et un test (`course-generation-engine.test.mjs`) n'existent que dans le zip. Le zip correspond donc à une branche de travail ou à un état local plus récent ; **laquelle n'est pas établi**. Il n'a pas été importé dans l'île : à décider avec Anton.

**Repris des dossiers, non revérifié ici :** PR en attente (#24, #26, et #25 selon l'autre dossier), cache `rev-em-v17`, tests, absence de CI.

**Limite de cette session :** copie en lecture seule de `main`. Pour travailler sur une branche, il faut attacher le dépôt en écriture.
