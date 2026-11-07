"""Shared design settings, bounded controls, and static CSS tokens."""
import copy
import math
import re

LIGHT = dict(accent='#005035', gold='#A49665', paper='#FFFFFF', ink='#252B2A', muted='#626D68', line='#DCE2DE', **{'accent-soft': '#EEF4F1'})
DARK = dict(accent='#8FB9A0', gold='#C3B387', paper='#1B1B1B', ink='#E8E4DC', muted='#B2AEA6', line='#3B3B3B', **{'accent-soft': '#262626'})
FONTS = {
    'optima': "Optima,Candara,'Source Sans 3',Arial,sans-serif",
    'palatino': "'TeX Gyre Pagella',Palatino,'Palatino Linotype',serif",
    'source-sans': "'Source Sans 3',Arial,sans-serif",
    'inter': 'Inter,Arial,sans-serif',
    'plex': "'IBM Plex Sans',Arial,sans-serif",
    'source-serif': "'Source Serif 4',Georgia,serif",
    'google-sans': "'Google Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif",
    'system': "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif",
}

def control(key, label, default, minimum=None, maximum=None, step=1, choices=None, labels=None, unit='px'):
    result = dict(key=key, label=label, default=default, required=True)
    if choices:
        result.update(type='select', choices=choices, labels=labels)
    else:
        result.update(type='range', min=minimum, max=maximum, step=step, unit=unit)
    return result

FONT_CHOICES = list(FONTS)
FONT_LABELS = ['Optima (system font)', 'TeX Gyre Pagella / Palatino', 'Source Sans 3', 'Inter', 'IBM Plex Sans', 'Source Serif 4', 'Google Sans (display)', 'System UI sans-serif']
GROUPS = [
    dict(key='typography', label='Typography', fields=[
        control('body_font', 'Body typeface', 'palatino', choices=FONT_CHOICES, labels=FONT_LABELS),
        control('heading_font', 'Heading typeface', 'palatino', choices=FONT_CHOICES, labels=FONT_LABELS),
        control('nav_font', 'Navigation typeface', 'source-sans', choices=FONT_CHOICES, labels=FONT_LABELS),
        control('body_size', 'Body and minimum text size', 16, 16, 22),
        control('heading_size', 'Main heading size', 44, 32, 60),
        control('section_size', 'Section heading size', 26, 22, 36),
        control('chinese_size', 'Chinese name size', 28, 16, 40),
        control('line_height', 'Body line height', 1.6, 1.35, 1.9, .05, unit=''),
    ]),
    dict(key='spacing', label='Spacing', fields=[
        control('paragraph_gap', 'Paragraph spacing', 12, 8, 24),
        control('section_gap', 'Section spacing', 32, 20, 64),
        control('publication_gap', 'Publication spacing', 18, 8, 32),
    ]),
    dict(key='layout', label='Layout', fields=[
        control('page_width', 'Page width', 1040, 800, 1280, 20),
        control('portrait_size', 'Portrait size', 168, 96, 240, 4),
        control('portrait_position', 'Portrait position on desktop', 'original', choices=['original', 'left', 'right'], labels=['Follow the selected layout', 'Left', 'Right']),
        control('news_height', 'Scrollable news height', 320, 180, 600, 20),
    ]),
]
COLOR_LABELS = dict(accent='Links / accent', gold='Section markers', paper='Background', ink='Body text', muted='Secondary text', line='Borders', **{'accent-soft': 'Secondary surface'})
for key, label, palette in [('light', 'Light mode colors', LIGHT), ('dark', 'Dark mode colors', DARK)]:
    GROUPS.append(dict(key=key, label=label, fields=[dict(key=name, label=COLOR_LABELS[name], type='color', required=True, default=value) for name, value in palette.items()]))
DEFAULTS = {group['key']: {field['key']: field['default'] for field in group['fields']} for group in GROUPS}

def default_design(): return copy.deepcopy(DEFAULTS)

def contrast(a, b):
    def luminance(value):
        values = [int(value[i:i+2], 16)/255 for i in (1, 3, 5)]
        values = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in values]
        return sum(v*w for v, w in zip(values, (.2126, .7152, .0722)))
    first, second = sorted([luminance(a), luminance(b)])
    return (second+.05)/(first+.05)

def validate_design(data):
    errors = []
    if not isinstance(data, dict) or set(data) != set(DEFAULTS): return ['Design: include every settings group.']
    for group in GROUPS:
        values = data.get(group['key'])
        if not isinstance(values, dict) or set(values) != set(DEFAULTS[group['key']]):
            errors.append(f"{group['label']}: include every setting."); continue
        for field in group['fields']:
            value = values[field['key']]
            label = f"{group['label']} — {field['label']}"
            if field['type'] == 'range':
                if type(value) not in (int, float) or not math.isfinite(value) or not field['min'] <= value <= field['max']:
                    errors.append(f"{label}: use {field['min']}–{field['max']}.")
                elif abs((value-field['min'])/field['step'] - round((value-field['min'])/field['step'])) > 1e-6:
                    errors.append(f"{label}: use increments of {field['step']}.")
            elif field['type'] == 'select' and value not in field['choices']:
                errors.append(f'{label}: invalid choice.')
            elif field['type'] == 'color' and (not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value)):
                errors.append(f'{label}: use a six-digit hex color.')
    if errors: return errors
    if data['typography']['chinese_size'] < data['typography']['body_size']:
        errors.append('Chinese name size must be at least the minimum text size.')
    for mode in ('light', 'dark'):
        palette = data[mode]
        for foreground in ('ink', 'muted', 'accent'):
            for background in ('paper', 'accent-soft'):
                ratio = contrast(palette[foreground], palette[background])
                if ratio < 4.5:
                    errors.append(f"{mode.title()} mode: {COLOR_LABELS[foreground]} on {COLOR_LABELS[background].lower()} has {ratio:.2f}:1 contrast; adjust to at least 4.5:1.")
    return errors

def token_css(design):
    declarations = []
    for group in GROUPS[:3]:
        for field in group['fields']:
            value = design[group['key']][field['key']]
            if field['key'] == 'portrait_position': continue
            if field['type'] == 'select': value = FONTS[value]
            elif field.get('unit') == 'px': value = f'{value:g}px'
            declarations.append(f"--d-{field['key'].replace('_','-')}:{value};")
    colors = lambda mode: ''.join(f'--{key}:{value};' for key, value in design[mode].items())
    return ':root{'+''.join(declarations)+colors('light')+'}\n@media(prefers-color-scheme:dark){:root:not([data-theme="light"]){'+colors('dark')+'}}\nhtml[data-theme="dark"]{'+colors('dark')+'}\n'
