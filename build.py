#!/usr/bin/env python3
"""Build the current academic website with Python's standard library."""
from news_format import render_news_text
from gallery import render_gallery
from person_cards import render_people
from project_portfolio import project_cards, project_detail
import json
import html
import shutil
from pathlib import Path
from datetime import datetime
from publication_format import publication_label
from design import token_css, validate_design

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'dist'
if OUT.exists(): shutil.rmtree(OUT)
OUT.mkdir(parents=True, exist_ok=True)
shutil.copytree(ROOT / 'assets', OUT / 'assets', dirs_exist_ok=True)
def load(name): return json.loads((ROOT / 'content' / (name+'.json')).read_text())
def e(value): return html.escape(str(value), quote=True)
profile=load('profile'); news=sorted(load('news'),key=lambda x:x['date'],reverse=True)
settings=load('site')
brand=load('brand')
design_settings=load('design')
design_errors=validate_design(design_settings)
if design_errors: raise ValueError('\n'.join(design_errors))
(OUT/'assets'/'design-tokens.css').write_text('/* Generated from content/design.json. */\n'+token_css(design_settings))
# One palette feeds both layouts, browser chrome, and the temporary favicon.
palette=design_settings['light']
dark_palette=design_settings['dark']
tokens=lambda colors: ''.join(f'--{key}:{value};' for key,value in colors.items())
(OUT/'assets'/'colors.css').write_text('/* Generated from content/design.json; original palette provenance is in brand.json. */\n:root{color-scheme:light;'+tokens(palette)+'}\n@media(prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;'+tokens(dark_palette)+'}}\nhtml[data-theme="dark"]{color-scheme:dark;'+tokens(dark_palette)+'}\n')
(OUT/'assets'/'favicon.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="8" fill="{palette["accent"]}"/><text x="32" y="43" text-anchor="middle" font-family="Georgia,serif" font-size="32" fill="{palette["paper"]}">W</text></svg>')
papers=sorted(load('publications'),key=lambda x:x['year'],reverse=True)
projects=load('projects'); teaching=load('teaching'); lab=load('lab')
people=[person for person in load('people') if person.get('approved') is True]
name_heading=e(profile['name'])+(f' <span class="chinese-name" lang="zh-Hans">{e(profile["name_chinese"])}</span>' if profile.get('name_chinese') else '')
FONTS=[('google-sans','Google Sans + system sans-serif','Current design, matching the funding tracker. Locally hosted Google Sans for headings with the system UI sans-serif for body text and navigation.'),('optima','Optima','Previous design. Uses installed Optima, with Candara and locally hosted Source Sans 3 as fallbacks.'),('source-sans','Source Sans 3','Warm, readable, understated sans-serif alternative.'),('inter','Inter','Crisp and modern, with a clean sans-serif hierarchy.'),('plex','IBM Plex Sans','A distinctive technical character, well suited to systems research.'),('serif','Source Serif 4 + Source Sans 3','Contemporary serif headings with readable sans-serif body text.'),('palatino','TeX Gyre Pagella / Palatino','Academic serif alternative. Locally hosted TeX Gyre Pagella for body and headings, with Palatino as fallback. Navigation uses Source Sans 3.')]

def link(label,url,cls=''):
    return f'<a class="{e(cls)}" href="{e(url)}">{e(label)}</a>'

def head(title,desc,design,asset):
    return f'''<!doctype html><html lang="en" data-portrait="{e(design_settings['layout']['portrait_position'])}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="{e(desc)}"><meta name="theme-color" content="{e(palette['accent'])}"><title>{e(title)}</title><link rel="icon" href="{asset}favicon.svg" type="image/svg+xml"><script src="{asset}theme.js"></script><script src="{asset}name-fonts.js" defer></script><script src="{asset}people.js" defer></script><script src="{asset}cv-preview.js" defer></script><link rel="stylesheet" href="{asset}colors.css"><link rel="stylesheet" href="{asset}style.css"><link rel="stylesheet" href="{asset}typography.css"><link rel="stylesheet" href="{asset}theme.css"><link rel="stylesheet" href="{asset}sponsors.css"><link rel="stylesheet" href="{asset}design-tokens.css"><link rel="stylesheet" href="{asset}design.css"><script src="{asset}site.js" defer></script></head><body data-design="{design}" data-font="{e(settings['font'])}"><a class="skip-link" href="#main">Skip to content</a>'''

