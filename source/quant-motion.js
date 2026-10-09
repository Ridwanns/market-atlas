// Replay retained observations and seeded scenario paths. No fits or random draws here.
(function(){
 'use strict';
 const get=id=>document.getElementById(id),ns='http://www.w3.org/2000/svg';
 const reduced=matchMedia('(prefers-reduced-motion: reduce)');
 let tracks=[],progress=1,playing=false,frame=0,last=0,bound=false;
 const clamp=v=>Math.max(0,Math.min(1,v));
 function paint(){
  const labels=tracks.map(track=>track.update(progress));
  get('quant-progress').value=Math.round(progress*1000);
  get('quant-motion-status').textContent=labels[0]||'No retained observations';
  get('quant-play').textContent=playing?'Ⅱ Pause':progress===1?'↻ Replay':'▶ Play';
  get('quant-play').setAttribute('aria-pressed',String(playing));
  get('quant-workspace').dataset.motion=playing?'playing':'paused';
 }
 function pause(){playing=false;cancelAnimationFrame(frame);last=0;if(bound)paint()}
 function tick(now){
  if(!playing)return;
  if(get('quant-workspace').hidden||document.hidden){pause();return}
  if(last)progress=clamp(progress+(now-last)/8000*Number(get('quant-speed').value));
  last=now;if(progress===1)playing=false;paint();
  if(playing)frame=requestAnimationFrame(tick);else last=0;
 }
 function play(){if(!tracks.length)return;if(progress===1)progress=0;playing=true;last=0;paint();frame=requestAnimationFrame(tick)}
 function bind(){
  if(bound)return;bound=true;
  get('quant-play').addEventListener('click',()=>playing?pause():play());
  get('quant-restart').addEventListener('click',()=>{pause();progress=0;paint()});
  get('quant-progress').addEventListener('input',e=>{const position=Number(e.target.value)/1000;pause();progress=clamp(position);paint()});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)pause()});
  new MutationObserver(()=>{if(get('quant-workspace').hidden)pause()}).observe(get('quant-workspace'),{attributes:true,attributeFilter:['hidden']});
  reduced.addEventListener('change',e=>{if(e.matches){pause();progress=1;paint()}});
 }
 function clip(id){
  const el=get(id),svg=el.querySelector('svg'),defs=document.createElementNS(ns,'defs'),path=document.createElementNS(ns,'clipPath'),rect=document.createElementNS(ns,'rect');
  const box=svg.viewBox.baseVal;path.id=id+'-motion-clip';path.setAttribute('clipPathUnits','userSpaceOnUse');rect.setAttribute('x','0');rect.setAttribute('y','0');rect.setAttribute('height',box.height);rect.setAttribute('width',box.width);path.append(rect);defs.append(path);svg.append(defs);
  svg.querySelectorAll('.q-line,.q-marker,.q-path,.q-band').forEach(mark=>mark.setAttribute('clip-path','url(#'+path.id+')'));
  const cursor=document.createElementNS(ns,'line');cursor.setAttribute('class','q-cursor q-motion-cursor');cursor.setAttribute('y1','16');cursor.setAttribute('y2',box.height-34);svg.append(cursor);
  const caption=document.createElement('div');caption.className='quant-replay-date';caption.setAttribute('aria-live','off');el.append(caption);
  return{rect,cursor,caption};
 }
 window.quantMotion={
  begin(){bind();pause();tracks=[];progress=1},
  line(id,series,start,end,x,format){
   const c=clip(id),first=series[0].points;let prior=-1;
   tracks.push({kind:'history',update(p){
    const time=start+(end-start)*p,width=x(new Date(time).toISOString());c.rect.setAttribute('width',width);c.cursor.setAttribute('x1',width);c.cursor.setAttribute('x2',width);
    let index=first.findLastIndex(point=>Date.parse(point.date)<=time);index=Math.max(0,index);
    if(index!==prior){prior=index;const date=first[index].date;c.caption.textContent=date+' · '+series.map(s=>{const point=s.points.findLast(point=>Date.parse(point.date)<=time);return s.name+' '+(point?format(point.value):'—')}).join(' · ')}
    return first[index].date+' · history replay';
   }});
  },
  scenario(id,n,x,inspect){
   const c=clip(id);let prior=-1;
   tracks.push({kind:'scenario',update(p){const day=Math.floor(clamp(p)*n),width=x(day);c.rect.setAttribute('width',width);c.cursor.setAttribute('x1',width);c.cursor.setAttribute('x2',width);if(day!==prior){prior=day;inspect?.(day);c.caption.textContent='Simulated session '+day+' / '+n+' · same retained paths'}return'Session '+day+' / '+n+' · scenario replay'}});
  },
  observations(id,records){
   const el=get(id),marks=[...el.querySelectorAll('.q-observation')],caption=document.createElement('div');caption.className='quant-replay-date';el.append(caption);
   tracks.push({kind:'history',update(p){const count=Math.max(1,Math.ceil(p*records.length));marks.forEach((mark,i)=>mark.style.opacity=i<count?'1':'0');const row=records[count-1];caption.textContent=row.origin+' · recorded calibration outcome '+count+' / '+records.length;return row.origin+' · calibration replay'}});
  },
  seek(p){pause();progress=clamp(p);paint()},
  finish(autoplay=true){
   // Factor coefficients are a fixed fit, so their animation is explicitly a visual reveal.
   if(!tracks.length){
    const marks=[...get('quant-content').querySelectorAll('svg rect,svg circle')];
    if(marks.length)tracks.push({kind:'fixed',update(p){marks.forEach((mark,i)=>{mark.style.opacity=p===1||i<Math.ceil(p*marks.length)?'1':'.08'});return'Fixed estimates · '+Math.round(p*100)+'% revealed'}});
   }
   const kinds=new Set(tracks.map(t=>t.kind));
   get('quant-motion-note').textContent=kinds.has('fixed')?'Visual reveal of fixed fitted estimates; these coefficients do not evolve with playback.':kinds.has('history')?'Replay of retained observations; each chart uses its own dated range. Static estimates and scores remain fixed.': 'Replay of the same seeded simulations, not incoming prices. The histogram shows the full-horizon distribution throughout.';
   ['quant-play','quant-restart','quant-progress','quant-speed'].forEach(id=>get(id).disabled=!tracks.length);
   paint();if(autoplay&&!reduced.matches&&!document.hidden&&tracks.length&&!get('quant-workspace').hidden)play();
  }
 };
})();
