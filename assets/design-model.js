/* Shared design model: no DOM, dependencies, or executable user CSS. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.HPDiDesignModel=api;})(globalThis,function(){
  const fonts={optima:"Optima,Candara,'Source Sans 3',Arial,sans-serif",palatino:"'TeX Gyre Pagella',Palatino,'Palatino Linotype',serif",'source-sans':"'Source Sans 3',Arial,sans-serif",inter:'Inter,Arial,sans-serif',plex:"'IBM Plex Sans',Arial,sans-serif",'source-serif':"'Source Serif 4',Georgia,serif",'google-sans':"'Google Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif",system:"-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif"};
  function contrast(a,b){
    const luminance=hex=>{const rgb=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;};
    const [low,high]=[luminance(a),luminance(b)].sort((a,b)=>a-b);return(high+.05)/(low+.05);
  }
  function validate(data,groups){
    const errors=[];
    const sameKeys=(object,keys)=>object&&typeof object==='object'&&!Array.isArray(object)&&JSON.stringify(Object.keys(object).sort())===JSON.stringify([...keys].sort());
    if(!sameKeys(data,groups.map(g=>g.key)))return['Design: include every settings group.'];
    for(const group of groups){
      const values=data[group.key];
      if(!sameKeys(values,group.fields.map(f=>f.key))){errors.push(`${group.label}: include every setting.`);continue;}
      for(const field of group.fields){
        const value=values[field.key],label=`${group.label} — ${field.label}`;
        if(field.type==='range'){
          if(typeof value!=='number'||!Number.isFinite(value)||value<field.min||value>field.max)errors.push(`${label}: use ${field.min}–${field.max}.`);
          else if(Math.abs((value-field.min)/field.step-Math.round((value-field.min)/field.step))>1e-6)errors.push(`${label}: use increments of ${field.step}.`);
        }else if(field.type==='select'&&!field.choices.includes(value))errors.push(`${label}: invalid choice.`);
        else if(field.type==='color'&&(typeof value!=='string'||!/^#[0-9a-f]{6}$/i.test(value)))errors.push(`${label}: use a six-digit hex color.`);
      }
    }
    if(errors.length)return errors;
    if(data.typography.chinese_size<data.typography.body_size)errors.push('Chinese name size must be at least the minimum text size.');
    for(const mode of ['light','dark'])for(const foreground of ['ink','muted','accent'])for(const background of ['paper','accent-soft']){
      const ratio=contrast(data[mode][foreground],data[mode][background]);
      if(ratio<4.5){const fields=groups.find(g=>g.key===mode).fields;errors.push(`${mode==='light'?'Light':'Dark'} mode: ${fields.find(f=>f.key===foreground).label} on ${fields.find(f=>f.key===background).label.toLowerCase()} has ${ratio.toFixed(2)}:1 contrast; adjust to at least 4.5:1.`);}
    }
    return errors;
  }
  function css(data,groups){
    const errors=validate(data,groups);if(errors.length)throw new Error(errors[0]);
    const declarations=[];
    for(const group of groups.slice(0,3))for(const field of group.fields){
      if(field.key==='portrait_position')continue;
      let value=data[group.key][field.key];
      if(field.type==='select')value=fonts[value];else if(field.unit==='px')value=`${value}px`;
      declarations.push(`--d-${field.key.replaceAll('_','-')}:${value};`);
    }
    const colors=mode=>Object.entries(data[mode]).map(([key,value])=>`--${key}:${value};`).join('');
    return`:root{${declarations.join('')}${colors('light')}}\n@media(prefers-color-scheme:dark){:root:not([data-theme="light"]){${colors('dark')}}}\nhtml[data-theme="dark"]{${colors('dark')}}\n`;
  }
  return {validate,css,contrast};
});