def page(filename,title,body,design='classic',description=None,lab_page=False):
    d=OUT
    asset='assets/'
    nav=''
    for item in lab['navigation'] if lab_page else settings['navigation']:
        if item['kind']=='section':
            href=('#' if filename=='index.html' else 'index.html#')+item['target']
            nav+=f'<a class="section-nav" data-section="{e(item["target"])}" href="{e(href)}">{e(item["label"])}</a>'
        elif item['kind']=='local':
            nav+=f'<a class="section-nav" data-section="{e(item["target"])}" href="{("#" if filename=="lab.html" else "lab.html#")+e(item["target"])}">{e(item["label"])}</a>'
        else:
            nav+=f'<a href="{e(item["target"])}"'+(' aria-current="page"' if filename==item['target'] else '')+(' class="nav-lab"' if item['target']=='lab.html' else '')+f'>{e(item["label"])}</a>'
    if lab_page and not any(item.get('target') == 'gallery.html' for item in lab['navigation']): nav += '<a href="gallery.html"'+(' aria-current="page"' if filename == 'gallery.html' else '')+'>Gallery</a>'
    font_controls='<aside class="font-preview" hidden aria-label="Typography preview"><div class="font-preview-title"><strong>Compare typefaces</strong><a href="fonts.html">View samples →</a></div><div class="font-buttons">'+''.join(f'<button type="button" data-font-choice="{key}" aria-pressed="false">{e(name)}</button>' for key,name,_ in FONTS)+'</div><p id="font-description" role="status" aria-live="polite"></p></aside>'
    document_title = profile['lab'] if lab_page else (f"{profile['name']} | {profile['role'].capitalize()}, {profile['university']}" if filename == 'index.html' else f"{title} · {profile['name']}")
    s=head(document_title,description or 'Academic website of Jinzhen Wang at UNC Charlotte. Research, publications, news, and teaching.',design,asset)
    if filename == 'gallery.html': s=s.replace('</head>', '<link rel="stylesheet" href="assets/gallery.css"><script src="assets/gallery.js" defer></script></head>')
    if lab_page: s=s.replace(f'{asset}favicon.svg', f'{asset}lab-favicon.svg')
    if filename=='fonts.html': s=s.replace(f'<link rel="stylesheet" href="{asset}design.css">','')
    shell='page-shell lab-shell' if lab_page else 'page-shell single-column'
    side=''
    if lab_page:
        body=body.replace('src="__SPONSOR_ASSET__', 'src="'+asset).replace('src="__PERSON_ASSET__', 'src="'+asset)
    s+=f'''<header class="site-header"><div class="header-inner"><div class="institution-logos"><a class="hpdi-header-logo" href="{'lab.html' if lab_page else 'index.html'}" aria-label="HPDi Lab home"><img class="hpdi-logo-light" src="{asset}logos/hpdi-header-{'green' if lab_page else 'black'}.png" alt="HPDi Lab"><img class="hpdi-logo-dark" src="{asset}logos/hpdi-header-white.png" alt="HPDi Lab"></a></div><button class="menu-toggle" type="button" aria-controls="site-nav" aria-expanded="false">Menu</button><nav id="site-nav" aria-label="Main navigation">{nav}</nav><button class="theme-toggle" type="button" aria-label="Switch to dark mode" aria-pressed="false" hidden><svg class="theme-icon theme-moon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8Z"/></svg><svg class="theme-icon theme-sun" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42m0-14.14-1.42 1.42M6.35 17.65l-1.42 1.42"/></svg></button></div></header><div class="{shell}">{side}<main id="main">{font_controls}{body}</main></div><footer class="site-footer"><span>@Jinzhen Wang</span><span class="last-update">Last update: {e(profile["updated"])}</span><a href="#main">Back to top ↑</a></footer></body></html>'''
    (d/filename).write_text(s)

def section(title,content,url=None,label=None,cls='',anchor=None):
    attr=f' id="{e(anchor)}"' if anchor else ''
    return f'<section class="section {cls}"{attr}><div class="section-heading"><h2>{e(title)}</h2>{link(label or "View all →",url) if url else ""}</div>{content}</section>'

def newslist(items):
    rows=[]
    for n in items:
        date=datetime.strptime(n['date'],'%Y-%m').strftime('%b %Y')
        text=render_news_text(n['text'])
        if n.get('url'): text=f'<a href="{e(n["url"])}">{text}</a>'
        rows.append(f'<li class="news-item"><time datetime="{n["date"]}">{date}</time><div><span class="news-kind">{e(n["kind"])}</span><p>{text}</p></div></li>')
    return '<ul class="news-list">'+''.join(rows)+'</ul>'

