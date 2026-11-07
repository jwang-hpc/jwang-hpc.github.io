#!/usr/bin/env python3
"""Find Google Scholar papers missing from content/publications.json.

Google Scholar is used only to discover candidates. Each candidate's citation
data comes from publisher-deposited Crossref metadata, and is added only when
the title matches confidently and Jinzhen Wang is a listed author. Anything
else is reported for manual entry; no publication facts are inferred.

Scholar source: the public profile page, or SerpAPI's Google Scholar Author
API when SERPAPI_KEY is set. Scholar usually blocks requests from CI servers;
the script then falls back to DBLP, choosing the DBLP author profile whose
papers overlap most with the DOIs already on the site.
"""
import argparse
import difflib
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bibliography import from_metadata  # noqa: E402

PUBLICATIONS = ROOT / 'content' / 'publications.json'
IGNORE = ROOT / '.github' / 'scholar-ignore.txt'
USER_AGENT = 'Mozilla/5.0 (compatible; HPDi-website-scholar-sync/1.0; +https://github.com/jwang-hpc/jwang-hpc.github.io)'
PAPER_TYPES = {'journal-article', 'proceedings-article', 'book-chapter'}
STOPWORDS = {'a', 'an', 'the', 'on', 'of', 'for', 'to', 'in', 'and', 'with', 'towards', 'toward', 'via', 'using', 'by', 'at', 'from', 'is', 'are'}


class ScholarBlocked(RuntimeError):
    pass


def get(url, accept='text/html', attempts=5):
    request = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': accept, 'Accept-Language': 'en'})
    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=30) as response:
                return response.read().decode('utf-8', 'replace')
        except HTTPError as error:
            # Back off on rate limits (Crossref, DBLP) but not on Scholar, which means a block.
            if error.code not in (429, 503) or 'scholar.google' in url or attempt == attempts - 1:
                raise
            retry_after = error.headers.get('Retry-After', '')
            time.sleep(min(int(retry_after), 60) if retry_after.isdigit() else 2 ** (attempt + 1))


def normalize(title):
    return re.sub(r'[^a-z0-9]+', ' ', unescape(title).lower()).strip()


def similar(a, b):
    a, b = normalize(a), normalize(b)
    return 1.0 if a == b else difflib.SequenceMatcher(None, a, b).ratio()


