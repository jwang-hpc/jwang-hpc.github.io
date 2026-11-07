/* Pure editor model, also exercised by Node tests. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.HPDiEditorModel = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  const D = typeof module === 'object' && module.exports ? require('./design-model.js') : globalThis.HPDiDesignModel;
  const clone = value => JSON.parse(JSON.stringify(value));
  const get = (data, path) => path.reduce((value, key) => value?.[key], data);
  const canonical = value => Array.isArray(value) ? value.map(canonical) : value && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])])) : value;
  const equal = (a, b) => JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
  const validURL = value => {
    if (!value) return true;
    if (typeof value !== 'string' || /[\x00-\x1f]/.test(value)) return false;
    try { const u = new URL(value); return ['http:', 'https:'].includes(u.protocol) && !u.username && !u.password; } catch { return false; }
  };
  const label = paper => `[${paper.short.replace(/^IEEE /, '')}'${String(paper.year).slice(-2)}]`;
  const changed = (data, baseline) => Object.keys(baseline).filter(name => !equal(data[name], baseline[name]));
  function validate(data, schema, baseline) {
    const errors = [];
    if (!data || Array.isArray(data) || !equal(Object.keys(data).sort(), Object.keys(baseline).sort())) return ['Import a complete editor content package.'];
    function fields(record, definitions, prefix) {
      if (!record || typeof record !== 'object' || Array.isArray(record)) { errors.push(`${prefix}: invalid record.`); return; }
      for (const field of definitions) {
        if (field.store) continue;
        const value = record[field.key]; const name = `${prefix} — ${field.label}`;
        if (field.required && (value == null || (typeof value === 'string' && !value.trim()) || (Array.isArray(value) && !value.length))) { errors.push(`${name}: required.`); continue; }
        if (value == null) continue;
        switch (field.type) {
          case 'checkbox': if (typeof value !== 'boolean') errors.push(`${name}: expected yes/no.`); break;
          case 'number': if (!Number.isInteger(value) || value < 1900 || value > 2100) errors.push(`${name}: enter a year between 1900 and 2100.`); break;
          case 'lines': case 'paragraphs': if (!Array.isArray(value) || !value.every(x => typeof x === 'string' && x.trim())) errors.push(`${name}: enter non-empty text.`); break;
          case 'records':
            if (!Array.isArray(value) || value.length > 200) errors.push(`${name}: invalid or excessive entries.`);
            else value.forEach((item, i) => fields(item, field.fields, `${name} ${i + 1}`));
            break;
          default:
            if (typeof value !== 'string' || value.length > 20000) errors.push(`${name}: invalid text.`);
            else if (field.type === 'photo' && !/^assets\/gallery\/[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}\.jpg$/.test(value)) errors.push(`${name}: upload a photo.`);
            else if (field.type === 'paperurl' && !validURL(value) && !/^assets\/papers\/[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}\.pdf$/.test(value)) errors.push(`${name}: use an http(s) URL or upload a paper PDF.`);
            else if (field.type === 'pdf' && value !== 'assets/cv/jinzhen-wang.pdf' && !validURL(value)) errors.push(`${name}: upload a PDF.`);
            else if (field.type === 'url' && !validURL(value)) errors.push(`${name}: use a complete http(s) URL.`);
            else if (field.type === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) errors.push(`${name}: enter a valid email.`);
            else if (field.type === 'month' && !/^\d{4}-(0[1-9]|1[0-2])$/.test(value)) errors.push(`${name}: enter YYYY-MM.`);
            else if (field.type === 'select' && !field.choices.includes(value)) errors.push(`${name}: invalid choice.`);
        }
      }
    }
    for (const section of schema) {
      if (section.key === 'design') { errors.push(...D.validate(data.design,section.groups)); continue; }
      const value = get(data, section.path);
      if (section.list) {
        if (!Array.isArray(value) || value.length > 200) errors.push(`${section.label}: invalid or excessive records.`);
        else value.forEach((record, i) => fields(record, section.fields, `${section.label} ${i + 1}`));
      } else fields(value, section.fields, section.label);
    }
    for (const name of ['publications', 'projects', 'gallery']) {
      const ids = new Set();
      for (const record of Array.isArray(data[name]) ? data[name] : []) {
        const id = record?.id;
        if (typeof id !== 'string' || !/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}$/.test(id) || ids.has(id)) errors.push(`${name}: record keys must be unique.`);
        ids.add(id);
      }
    }
    for (const name of ['site', 'lab']) {
      const keys = name === 'site' ? ['navigation', 'extra_pages', 'font'] : ['navigation'];
      for (const key of keys) if (!equal(data[name]?.[key], baseline[name]?.[key])) errors.push(`${name}: navigation and design settings cannot be changed through this editor.`);
    }
    if (!Array.isArray(data.site?.student_authors) || !data.site.student_authors.every(x => typeof x === 'string' && x.trim())) errors.push('Student author names must be non-empty text.');
    return errors;
  }
  function newRecord(section) {
    const record = {};
    for (const field of section.fields) {
      if (field.store) continue;
      record[field.key] = field.type === 'checkbox' ? false : field.type === 'number' ? new Date().getFullYear() : ['records', 'lines', 'paragraphs'].includes(field.type) ? [] : field.type === 'select' ? field.choices[0] : '';
    }
    if (['publications', 'projects', 'gallery'].includes(section.key)) record.id = `${section.key === 'publications' ? 'paper' : 'project'}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    if (section.key === 'gallery') record.date = `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, '0')}`;
    if (section.key === 'news') { record.date = `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, '0')}`; record.kind = 'Paper'; }
    return record;
  }
  return {clone, get, equal, validURL, label, changed, validate, newRecord};
});