from bibliography import citation as bib

def paperlist(items):
    rows=[]
    student_authors=set(settings.get('student_authors',[]))
    for p in items:
        author_parts=[]
        for name in p['authors'].split(', '):
            text=e(name)
            if name==profile['name']: text=f'<strong>{text}</strong>'
            if name in student_authors: text=f'<span class="student-author">{text}</span>'
            author_parts.append(text)
        authors=', '.join(author_parts)
        links=''.join(link(x['label'],x['url']) for x in p.get('links',[]))
        citation=f'<details class="citation"><summary>BibTeX</summary><pre>{e(bib(p))}</pre>{'<p>Publisher metadata not verified; citation uses the local record.</p>' if not p.get('bibtex') and not p.get('citation') else ''}<button type="button" class="copy-citation">Copy citation</button></details>'
        rows.append(f'''<article class="paper" data-year="{p['year']}"><div class="paper-venue">{e(publication_label(p))}</div><div class="paper-body"><h3>{e(p['title'])}</h3><p class="authors">{authors}</p><p class="venue-full">{e(p['venue'])}, {p['year']}</p><div class="paper-links">{links}{citation}</div>{f'<p class="paper-note">{e(p["note"])}</p>' if p.get('note') else ''}</div></article>''')
    return '<div class="paper-list">'+''.join(rows)+'</div>'

def intro(title,desc): return f'<div class="page-intro"><p class="eyebrow">HPDi Lab · UNC Charlotte</p><h1>{e(title)}</h1><p class="intro-description">{e(desc)}</p></div>'

bio=''.join('<p>'+e(p)+'</p>' for p in profile['bio'])
bio=bio.replace('High-Performance Data Intensive (HPDi) Lab','<a class="bio-lab-link" href="lab.html">High-Performance Data Intensive (HPDi) Lab</a>')
research='<ul class="research-list">'+''.join('<li>'+e(x)+'</li>' for x in profile['interests'])+'</ul>'
profile_controls=f'''<div class="profile-controls" role="region" aria-label="Profile links and contact details" tabindex="0">{link('Google Scholar',profile['scholar'],'profile-button')}{link('CV',profile['cv'],'profile-button')}{link(profile['email'],'mailto:'+profile['email'],'contact-chip')}<span class="contact-chip">{e(profile['office'])}</span></div>'''
main_intro=f'''<section class="home-intro" id="about"><div class="home-profile"><img class="portrait" src="assets/jinzhen-wang.jpg" alt="Jinzhen Wang" width="520" height="440"><div class="home-profile-details"><h1>{name_heading}</h1><p class="home-subtitle">{e(profile['role'])}</p>{profile_controls}</div></div><div class="bio">{bio}</div>{research}<p class="recruiting-inline"><strong>Prospective students</strong> · Explore {link('HPDi Lab','lab.html')} for research opportunities.</p></section>'''

author_legend=f'<p class="author-legend"><span class="student-author">Underlined</span> names are HPDi Lab students.</p>'
pubbody=intro('Publications','Research in scientific data management, compression, and high-performance systems.')+author_legend+paperlist(papers)+f'<p class="end-note">{link("Google Scholar →",profile["scholar"])}</p>'
projbody=intro('Research & projects','Efficient methods for managing and understanding scientific data at scale.')
project_content=project_cards(projects)
projbody+=project_content
projbody+=section('Research interests',research)
course_content=''
for t in teaching:
    course_content+=f'''<article class="course"><p class="eyebrow">{e(t['institution'])}</p><h3>{link(t['title'],t['url']) if t.get('url') else e(t['title'])}</h3><p class="course-code">{e(t['code'])} · {e(t['terms'])}</p>{f'<p>{e(t["description"])}</p>' if t.get('description') else ''}</article>'''
