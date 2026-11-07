# Website maintenance

This repository contains Jinzhen Wang's current academic website and HPDi Lab
at UNC Charlotte. Build only the current design; do not restore retired Classic
alternatives, Editorial, Simple or Compact demos, snapshot exports, or legacy pages.

## Source and verification

- Content is in content/*.json. build.py generates dist/, which is ignored.
- Use Python's standard library; preserve static hosting and accessibility.
- Run python3 build.py, python3 scripts/check_site.py and Python unittest discovery.
- Preview with the real build (python3 -m http.server -d dist). Exclude Git,
  credentials, generated output and local state from temporary preview sources.
- Never infer student or publication facts. Publication/project IDs stay stable.

## Design

Preserve the single reading column, portrait/name/position group, Scholar and CV
buttons, and email/office chips. Main page sections are About, News, Publications,
and Teaching. News scrolls; it is not folded and is not repeated on Lab.
The Lab page contains research, projects, students, and sponsors. Do not restore
Education, Professional Service, redundant PI links or the removed tagline.

Use the Charlotte light palette and neutral charcoal dark palette in
content/design.json. Keep text at least as large as News (16px). Typography
matches the funding tracker: locally hosted Google Sans (weight 400) for h1–h4,
and the system UI sans-serif stack for body and navigation. The Chinese
name 王金震 uses 行楷 with its local subset; preserve font licenses. Other local
fonts remain in use by the design settings and typography preview page.
Header logos use the black/green HPDi variants in light mode and white in dark.
Sponsor logos retain proportions, with equal 240×96px boxes in three columns.
Preserve mobile layouts, theme controls, keyboard access, and team/CV dialogs.

## Workflow and Git

There is no local editor; the owner works through Claude Code sessions. Edit
content/*.json and source files directly, build and test, then commit and push
to local-design. Never merge or push main, force-push, or discard work; the owner
merges local-design into main to deploy through .github/workflows/pages.yml.
After pushing, confirm receipt by fetching and checking commit ancestry, not only
Git exit status. stamp-updated.yml stamps the update date on local-design pushes
(a bot commit follows yours); it must never write main.

Design settings live in content/design.json (validated by design.py, which also
generates the design tokens). Styling changes go in assets/*.css.

The CV lives at assets/cv/jinzhen-wang.pdf, paper PDFs at assets/papers/<id>.pdf.
Gallery photos go in assets/gallery/ as metadata-stripped JPEGs, at most 2000 px.

## Citations and Google Scholar

Use verified publisher DOI metadata for citations, or a pasted Scholar/IEEE/ACM
BibTeX export. Do not fabricate pages, DOI, year or conference metadata. DeepCQ
currently cites its verified arXiv preprint until publisher metadata is available.

.github/workflows/scholar-sync.yml (every four months) uses Google Scholar only to
discover candidates. It adds a paper only with a confident Crossref match that
lists Jinzhen Wang, and opens a PR into local-design for the owner to approve;
unverified papers are reported for manual entry. Titles to skip go in
.github/scholar-ignore.txt.
