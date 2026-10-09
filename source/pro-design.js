// Design layer only. Quote fetching, portfolio arithmetic and saved models are retained.
let proRange='today',proChartKey='',proCursorTime=null,proCommandIndex=0,proCommandFocus=null;
const proNames={spy:'SPDR S&P 500 ETF Trust',qqq:'Invesco QQQ Trust',tsm:'Taiwan Semiconductor · US ADR',nvda:'NVIDIA Corporation',mu:'Micron Technology',amd:'Advanced Micro Devices',intc:'Intel Corporation'};
const proPrices=new Map();
const proStockRender=compactStock,proWatchRender=renderWatchlist;
const proEasingReduced=()=>Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);
function proSetTheme(theme){
 document.documentElement.dataset.theme=theme;
 $('pro-theme-toggle').setAttribute('aria-label','Switch to '+(theme==='dark'?'light':'dark')+' theme');
 $('pro-theme-toggle').innerHTML=theme==='dark'?'<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><circle cx="10" cy="10" r="3.5"/><path d="M10 1v2m0 14v2M1 10h2m14 0h2M3.5 3.5 5 5m10 10 1.5 1.5M3.5 16.5 5 15M15 5l1.5-1.5"/></svg>':'<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M16.5 11.7A7 7 0 0 1 8.3 3.5a7 7 0 1 0 8.2 8.2Z"/></svg>';
 try{localStorage.setItem('market-atlas-theme',theme)}catch(_){/* Storage is optional. */}
}
function proSpark(rows){
 const data=rows.slice(-60);if(data.length<2)return'';
 const values=data.map(q=>q.price),lo=Math.min(...values),hi=Math.max(...values),points=data.map((q,i)=>(i*40/(data.length-1)+1)+','+(13-(q.price-lo)*12/(hi-lo||1)));
 return'<svg class="watch-spark" viewBox="0 0 42 14" aria-hidden="true"><polyline points="'+points.join(' ')+'" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>';
}
renderWatchlist=function(){
 const focusId=document.activeElement?.dataset?.liveTicker;
 proWatchRender();
 document.querySelectorAll('[data-live-ticker]').forEach(button=>{
  const id=button.dataset.liveTicker,c=currentQuote(id),previous=proPrices.get(id),value=button.querySelector(':scope>span');
  button.querySelector('strong').insertAdjacentHTML('beforeend',proSpark(c.q.intraday||[]));
  if(previous!==undefined&&previous!==c.price&&!proEasingReduced())value.classList.add('quote-changed');
  proPrices.set(id,c.price);
  if(focusId===id)button.focus({preventScroll:true});
 });
};
function proData(id){
 if(proRange==='today')return(currentQuote(id).q.intraday||[]).map(q=>({time:q.time,value:q.price}));
 const history=Q.assets[id]?Q.assets[id].summary.history.map(q=>({date:q.date,level:q.close})):A.assets[id].history,last=Date.parse(history.at(-1).date),days={'1m':31,'6m':183,'1y':366,'5y':1827}[proRange]||1827;
 const rows=history.filter(q=>Date.parse(q.date)>=last-days*86400000),base=rows[0]?.level;
 return rows.map(q=>({time:q.date+'T00:00:00+07:00',value:q.level/base*100}));
}
function proTimeLabel(time,full=false){
 const day=proRange!=='today';
 return new Date(time).toLocaleString('en-GB',{timeZone:'Asia/Jakarta',...(day?{...((full||proRange!=='5y')?{day:'2-digit'}:{}),month:'short',...((full||proRange==='5y')?{year:'numeric'}:{})}:{...(full?{day:'2-digit',month:'short'}:{}),hour:'2-digit',minute:'2-digit',hour12:false})});
}
function proDrawChart(id){
 const target=$('simple-stock-history'),data=proData(id),isLive=proRange==='today',focused=target.contains(document.activeElement),key=id+'/'+proRange;
 const shouldEnter=key!==proChartKey;proChartKey=key;
 document.querySelectorAll('[data-chart-range]').forEach(n=>n.setAttribute('aria-pressed',String(n.dataset.chartRange===proRange)));
 const cutoff=Q.assets[id]?.data.cutoff||A.assets[id].last;
 $('pro-chart-caption').textContent=isLive?'USD · WIB · axis scaled to visible prices':'Adjusted history · rebased to 100 · '+cutoff;
 if(!isLive)$('compact-history-note').textContent=({'1m':'1-month','6m':'6-month','1y':'1-year','5y':'5-year'}[proRange]||'5-year')+' adjusted-price history through '+cutoff+', rebased to 100 at the first observation in this range. Latest quotes are shown separately; financials and options retain their own saved dates.';
 if(data.length<2){target.innerHTML='<p class="quiet">'+(livePayload?'Intraday bars unavailable. Choose a historical range above.':'Connecting to intraday prices… Historical ranges are available now.')+'</p>';return}
 const W=Math.max(260,Math.min(940,target.clientWidth||940)),H=W<480?230:W<760?280:320,L=52,Rt=16,T=20,B=32,start=Date.parse(data[0].time),end=Date.parse(data.at(-1).time);
 const values=data.map(q=>q.value),lo=Math.min(...values),hi=Math.max(...values),pad=(hi-lo)*.13||Math.abs(lo)*.001,min=lo-pad,max=hi+pad;
 const x=t=>L+(Date.parse(t)-start)*(W-L-Rt)/(end-start||1),y=v=>T+(max-v)*(H-T-B)/(max-min);
 const valueLabel=v=>isLive?'$'+num(v,2):num(v,1)+' index';
 const slug='pro-price-'+id;
 let svg='<svg class="chart '+(shouldEnter?'chart-enter':'')+'" tabindex="0" role="img" aria-labelledby="'+slug+'-title '+slug+'-desc" viewBox="0 0 '+W+' '+H+'"><title id="'+slug+'-title">'+id.toUpperCase()+(isLive?' intraday USD price':' adjusted historical growth')+'</title><desc id="'+slug+'-desc">'+(isLive?'Timestamped public-feed prices, with vertical axis scaled to the observed price range.':'Adjusted-close proxy growth, rebased to 100 at the selected range start.')+' Use left and right arrows to inspect observations.</desc>';
 for(let i=0;i<5;i++){const v=min+(max-min)*i/4,yy=y(v);svg+='<line class="chart-grid" x1="'+L+'" x2="'+(W-Rt)+'" y1="'+yy+'" y2="'+yy+'"/><text x="'+(L-10)+'" y="'+(yy+4)+'" text-anchor="end" font-size="11">'+num(v,isLive?2:0)+'</text>'}
 const segments=[[]];data.forEach((q,i)=>{if(isLive&&i&&Date.parse(q.time)-Date.parse(data[i-1].time)>30*60000)segments.push([]);segments.at(-1).push(q)});
 for(const rows of segments){if(rows.length<2)continue;const pts=rows.map(q=>x(q.time)+','+y(q.value)).join(' '),floor=H-B;svg+='<polygon class="price-area" points="'+x(rows[0].time)+','+floor+' '+pts+' '+x(rows.at(-1).time)+','+floor+'"/><polyline class="price-trace" points="'+pts+'"/>'}
 const timeTicks=W<480?3:5;
 for(let i=0;i<timeTicks;i++){const t=start+(end-start)*i/(timeTicks-1),align=i===0?'start':i===timeTicks-1?'end':'middle';svg+='<text x="'+x(new Date(t).toISOString())+'" y="'+(H-8)+'" text-anchor="'+align+'" font-size="11">'+esc(proTimeLabel(t))+'</text>'}
 const last=data.at(-1);svg+='<circle class="cursor-dot" cx="'+x(last.time)+'" cy="'+y(last.value)+'" r="3.5"/><g id="pro-chart-cursor" hidden><line class="cursor-line" id="pro-cursor-x" y1="'+T+'" y2="'+(H-B)+'"/><line class="cursor-line" id="pro-cursor-y" x1="'+L+'" x2="'+(W-Rt)+'"/><circle class="cursor-dot" id="pro-cursor-dot" r="4"/></g></svg>';
 target.innerHTML=svg+'<div id="pro-chart-tooltip" class="chart-tooltip" role="status" hidden></div>';
 const element=target.querySelector('svg'),tooltip=$('pro-chart-tooltip');let cursor=data.length-1;
 function nearest(stamp){let a=0,b=data.length-1;while(a<b){const mid=Math.floor((a+b)/2);if(Date.parse(data[mid].time)<stamp)a=mid+1;else b=mid}return a>0&&stamp-Date.parse(data[a-1].time)<Date.parse(data[a].time)-stamp?a-1:a}
 function inspect(index){
  cursor=Math.max(0,Math.min(data.length-1,index));const q=data[cursor],xx=x(q.time),yy=y(q.value),bounds=element.getBoundingClientRect();
  proCursorTime=q.time;$('pro-chart-cursor').removeAttribute('hidden');tooltip.hidden=false;
  $('pro-cursor-x').setAttribute('x1',xx);$('pro-cursor-x').setAttribute('x2',xx);$('pro-cursor-y').setAttribute('y1',yy);$('pro-cursor-y').setAttribute('y2',yy);$('pro-cursor-dot').setAttribute('cx',xx);$('pro-cursor-dot').setAttribute('cy',yy);
  tooltip.innerHTML='<strong>'+esc(valueLabel(q.value))+'</strong><time>'+esc(proTimeLabel(q.time,true)+(isLive?' WIB':''))+'</time>';
  const left=xx*(bounds.width||W)/W,top=yy*(bounds.height||H)/H;
  tooltip.style.left=Math.max(4,Math.min((bounds.width||W)-148,left+12))+'px';tooltip.style.top=Math.max(4,top-60)+'px';
 }
 function hide(){tooltip.hidden=true;$('pro-chart-cursor').setAttribute('hidden','');proCursorTime=null}
 element.addEventListener('pointermove',event=>{const bounds=element.getBoundingClientRect(),px=(event.clientX-bounds.left)*W/bounds.width,stamp=start+(Math.max(L,Math.min(W-Rt,px))-L)*(end-start)/(W-L-Rt);inspect(nearest(stamp))});
 element.addEventListener('pointerleave',()=>{if(document.activeElement!==element)hide()});
 element.addEventListener('focus',()=>inspect(proCursorTime?nearest(Date.parse(proCursorTime)):data.length-1));
 element.addEventListener('blur',hide);
 element.addEventListener('keydown',event=>{const delta={ArrowLeft:-1,ArrowRight:1,Home:-data.length,End:data.length}[event.key];if(delta!==undefined){event.preventDefault();inspect(cursor+delta)}else if(event.key==='Escape')hide()});
 if(focused){element.focus({preventScroll:true});if(proCursorTime)inspect(nearest(Date.parse(proCursorTime)))}
}
function proSelectedStock(){
 const id=$('simple-stock-select').value,weight=selectedPlan().weights[id]||0;
 $('compact-ticker-name').textContent=id.toUpperCase();$('company-monogram').textContent=id.toUpperCase().slice(0,2);$('company-full-name').textContent=proNames[id]||names[id];
 $('pro-open-models').textContent=id.toUpperCase()+(R.assets[id]?' models':' index models');
 $('pro-open-models').setAttribute('aria-label','View '+id.toUpperCase()+(R.assets[id]?' stock models':' index context models'));
 $('pro-allocation-value').textContent=pct(weight);$('pro-allocation-fill').style.setProperty('--allocation-fraction',weight);
 $('compact-stock-facts').querySelectorAll('span').forEach(row=>{const label=row.firstChild;if(label?.nodeType===3)label.textContent=label.textContent.replace(/:\s*$/,'')});
 proDrawChart(id);
}
compactStock=function(){const hadChartFocus=$('simple-stock-history').contains(document.activeElement),cursor=proCursorTime;proStockRender();proSelectedStock();if(hadChartFocus){proCursorTime=cursor;$('simple-stock-history').querySelector('svg')?.focus({preventScroll:true})}};
document.querySelectorAll('[data-chart-range]').forEach(button=>button.addEventListener('click',()=>{
 proRange=button.dataset.chartRange;$('live-chart-mode').value=proRange==='today'?'today':'history';simpleStock();
}));
$('live-chart-mode').addEventListener('change',()=>{proRange=$('live-chart-mode').value==='today'?'today':'5y';compactStock()});
$('pro-open-plan').addEventListener('click',()=>detailShow('plan'));
$('pro-open-models').addEventListener('click',()=>detailShow('models'));
$('pro-theme-toggle').addEventListener('click',()=>proSetTheme(document.documentElement.dataset.theme==='dark'?'light':'dark'));
const proCommands=[...simpleInvestmentIds.map(id=>({title:id.toUpperCase(),detail:proNames[id],type:'Investment',run:()=>{$('simple-stock-select').value=id;simpleStock();$('simple-stocks').scrollIntoView?.({behavior:proEasingReduced()?'instant':'smooth',block:'start'})}})),...[
 ['Investment plan & IDR budget','plan'],['Company financials & options','company'],['Forecasts & risk models','models'],['Markets & portfolios','portfolios'],['Sources & full modules','sources']
].map(([title,id])=>({title,detail:'Research',type:'Analysis',run:()=>detailShow(id)})),{title:'Refresh prices',detail:'Fetch the latest public quotes',type:'Action',run:refreshLive},{title:'Switch theme',detail:'Light / dark appearance',type:'Action',run:()=>$('pro-theme-toggle').click()}];
let proCommandMatches=[];
function proCloseSearch(){const dialog=$('command-dialog');if(dialog.close)dialog.close();else dialog.removeAttribute('open');proCommandFocus?.focus?.({preventScroll:true})}
function proSearchResults(){
 const query=$('command-query').value.trim().toLowerCase();proCommandMatches=proCommands.filter(q=>(q.title+' '+q.detail).toLowerCase().includes(query));proCommandIndex=0;
 $('command-results').innerHTML=proCommandMatches.length?proCommandMatches.map((q,i)=>'<button type="button" class="command-row" data-command-index="'+i+'" aria-selected="'+(i===0)+'"><span>'+esc(q.title)+'</span><small>'+esc(q.type)+'</small></button>').join(''):'<p class="command-empty">No matches. Try a ticker such as MU or a topic such as risk.</p>';
 $('command-results').querySelectorAll('button').forEach(button=>button.addEventListener('click',()=>{const q=proCommandMatches[Number(button.dataset.commandIndex)];proCloseSearch();q.run()}));
}
function proOpenSearch(){proCommandFocus=document.activeElement;$('command-query').value='';proSearchResults();const dialog=$('command-dialog');if(dialog.showModal)dialog.showModal();else dialog.setAttribute('open','');$('command-query').focus()}
$('pro-search-open').addEventListener('click',proOpenSearch);$('command-close').addEventListener('click',proCloseSearch);$('command-query').addEventListener('input',proSearchResults);
$('command-dialog').addEventListener('click',event=>{if(event.target===$('command-dialog'))proCloseSearch()});
$('command-dialog').addEventListener('cancel',()=>{proCommandFocus?.focus?.({preventScroll:true})});
$('command-query').addEventListener('keydown',event=>{if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();proCommandIndex=Math.max(0,Math.min(proCommandMatches.length-1,proCommandIndex+(event.key==='ArrowDown'?1:-1)));$('command-results').querySelectorAll('button').forEach((n,i)=>n.setAttribute('aria-selected',String(i===proCommandIndex)));$('command-results').querySelectorAll('button')[proCommandIndex]?.scrollIntoView?.({block:'nearest'})}else if(event.key==='Enter'&&proCommandMatches[proCommandIndex]){event.preventDefault();const command=proCommandMatches[proCommandIndex];proCloseSearch();command.run()}});
document.addEventListener('keydown',event=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){event.preventDefault();if($('command-dialog').open)proCloseSearch();else proOpenSearch()}});
// Keep prices precise: acknowledge changes visually without counting through fictitious quotes.
const proRefreshButton=$('live-refresh');
const proRefreshState=()=>{proRefreshButton.setAttribute('aria-busy',String(proRefreshButton.disabled));proRefreshButton.dataset.state=proRefreshButton.disabled?'loading':$('live-state').classList.contains('connected')?'success':'error'};
const proBusyObserver=new MutationObserver(proRefreshState);
proBusyObserver.observe(proRefreshButton,{attributes:true,attributeFilter:['disabled']});
proRefreshState();
// The same semantic chart colours apply to retained detail charts.
Object.keys(colors).forEach((id,i)=>colors[id]=['var(--color-accent)','var(--series-1)','var(--series-2)','var(--series-3)','var(--series-4)','var(--series-5)'][i%6]);
let proSavedTheme='light';try{proSavedTheme=localStorage.getItem('market-atlas-theme')||'light'}catch(_){}
proSetTheme(proSavedTheme==='dark'?'dark':'light');compactStock();
if(window.ResizeObserver){let width=0;const chartResize=new ResizeObserver(entries=>{const next=Math.round(entries[0].contentRect.width);if(next&&next!==width){width=next;proDrawChart($('simple-stock-select').value)}});chartResize.observe($('simple-stock-history'))}