teachbody=intro('Teaching','Courses in parallel computing, computer architecture, and digital systems.')+course_content
newsbody=intro('News','Updates from our research, publications, and academic community.')
for y in sorted({n['date'][:4] for n in news},reverse=True): newsbody+=section(y,newslist([n for n in news if n['date'].startswith(y)]))
peoplebody=intro('Lab directory','Student profiles now belong to the dedicated lab page.')+link('View HPDi Lab people →','lab.html#people')
home_sections=section('News','<div class="news-scroll" role="region" aria-label="News updates" tabindex="0">'+newslist(news)+'</div>',anchor='news')
home_sections+=section('Publications',author_legend+paperlist(papers),profile['scholar'],'Google Scholar →',anchor='papers')
home_sections+=section('Teaching',course_content,anchor='teaching')
fontbody=intro('Typography options','Compare the same academic content in six typeface options. Open a full-page preview to see each font in context.')
fontbody+='<section id="chinese-fonts"><h2>Chinese name styles</h2><p>Compare 王金震 in 楷体、行楷、草书. These previews do not change the saved design.</p><div class="name-font-grid">'
for key,label,description in [('kai','楷体','Regular script · LXGW WenKai'),('xingkai','行楷','Running script · Zhi Mang Xing'),('cursive','草书','Grass script · Liu Jian Mao Cao')]:
    fontbody+=f'<article class="name-font-sample"><h3>{e(label)}</h3><p class="chinese-name" data-name-font="{key}" lang="zh-Hans">{e(profile["name_chinese"])}</p><p>{e(description)}</p>'+link('Preview on homepage →','index.html?chinese-font='+key)+'</article>'
fontbody+='</div></section>'
for key,name,desc in FONTS:
    fontbody+=f'''<section class="font-sample" data-font="{key}"><div class="font-sample-label"><span>{e(name)}</span>{link('Preview full website →','index.html?font='+key+'&preview=fonts')}</div><h2>Jinzhen Wang</h2><h3>High-performance computing & scientific data</h3><p>I lead the High-Performance Data Intensive Lab at UNC Charlotte. My research focuses on data reduction, compression, and parallel and distributed systems.</p><p class="sample-paper">DeepCQ: A Two-Stage Deep-Surrogate Framework for Lossy Compression Quality Prediction</p><p class="font-sample-description">{e(desc)}</p></section>'''
lab_about=e(lab['mission']).replace(e(profile['name']),link(profile['name'],'index.html'),1)
labbody=f'''<section class="lab-hero" id="lab-overview"><h1>{e(profile['lab'])}</h1><p class="lab-mission">{lab_about}</p></section>'''
themes='<div class="research-themes">'+''.join(f'<article><h3>{e(x["title"])}</h3><p>{e(x["description"])}</p></article>' for x in lab['research'])+'</div>'
labbody+=section('Research',themes,anchor='research')+section('Projects',project_content,anchor='projects')
directory=render_people(profile,people,'__PERSON_ASSET__')
labbody+=section('People',directory,anchor='people')
def sponsor_logo(sponsor,asset=None):
    if not sponsor.get('logo'):return ''
    prefix=asset or '__SPONSOR_ASSET__'
    return f'<a class="sponsor-logo-panel" href="{e(sponsor["url"])}"><img src="{prefix}{e(sponsor["logo"])}" alt="{e(sponsor["name"])} logo" width="240" height="96" loading="lazy"></a>'
sponsor_cards=''.join(sponsor_logo(sponsor,asset=None) for sponsor in lab.get('sponsors',[]))
labbody+=section('Sponsors','<p class="sponsor-thanks">'+e(lab['sponsor_thanks'])+'</p><div class="sponsor-grid">'+sponsor_cards+'</div>',anchor='sponsors')
page('index.html','Home',main_intro+home_sections)
page('news.html','News',newsbody)
page('publications.html','Publications',pubbody)
page('projects.html','Projects',projbody)
for project in projects:
    page('project-'+project['id']+'.html',project['name'],project_detail(project, papers),lab_page=True)
page('gallery.html','Gallery',intro('Life at HPDi','Research, shared experiences, and the people behind our work.')+render_gallery(load('gallery')),lab_page=True)
page('lab.html',profile['lab'],labbody,lab_page=True)
page('people.html','People',peoplebody)
page('teaching.html','Teaching',teachbody)
page('fonts.html','Typography options',fontbody)
for extra in settings.get('extra_pages',[]):
    content=intro(extra['title'],extra['description'])
    for item in extra.get('items',[]):
        content+=f'<article class="project"><h2>{e(item["title"])}</h2><p>{e(item["description"])}</p>'+(link('Details →',item['url']) if item.get('url') else '')+'</article>'
    page(extra['file'],extra['title'],content)
page('404.html','Page not found',intro('Page not found','This page may have moved.')+link('Return home →','index.html'))
(OUT/'.nojekyll').touch()
(OUT/'assets'/'publications.bib').write_text('\n\n'.join(bib(p) for p in papers)+'\n')
print(f'Built {len(list(OUT.rglob("*.html")))} pages, {len(papers)} papers and {len(news)} news items.')
