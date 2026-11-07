# Website maintenance

This repository contains Jinzhen Wang's current academic website and HPDi Lab
at UNC Charlotte. Build only the current design; do not restore retired Classic
alternatives, Editorial, Simple or Compact demos, snapshot exports, or legacy pages.

## Source and verification

- Content is in content/*.json. build.py generates dist/, which is ignored.
- Use Python's standard library; preserve static hosting and accessibility.
- Run python3 build.py, python3 scripts/check_site.py, Python unittest discovery,
  and node --test tests/editor-model.test.cjs for editor changes.
- Preview uses the real build, including future renderer modules. Exclude Git,
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
fonts remain in use by the supported XML settings and typography preview page.
Header logos use the black/green HPDi variants in light mode and white in dark.
Sponsor logos retain proportions, with equal 240×96px boxes in three columns.
Preserve mobile layouts, theme controls, keyboard access, and team/CV dialogs.

## Editor and Git

Open with python3 edit.py. Fetch origin and fast-forward clean local-design
checkouts. Preserve saved local edits; open local files when offline or diverged.
Do not switch dirty other branches or proceed with unfinished merges.
Never merge main automatically, push main, force-push, or discard local work.
User merges local-design into main to deploy through .github/workflows/pages.yml.

The browser editor supports content only. Design changes use source edits or
scripts/design_xml.py with the supported XML schema. Arbitrary third-party XML
must be translated to that schema first.

CV uploads validate PDFs and save to assets/cv/jinzhen-wang.pdf. Publish includes
the PDF and stamps the date in America/New_York. stamp-updated.yml also stamps
manual pushes to local-design; it must never write main.

Use verified publisher DOI metadata for citations, or a pasted Scholar/IEEE/ACM
BibTeX export. Do not fabricate pages, DOI, year or conference metadata. DeepCQ
currently cites its verified arXiv preprint until publisher metadata is available.

After Publish, confirm remote receipt by fetching and checking commit ancestry, not only Git exit status. Keep pending commits on failures. The editor status panel checks on opening, periodically while visible, and on request; preserve reminders for saved/unpushed/unconfirmed work.

## Embedded design assistant exception
The owner authorized a separate Design changes section using their OpenAI API
key. Keep content forms free of design sliders. API keys may be remembered only in ignored .editor-state/openai-credentials.json
with owner-only permissions, as authorized by the owner. Never serialize keys
to status, browser storage, tracked source, previews or exports.
Use the Responses API with structured proposals. Chat/preview never mutate
source. Apply only validated design JSON and a CSS override after explicit user
action, with backups and source-revision checks. Do not execute model-generated
scripts or permit external resource imports in proposed CSS. Publish design only
to local-design and confirm receipt. Never write main. Retain content drafts.
