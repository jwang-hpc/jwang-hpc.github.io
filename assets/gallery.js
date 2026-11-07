(()=>{
  const grid=document.querySelector('.gallery-grid');if(!grid)return;
  document.documentElement.classList.add('gallery-enhanced');
  const photos=[...grid.querySelectorAll('.gallery-photo')],year=document.getElementById('gallery-year'),event=document.getElementById('gallery-event'),dialog=document.getElementById('gallery-viewer');
  let selected=0,visible=photos;
  function filter(){visible=photos.filter(photo=>{photo.hidden=!!((year.value&&photo.dataset.year!==year.value)||(event.value&&photo.dataset.event!==event.value));return !photo.hidden;});document.getElementById('gallery-count').textContent=`${visible.length} photo${visible.length===1?'':'s'}`;}
  function show(index){selected=(index+visible.length)%visible.length;const photo=visible[selected],image=photo.querySelector('img');document.getElementById('gallery-large').src=image.src;document.getElementById('gallery-large').alt=image.alt;document.getElementById('gallery-caption').textContent=photo.querySelector('figcaption').textContent;document.getElementById('gallery-prev').disabled=visible.length<2;document.getElementById('gallery-next').disabled=visible.length<2;}
  year.addEventListener('change',filter);event.addEventListener('change',filter);filter();
  photos.forEach(photo=>photo.querySelector('a').addEventListener('click',e=>{if(!dialog.showModal)return;e.preventDefault();show(visible.indexOf(photo));dialog.showModal();}));
  document.getElementById('gallery-close').addEventListener('click',()=>dialog.close());document.getElementById('gallery-prev').addEventListener('click',()=>show(selected-1));document.getElementById('gallery-next').addEventListener('click',()=>show(selected+1));dialog.addEventListener('keydown',e=>{if(e.key==='ArrowLeft'){e.preventDefault();show(selected-1);}if(e.key==='ArrowRight'){e.preventDefault();show(selected+1);}});
})();