class ProfileParser(HTMLParser):
    """Rows of a Scholar profile table: title, authors, venue, year."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.row, self.field, self.depth = [], None, None, 0

    def handle_starttag(self, tag, attrs):
        classes = (dict(attrs).get('class') or '').split()
        if tag == 'tr' and 'gsc_a_tr' in classes:
            self.row = dict(title='', authors='', venue='', year='', grays=0)
        elif self.row is None:
            return
        elif tag == 'a' and 'gsc_a_at' in classes:
            self.field = 'title'
        elif tag == 'div' and 'gs_gray' in classes:
            self.field = 'authors' if self.row['grays'] == 0 else 'venue'
            self.row['grays'] += 1
        elif tag == 'span' and 'gs_oph' in classes:
            self.field = None  # ", 2023" appended to the venue line
        elif tag == 'span' and 'gsc_a_h' in classes:
            self.field = 'year'

    def handle_endtag(self, tag):
        if self.row is None:
            return
        if tag == 'tr':
            row = self.row
            row.pop('grays')
            row = {k: ' '.join(v.split()) for k, v in row.items()}
            if row['title']:
                self.rows.append(row)
            self.row = self.field = None
        elif tag in ('a', 'div', 'span'):
            self.field = None

    def handle_data(self, data):
        if self.row is not None and self.field:
            self.row[self.field] += data


def parse_profile(html):
    parser = ProfileParser()
    parser.feed(html)
    if not parser.rows and ('gs_captcha' in html or 'unusual traffic' in html.lower() or 'id="gsc_a_b"' not in html):
        raise ScholarBlocked('Google Scholar returned a CAPTCHA or an unexpected page instead of the profile.')
    return parser.rows


def scholar_direct(user):
    rows, start = [], 0
    while True:
        url = 'https://scholar.google.com/citations?' + urlencode(dict(user=user, hl='en', cstart=start, pagesize=100, sortby='pubdate'))
        try:
            page = parse_profile(get(url))
        except HTTPError as error:
            raise ScholarBlocked(f'Google Scholar refused the request (HTTP {error.code}).') from error
        except URLError as error:
            raise ScholarBlocked(f'Could not reach Google Scholar ({error.reason}).') from error
        rows += page
        if len(page) < 100 or start >= 900:
            return rows
        start += 100
        time.sleep(5)


def scholar_serpapi(user, key):
    rows, start = [], 0
    while True:
        try:
            body = get('https://serpapi.com/search.json?' + urlencode(dict(engine='google_scholar_author', author_id=user, hl='en', sort='pubdate', num=100, start=start, api_key=key)), 'application/json')
        except (HTTPError, URLError) as error:
            raise ScholarBlocked(f'SerpAPI request failed ({error}).') from error
        data = json.loads(body)
        if data.get('error'):
            raise ScholarBlocked('SerpAPI: ' + data['error'])
        page = data.get('articles', [])
        rows += [dict(title=a.get('title', ''), authors=a.get('authors', ''), venue=a.get('publication', ''), year=str(a.get('year', ''))) for a in page]
        if len(page) < 100 or start >= 900:
            return rows
        start += 100


def dblp_records(xml_text):
    """Formal publications in a DBLP person XML file (CoRR/informal entries skipped)."""
    rows = []
    for record in ET.fromstring(xml_text).iter('r'):
        for pub in record:
            if pub.get('publtype') in ('informal', 'withdrawn', 'edited'):
                continue
            title = ' '.join(''.join(pub.find('title').itertext()).split()).rstrip('.') if pub.find('title') is not None else ''
            dois = [e.text.split('doi.org/', 1)[1] for e in pub.findall('ee') if e.text and 'doi.org/' in e.text]
            venue = pub.findtext('journal') or pub.findtext('booktitle') or ''
            if title:
                rows.append(dict(title=title, authors=', '.join(a.text or '' for a in pub.findall('author')), venue=venue,
                                 year=pub.findtext('year') or '', doi=dois[0] if dois else ''))
    return rows


def dblp_author(name, publications):
    """Rows for the DBLP profile of `name` that shares the most DOIs with the site."""
    known = {p['doi'].lower() for p in publications if p.get('doi')}
    hits = json.loads(get('https://dblp.org/search/author/api?' + urlencode(dict(q=name, format='json', h=20)), 'application/json'))
    best = (0, None, [])
    for hit in hits['result']['hits'].get('hit', []):
        url = hit['info'].get('url', '')
        if '/pid/' not in url:
            continue
        rows = dblp_records(get(url.replace('http://', 'https://') + '.xml', 'application/xml'))
        overlap = sum(1 for r in rows if r['doi'].lower() in known)
        if overlap > best[0]:
            best = (overlap, url, rows)
        time.sleep(1)
    if best[0] < 2:
        raise ScholarBlocked(f'No DBLP profile for {name} shares at least two DOIs with the site.')
    return best[1], best[2]


def scholar_user(profile):
    user = parse_qs(urlparse(profile.get('scholar', '')).query).get('user', [''])[0]
    if not re.fullmatch(r'[\w-]{12}', user):
        raise SystemExit('content/profile.json has no Google Scholar profile URL with a user= ID.')
    return user


def is_owner(author):
    return author.get('family', '').strip().lower() == 'wang' and author.get('given', '').strip().lower().startswith('jinzhen')


def crossref_match(row, site_dois=frozenset()):
    """Return Crossref metadata for a Scholar row, or (None, reason).

    A looser match to a DOI already on the site is returned too, so the caller
    can recognise a paper that Scholar lists under a different title.
    """
    time.sleep(1)  # stay well inside Crossref's public rate limit
    if row.get('doi'):
        try:
            items = [json.loads(get('https://api.crossref.org/works/' + quote(row['doi'], safe=''), 'application/json'))['message']]
        except HTTPError as error:
            return None, f"DOI {row['doi']} is not registered with Crossref (HTTP {error.code})"
        threshold = .85  # the DOI already identifies the paper; allow small title edits
    else:
        query = urlencode({'query.bibliographic': row['title'], 'rows': 5})
        items = json.loads(get('https://api.crossref.org/works?' + query, 'application/json'))['message']['items']
        threshold = .92
    best = None
    for item in items:
        if item.get('type') not in PAPER_TYPES or not item.get('title'):
            continue
        score = similar(row['title'], item['title'][0])
        if item['DOI'].lower() in site_dois and score >= .7:
            return item, ''
        if score >= threshold and (best is None or score > best[0]):
            best = (score, item)
    if not best:
        kind = items[0].get('type') if row.get('doi') and items else ''
        return None, f"Crossref lists DOI {row['doi']} as {kind}, not a paper" if kind and kind not in PAPER_TYPES else 'no confident Crossref title match'
    item = best[1]
    if not any(is_owner(a) for a in item.get('author', [])):
        return None, f"Crossref match ({item['DOI']}) does not list Jinzhen Wang"
    dates = item.get('published-print') or item.get('published') or item.get('issued') or {}
    year = (dates.get('date-parts') or [[None]])[0][0]
    if row['year'].isdigit() and year and abs(int(row['year']) - year) > 1:
        return None, f"Crossref match ({item['DOI']}) is from {year}, Scholar says {row['year']}"
    return item, ''


def clean_venue(container):
    """Strip edition/year noise from a container title; pull a trailing (ACRONYM)."""
    venue = re.sub(r'\s+', ' ', container).strip()
    short = ''
    match = re.search(r'\s*\(([A-Z][A-Za-z0-9&\-\' ]{1,15})\)\s*$', venue)
    if match:
        short, venue = match.group(1).strip(), venue[:match.start()]
    venue = re.sub(r'^(Proceedings of (the )?)', '', venue, flags=re.I)
    venue = re.sub(r'^\d{4}\s+', '', venue)
    venue = re.sub(r'\b\d+(st|nd|rd|th)\s+', '', venue)
    venue = re.sub(r'\s+\d{4}$', '', venue).strip(' ,')
    return venue, short


def venue_fields(item, existing):
    venue, short = clean_venue((item.get('container-title') or [''])[0])
    best = max(existing, key=lambda p: similar(venue, p['venue']), default=None)
    if best and similar(venue, best['venue']) >= .9:
        return best['venue'], best['short'], True
    return venue, short or venue, False


def make_id(title, year, taken):
    words = [w for w in normalize(title).split() if w not in STOPWORDS and not w.isdigit()]
    base = (words[0] if words else 'paper')[:20] + str(year)
    candidate, n = base, 2
    while candidate in taken:
        candidate, n = f'{base}{chr(96 + n)}', n + 1
    taken.add(candidate)
    return candidate


def make_entry(item, existing, taken):
    data = from_metadata(item)
    authors = ', '.join(' '.join(filter(None, [a.get('given', '').strip(), a.get('family', '').strip()])) or a.get('name', '') for a in item.get('author', []))
    venue, short, known_venue = venue_fields(item, existing)
    title = ' '.join(unescape(re.sub(r'<[^>]+>', '', data['title'])).split())
    entry = dict(id=make_id(title, data['year'], taken), year=data['year'], title=title, authors=authors, venue=venue, short=short,
                 selected=False, links=[dict(label='DOI', url=data['url'])], doi=data['doi'], citation=data,
                 citation_source='https://api.crossref.org/works/' + data['doi'])
    return entry, known_venue


def ignored_titles():
    if not IGNORE.exists():
        return []
    return [line.strip() for line in IGNORE.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')]


def find_new(rows, publications, ignore):
    known = [p['title'] for p in publications] + ignore
    dois = {p.get('doi', '').lower() for p in publications if p.get('doi')}
    seen, new = set(), []
    for row in rows:
        key = normalize(row['title'])
        if not key or key in seen or row.get('doi', '').lower() in dois or any(similar(row['title'], t) >= .9 for t in known):
            continue
        seen.add(key)
        new.append(row)
    return new, dois


def run(rows, publications, lookup=crossref_match):
    ignore = ignored_titles()
    new, dois = find_new(rows, publications, ignore)
    taken = {p['id'] for p in publications}
    added, manual = [], []
    for row in new:
        try:
            item, reason = lookup(row, dois)
        except Exception as error:  # network or parse failure for one paper
            item, reason = None, f'Crossref lookup failed: {error}'
        if item and item['DOI'].lower() in dois:
            continue  # already on the site under a different title
        if not item:
            manual.append((row, reason))
            continue
        entry, known_venue = make_entry(item, publications + [e for e, _ in added], taken)
        dois.add(entry['doi'].lower())
        added.append((entry, known_venue))
    return added, manual


def report(added, manual, source):
    lines = [f'Checked {source} for papers missing from `content/publications.json`.', '']
    if added:
        lines += ['## Added from Crossref metadata', '',
                  'Please review each entry before merging, especially the **ID** (stays stable once published), the **venue abbreviation**, '
                  'and whether to mark it as selected. Venue names were tidied from the Crossref container title.', '']
        for entry, known_venue in added:
            flag = '' if known_venue else ' ⚠️ new venue: check name and abbreviation'
            lines.append(f"- `{entry['id']}` — {entry['title']} ({entry['short']}, {entry['year']}) · [doi:{entry['doi']}](https://doi.org/{entry['doi']}){flag}")
        lines.append('')
    if manual:
        lines += ['## Needs manual entry', '',
                  'These are on Google Scholar but could not be verified against Crossref, so they were not added. '
                  'Add them with the publisher DOI or a pasted Scholar/IEEE/ACM BibTeX export (e.g. ask Claude Code), or list their titles in '
                  '`.github/scholar-ignore.txt` to stop seeing them.', '']
        for row, reason in manual:
            lines.append(f"- **{row['title']}** — {row['venue'] or 'no venue'} ({row['year'] or 'no year'}). _{reason}_")
        lines.append('')
    return '\n'.join(lines)


def insert(publications, entries):
    for entry in entries:
        index = next((i for i, p in enumerate(publications) if p.get('year', 0) < entry['year']), len(publications))
        publications.insert(index, entry)
    return publications


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--report', type=Path, help='write a Markdown summary here')
    parser.add_argument('--github-output', type=Path, default=os.environ.get('GITHUB_OUTPUT') and Path(os.environ['GITHUB_OUTPUT']))
    parser.add_argument('--dry-run', action='store_true', help='do not modify content/publications.json')
    args = parser.parse_args()

    profile = json.loads((ROOT / 'content' / 'profile.json').read_text())
    user = scholar_user(profile)
    key = os.environ.get('SERPAPI_KEY', '').strip()
    publications = json.loads(PUBLICATIONS.read_text())
    source = 'the Google Scholar profile (via SerpAPI)' if key else 'the Google Scholar profile'
    try:
        rows = scholar_serpapi(user, key) if key else scholar_direct(user)
    except ScholarBlocked as error:
        print(f'::warning::{error} Falling back to DBLP. Add a SERPAPI_KEY repository secret to use Google Scholar via SerpAPI.', file=sys.stderr)
        try:
            url, rows = dblp_author(profile.get('name', 'Jinzhen Wang'), publications)
        except (ScholarBlocked, HTTPError, URLError, ET.ParseError, KeyError) as dblp_error:
            print(f'::error::DBLP fallback failed: {dblp_error}', file=sys.stderr)
            return 2
        source = f'DBLP ({url}), because Google Scholar blocked the request'
    if not rows:
        print('::error::No publications were returned.', file=sys.stderr)
        return 2
    added, manual = run(rows, publications)
    if added and not args.dry_run:
        PUBLICATIONS.write_text(json.dumps(insert(publications, [e for e, _ in added]), ensure_ascii=False, indent=2) + '\n')
    summary = report(added, manual, source)
    print(f'Scholar rows: {len(rows)}; added: {len(added)}; manual: {len(manual)}')
    print(summary)
    if args.report:
        args.report.write_text(summary)
    if args.github_output:
        with args.github_output.open('a') as out:
            out.write(f'added={len(added)}\nmanual={len(manual)}\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
