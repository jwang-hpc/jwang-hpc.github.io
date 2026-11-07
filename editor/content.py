"""Content serialization and validation; the public site stays static."""
import hashlib
import json
import re
from urllib.parse import urlparse
from .schema import CONTENT_NAMES, SECTIONS
from .design import validate_design


def read_content(root):
    return {name: json.loads((root / 'content' / f'{name}.json').read_text()) for name in CONTENT_NAMES}


def revision(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def bundle(root):
    data = read_content(root)
    return dict(schema_version=1, base_revision=revision(data), content=data)


def valid_url(value):
    if not value:
        return True
    if not isinstance(value, str) or any(ord(c) < 32 for c in value):
        return False
    try:
        url = urlparse(value)
        return url.scheme in ('https', 'http') and bool(url.hostname) and not url.username and not url.password
    except ValueError:
        return False


def validate(data, baseline):
    errors = []
    if not isinstance(data, dict) or set(data) != set(CONTENT_NAMES):
        return ['The content package must include every supported section.']

    def fields(record, definitions, label):
        if not isinstance(record, dict):
            errors.append(f'{label}: expected a record.')
            return
        for item in definitions:
            if item.get('store'):
                continue
            value = record.get(item['key'])
            prefix = f"{label} — {item['label']}"
            kind = item['type']
            if item.get('required') and (value is None or (isinstance(value, str) and not value.strip()) or value == []):
                errors.append(prefix + ': required.')
                continue
            if value is None:
                continue
            if kind == 'checkbox':
                if not isinstance(value, bool): errors.append(prefix + ': expected yes/no.')
            elif kind == 'number':
                if type(value) is not int or not 1900 <= value <= 2100: errors.append(prefix + ': enter a year between 1900 and 2100.')
            elif kind in ('lines', 'paragraphs'):
                if not isinstance(value, list) or not all(isinstance(x, str) and x.strip() for x in value): errors.append(prefix + ': enter non-empty text.')
            elif kind == 'records':
                if not isinstance(value, list) or len(value) > 200: errors.append(prefix + ': too many or invalid entries.')
                else:
                    for index, child in enumerate(value): fields(child, item['fields'], f'{prefix} {index + 1}')
            elif not isinstance(value, str) or len(value) > 20000:
                errors.append(prefix + ': invalid text.')
            elif kind == 'photo' and not re.fullmatch(r'assets/gallery/[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}\.jpg', value): errors.append(prefix + ': upload a photo.')
            elif kind == 'paperurl' and not (valid_url(value) or re.fullmatch(r'assets/papers/[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}\.pdf', value)): errors.append(prefix + ': use an http(s) URL or upload a paper PDF.')
            elif kind == 'pdf' and not (value == 'assets/cv/jinzhen-wang.pdf' or valid_url(value)): errors.append(prefix + ': upload a PDF.')
            elif kind == 'url' and not valid_url(value): errors.append(prefix + ': use a complete http(s) URL.')
            elif kind == 'email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value): errors.append(prefix + ': enter a valid email.')
            elif kind == 'month' and not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', value): errors.append(prefix + ': enter YYYY-MM.')
            elif kind == 'select' and value not in item['choices']: errors.append(prefix + ': invalid choice.')

    for section in SECTIONS:
        if section['key'] == 'design':
            errors.extend(validate_design(data['design']))
            continue
        value = data
        for key in section['path']:
            value = value.get(key) if isinstance(value, dict) else None
        if section.get('list'):
            if not isinstance(value, list) or len(value) > 200:
                errors.append(section['label'] + ': invalid or excessive records.')
                continue
            for index, record in enumerate(value): fields(record, section['fields'], f"{section['label']} {index + 1}")
        else:
            fields(value, section['fields'], section['label'])
    for name in ('publications', 'projects', 'gallery'):
        ids = set()
        if isinstance(data[name], list):
            for record in data[name]:
                key = record.get('id') if isinstance(record, dict) else None
                if not isinstance(key, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}', key) or key in ids:
                    errors.append(f'{name}: record keys must be unique letters, numbers, underscores, or hyphens.')
                ids.add(key if isinstance(key, str) else '')
    for name in ('site', 'lab'):
        if not isinstance(data[name], dict):
            continue
        protected = ('navigation', 'extra_pages', 'font') if name == 'site' else ('navigation',)
        for key in protected:
            if data[name].get(key) != baseline[name].get(key): errors.append(f'{name}: navigation and design settings cannot be changed through this editor.')
    authors = data['site'].get('student_authors') if isinstance(data['site'], dict) else None
    if not isinstance(authors, list) or not all(isinstance(x, str) and x.strip() for x in authors): errors.append('Student author names must be non-empty text.')
    return errors
