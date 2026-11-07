document.documentElement.classList.add('js');
const menu=document.querySelector('.menu-toggle'), nav=document.querySelector('#site-nav');
menu?.addEventListener('click',()=>{const open=menu.getAttribute('aria-expanded')!=='true';menu.setAttribute('aria-expanded',String(open));nav.classList.toggle('is-open',open);});
nav?.addEventListener('click',event=>{if(event.target.closest('a')&&window.matchMedia('(max-width:700px)').matches){menu.setAttribute('aria-expanded','false');nav.classList.remove('is-open');}});
const fontDescriptions={
 'google-sans':'Google Sans headings with system sans-serif body text: current design, matching the funding tracker.',
 optima:'Optima: previous design for body and headings. Uses installed Optima, with Candara and Source Sans 3 as fallbacks.',
 'source-sans':'Source Sans 3: warm, readable, understated sans-serif alternative.',
 inter:'Inter: crisp and modern, with a clean sans-serif hierarchy.',
 plex:'IBM Plex Sans: a distinctive technical character for systems research.',
 serif:'Source Serif 4 headings with Source Sans 3 body text: contemporary academic typography.',
 palatino:'TeX Gyre Pagella / Palatino: academic serif alternative, with locally hosted Pagella for headings and body and Source Sans 3 for navigation.'
};
const params=new URLSearchParams(location.search);
const fontPreview=document.querySelector('.font-preview');
if(params.get('preview')==='fonts'&&fontPreview)fontPreview.hidden=false;
function applyFont(font){
 if(!Object.hasOwn(fontDescriptions,font))return;
 document.body.dataset.font=font;
 if(params.has('font')||params.get('preview')==='fonts'){
  const families={'google-sans':"'Google Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif",system:"-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif",optima:"Optima,Candara,'Source Sans 3',Arial,sans-serif",'source-sans':"'Source Sans 3',Arial,sans-serif",inter:'Inter,Arial,sans-serif',plex:"'IBM Plex Sans',Arial,sans-serif",serif:"'Source Serif 4',Georgia,serif",palatino:"'TeX Gyre Pagella',Palatino,serif"};
  document.body.style.setProperty('--d-body-font',families[font==='serif'?'source-sans':font==='google-sans'?'system':font]);
  document.body.style.setProperty('--d-heading-font',families[font]);
 }
 document.querySelectorAll('[data-font-choice]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.fontChoice===font)));
 const description=document.querySelector('#font-description');if(description)description.textContent=fontDescriptions[font];
 if(params.has('font')||params.get('preview')==='fonts')document.querySelectorAll('a[href]').forEach(a=>{const raw=a.getAttribute('href');if(raw.startsWith('#')||a.closest('.font-sample-label'))return;const url=new URL(raw,location.href);if(url.origin!==location.origin||!url.pathname.endsWith('.html'))return;url.searchParams.set('font',font);if(params.get('preview')==='fonts')url.searchParams.set('preview','fonts');a.setAttribute('href',url.pathname+url.search+url.hash);});
}
applyFont(params.get('font')||document.body.dataset.font);
document.querySelectorAll('[data-font-choice]').forEach(button=>button.addEventListener('click',()=>{const font=button.dataset.fontChoice;const url=new URL(location.href);url.searchParams.set('font',font);history.replaceState(null,'',url);applyFont(font);}));
if('IntersectionObserver' in window){
 const sectionLinks=[...document.querySelectorAll('.section-nav')];
 const observer=new IntersectionObserver(entries=>{for(const entry of entries){if(!entry.isIntersecting)continue;for(const a of sectionLinks){if(a.dataset.section===entry.target.id)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current');}}},{rootMargin:'-100px 0px -65% 0px',threshold:0});
 sectionLinks.forEach(a=>{const s=document.getElementById(a.dataset.section);if(s)observer.observe(s);});
}
document.querySelectorAll('.copy-citation').forEach(button=>button.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(button.previousElementSibling.textContent);button.textContent='Copied';setTimeout(()=>button.textContent='Copy citation',1800);}catch{button.textContent='Select the citation text to copy';}}));
