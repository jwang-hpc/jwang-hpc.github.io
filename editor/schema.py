"""Form definitions shared by the browser editor and local validation."""

from .design import GROUPS

CONTENT_NAMES = ('profile', 'gallery', 'news', 'publications', 'teaching', 'projects', 'people', 'lab', 'site', 'design')


def field(key, label, kind='text', required=False, **options):
    return dict(key=key, label=label, type=kind, required=required, **options)


LINKS = [field('label', 'Link label', required=True), field('url', 'URL', 'url', True)]
PROGRAMS = [field('title', 'Program / award', required=True), field('year', 'Year', 'number', True), field('url', 'URL', 'url', True)]
SECTIONS = [
    dict(key='design', label='Design', path=['design'], fields=[], groups=GROUPS),
    dict(key='profile', label='Profile', path=['profile'], fields=[
        field('name', 'Name', required=True), field('name_chinese', 'Chinese name'),
        field('role', 'Position', required=True), field('department', 'Department', required=True),
        field('university', 'University', required=True), field('email', 'Email', 'email', True),
        field('office', 'Room / location'), field('lab', 'Lab short name', required=True),
        field('lab_name', 'Lab full name', required=True), field('bio', 'Biography', 'paragraphs', True),
        field('interests', 'Research interests — one per line', 'lines', True),
        field('scholar', 'Google Scholar', 'url', True), field('cv', 'Curriculum vitae (PDF)', 'pdf', True),
        field('github', 'Lab GitHub', 'url', True), field('site_url', 'Personal site URL', 'url', True),
    ]),
    dict(key='gallery', label='Gallery', path=['gallery'], list=True, fields=[field('caption', 'Caption', required=True), field('date', 'Month', 'month', True), field('event', 'Event'), field('members', 'Featured members'), field('alt', 'Photo description (alt text)', required=True), field('image', 'Photo', 'photo', True)]),
    dict(key='news', label='News', path=['news'], list=True, fields=[
        field('date', 'Month', 'month', True), field('kind', 'Category', required=True),
        field('text', 'Announcement', 'richtext', True), field('url', 'Link', 'url'),
    ]),
    dict(key='publications', label='Papers', path=['publications'], list=True, fields=[
        field('title', 'Paper title', 'textarea', True), field('year', 'Publication year', 'number', True),
        field('short', 'Venue abbreviation', required=True), field('venue', 'Full venue name', required=True),
        field('authors', 'Authors — comma separated', 'textarea', True),
        field('doi', 'DOI (for citation lookup)'), field('bibtex', 'Publisher BibTeX', 'textarea'),
        field('note', 'Optional note', 'textarea'), field('selected', 'Mark as selected', 'checkbox'),
        field('links', 'Paper links', 'records', fields=[field('label', 'Link label', required=True), field('url', 'URL or uploaded PDF', 'paperurl', True)]),
    ]),
    dict(key='teaching', label='Teaching', path=['teaching'], list=True, fields=[
        field('code', 'Course code', required=True), field('title', 'Course title', required=True),
        field('institution', 'Institution', required=True), field('terms', 'Terms taught', required=True),
        field('description', 'Description', 'textarea'), field('url', 'Course website', 'url'),
    ]),
    dict(key='projects', label='Projects', path=['projects'], list=True, fields=[
        field('publication_ids', 'Publication IDs (one per line)', 'lines', required=False),
        field('name', 'Project name', required=True), field('subtitle', 'Subtitle', required=True),
        field('summary', 'Card introduction', 'textarea'),
        field('description', 'Description', 'textarea', True),
        field('people', 'Collaborators', 'textarea'), field('links', 'Project links', 'records', fields=LINKS),
    ]),
    dict(key='people', label='People', path=['people'], list=True, fields=[
        field('name', 'Name', required=True), field('role', 'Role', required=True),
        field('group', 'Group', 'select', True, choices=['Students', 'Alumni', 'Collaborators']),
        field('photo', 'Portrait asset', 'select', choices=['', 'people/mumenin.jpg', 'people/jiaxiang.png', 'people/raivat.jpg', 'people/aagat.jpg', 'people/adelina.jpg']),
        field('keywords', 'Research keywords (one per line)', 'lines'),
        field('bio', 'Short biography / background', 'textarea'),
        field('topic', 'Research topic', 'textarea'), field('joined', 'Joined'), field('url', 'Personal URL', 'url'),
        field('source_url', 'Profile information source', 'url'),
        field('approved', 'Show this profile on the lab page', 'checkbox'),
    ]),
    dict(key='lab', label='Lab overview', path=['lab'], fields=[
        field('mission', 'Mission', 'textarea', True), field('sponsor_thanks', 'Sponsor thank-you sentence', 'textarea'), field('recruiting', 'Joining the lab', 'textarea', True),
        field('research', 'Research themes', 'records', True, fields=[field('title', 'Theme', required=True), field('description', 'Description', 'textarea', True)]),
    ]),
    dict(key='sponsors', label='Sponsors', path=['lab', 'sponsors'], list=True, fields=[
        field('name', 'Sponsor name', required=True), field('url', 'Sponsor website', 'url', True),
        field('label', 'Short display name'),
        field('logo', 'Sponsor logo', 'select', choices=['', 'logos/nsf.png', 'logos/doe.png', 'logos/charlotte.png', 'logos/charlotte-horizontal.png'], labels=['No logo', 'NSF', 'DOE', 'UNC Charlotte (stacked)', 'UNC Charlotte (horizontal)']),
        field('programs', 'Programs / awards', 'records', fields=PROGRAMS),
    ]),
]
