#!/usr/bin/env python3
"""Verify content and local links without installing dependencies."""
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT=Path(__file__).resolve().parents[1]
errors=[]
def fail(message): errors.append(message)
def read(name):
    try: return json.loads((ROOT/'content'/f'{name}.json').read_text())
    except Exception as ex: fail(f'{name}: {ex}'); return []

pubs=read('publications'); seen=set()
settings=read('site')
if settings.get('font') not in ['google-sans','optima','source-sans','inter','plex','serif','palatino']: fail('Unknown default font preset')
for item in settings.get('navigation',[]):
    if item.get('kind') not in ['section','page'] or not item.get('label') or not item.get('target'): fail(f'Invalid navigation item: {item}')
for p in pubs:
    for key in ['id','title','authors','year','venue','short','links']:
        if key not in p: fail(f'Publication missing {key}: {p.get("id","unknown")}')
    if p['id'] in seen: fail(f'Duplicate publication ID: {p["id"]}')
    seen.add(p['id'])
    if not isinstance(p['year'],int): fail(f'Year must be an integer: {p["id"]}')
for n in read('news'):
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',n.get('date','')): fail(f'Invalid news date: {n}')
    if not n.get('text'): fail('Empty news entry')

class Page(HTMLParser):
    def __init__(self): super().__init__(); self.refs=[]; self.ids=set(); self.h1=0; self.lang=False; self.title=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if a.get('id'):
            if a['id'] in self.ids: fail(f'Duplicate HTML ID {a["id"]}')
            self.ids.add(a['id'])
        if tag=='h1': self.h1+=1
        if tag=='html': self.lang=bool(a.get('lang'))
        if tag=='title': self.title=True
        for key in ['href','src']:
            if key in a: self.refs.append(a[key])
        if tag=='img' and 'alt' not in a: fail('Image missing alt attribute')

pages={}
for path in sorted((ROOT/'dist').rglob('*.html')):
    parser=Page();parser.feed(path.read_text());pages[path.resolve()]=parser
    if parser.h1!=1: fail(f'{path.name}: expected one h1, got {parser.h1}')
    if not parser.lang or not parser.title: fail(f'{path.name}: missing language or title')
for path,parser in pages.items():
    for ref in parser.refs:
        u=urlparse(ref)
        if u.scheme or u.netloc: continue
        target=(path.parent/unquote(u.path)).resolve() if u.path else path
        if target.is_dir(): target=target/'index.html'
        if not target.exists(): fail(f'{path.relative_to(ROOT)}: missing local target {ref}')
        if u.fragment and target in pages and unquote(u.fragment) not in pages[target].ids:
            fail(f'{path.relative_to(ROOT)}: missing anchor {ref}')
if not pages: fail('No built pages. Run python3 build.py first.')
for css in (ROOT/'dist'/'assets').glob('*.css'):
    for ref in re.findall(r'url\([\'\"]?([^\)\'\"]+)',css.read_text()):
        if not urlparse(ref).scheme and not (css.parent/ref).exists(): fail(f'Missing CSS asset: {ref}')
if errors:
    print('\n'.join(errors));raise SystemExit(1)
print(f'Checked {len(pages)} pages, {len(pubs)} publications, news dates, page metadata, image alt text, and local links.')
