# Jinzhen Wang / HPDi Lab website

Static academic website built with Python's standard library and deployed to
GitHub Pages. There is no local editor: content and design changes are made by
editing the source (usually by asking Claude Code in a cloud session) and pushed
to the `local-design` review branch.

## How changes reach the live site

1. Edit `content/*.json` (profile, news, papers, teaching, projects, people,
   lab, gallery, sponsors) or the design sources below.
2. Check the build:

   ```bash
   python3 build.py
   python3 scripts/check_site.py
   python3 -m unittest discover -s tests
   ```

3. Commit and push to `local-design`. `stamp-updated.yml` then adds a bot commit
   that sets the "Last update" date (America/New_York); pull it before the next push.
4. Merge `local-design` into `main` (for example through a pull request).
   `.github/workflows/pages.yml` builds and deploys `dist/` from `main`.
   Settings → Pages → Source must be GitHub Actions.

Never edit generated `dist/` files; the build deletes and regenerates them.

## Source layout

- `content/*.json` — authoritative content. `content/design.json` holds design
  settings (fonts, sizes, spacing, layout, light/dark palettes), validated by `design.py`.
- `build.py` and the renderer modules (`gallery.py`, `person_cards.py`,
  `project_portfolio.py`, `news_format.py`, `publication_format.py`) generate the pages.
- `assets/` — styles, scripts, self-hosted fonts (see `assets/fonts/README.md`),
  images, CV (`assets/cv/jinzhen-wang.pdf`), paper PDFs (`assets/papers/<id>.pdf`)
  and gallery photos (`assets/gallery/`).

## Papers and citations

Each paper needs `id`, `title`, `authors`, `year`, `venue`, `short` and `links`.
Citations come from publisher-deposited Crossref metadata (`bibliography.py`)
or a pasted Google Scholar/IEEE/ACM BibTeX export in `bibtex`. The build uses
that BibTeX, then verified DOI metadata, then a minimal local fallback, and
writes `assets/publications.bib`.

### Google Scholar check (every four months)

`.github/workflows/scholar-sync.yml` runs on Jan 1, May 1 and Sep 1, and can be
run any time from Actions → "Check Google Scholar for new publications" → Run
workflow. It only runs on a schedule once it is on `main`.

- `scripts/scholar_sync.py` reads the Scholar profile linked in `content/profile.json`,
  finds papers not already on the site, and looks each up on Crossref. A paper is
  added only if Crossref has a confident title match of a journal/proceedings
  paper that lists Jinzhen Wang as an author.
- Verified papers are committed to a `scholar/…` branch and a pull request into
  `local-design` is opened, assigned to `jwang-hpc` with a review request, so
  GitHub emails you. **Merge to approve, close to reject.** Check the ID and
  venue abbreviation before merging.
- Papers that could not be verified are listed (in the PR or in an issue) for
  manual entry. Add titles to `.github/scholar-ignore.txt` to stop proposing them.
- Google Scholar blocks requests from GitHub's servers (HTTP 403). The script then
  falls back to DBLP, picking the DBLP profile that shares the most DOIs with the
  site. To use Google Scholar itself, add a `SERPAPI_KEY` repository secret
  (serpapi.com; the free tier is plenty for three runs a year).
- Pull requests opened by the workflow need Settings → Actions → General →
  "Allow GitHub Actions to create and approve pull requests". Without it, the
  workflow opens an issue with a link to create the pull request instead.
- Optional direct email: set repository secrets `SMTP_HOST`, `SMTP_PORT`
  (default 587, STARTTLS), `SMTP_USERNAME`, `SMTP_PASSWORD` and `NOTIFY_EMAIL`.

## Photos and PDFs

Gallery photos should be JPEG, metadata-stripped and at most 2000 px on the
longest side before committing. Paper PDFs and the CV are plain files in
`assets/`; keep each under 10 MB.
