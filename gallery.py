"""Static photo grid with progressive enhancement for filters and viewing."""
from html import escape as e
from datetime import datetime


def render_gallery(records):
    photos = sorted(records, key=lambda p: p['date'], reverse=True)
    if not photos:
        return '<p class="gallery-empty">Photos from our lab community will appear here.</p>'
    years = sorted({p['date'][:4] for p in photos}, reverse=True)
    events = sorted({p.get('event', '') for p in photos} - {''})
    body = '<div class="gallery-filters"><label>Year <select id="gallery-year"><option value="">All years</option>'
    body += ''.join(f'<option>{e(y)}</option>' for y in years) + '</select></label><label>Event <select id="gallery-event"><option value="">All events</option>'
    body += ''.join(f'<option>{e(event)}</option>' for event in events) + '</select></label></div><p id="gallery-count" role="status"></p><div class="gallery-grid">'
    for p in photos:
        date = datetime.strptime(p['date'], '%Y-%m').strftime('%B %Y')
        caption = p['caption']
        body += f'<figure class="gallery-photo" data-year="{e(p["date"][:4])}" data-event="{e(p.get("event", ""))}"><a class="gallery-open" href="{e(p["image"])}"><img src="{e(p["image"])}" alt="{e(p["alt"])}" loading="lazy"></a><figcaption><strong>{e(caption)}</strong><p>{e(date)}'+(' · '+e(p['event']) if p.get('event') else '')+'</p>'
        if p.get('members'): body += '<p>'+e(p['members'])+'</p>'
        body += '</figcaption></figure>'
    return body + '</div><dialog id="gallery-viewer" aria-label="Photo viewer"><button id="gallery-close" type="button">Close ×</button><img id="gallery-large" alt=""><p id="gallery-caption"></p><div class="gallery-viewer-controls"><button id="gallery-prev" type="button">← Previous</button><button id="gallery-next" type="button">Next →</button></div></dialog>'
