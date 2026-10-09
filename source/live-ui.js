// A single dashboard; all original calculations stay under one disclosure.
let livePayload=null,liveBusy=false,liveLastSuccess=null,liveFailures=new Set();
const compactGroups={plan:[],company:['financials','options-new','mu-review','nvda'],models:['research','stocks','evidence'],portfolios:['overview','sector','allocation'],sources:['coverage','methods','indices','data']};
function syncResearchTicker(){
 const id=$('simple-stock-select').value;
 if(R.assets[id]){$('research-select').value=id;researchAsset()}
 if(A.stocks[id]){$('stock-select').value=id;renderStock()}
 if(R.filings[id]){$('financial-select').value=id;financialAsset();$('options-select').value=id;optionsAsset()}
}
function compactGroup(group){
 const id=$('simple-stock-select').value;let members=compactGroups[group]||[];
 if(group==='company')members=members.filter(v=>v==='financials'||v==='options-new'?Boolean(R.filings[id]):v==='stocks'?Boolean(A.stocks[id]):v==='mu-review'?id==='mu':v==='nvda'?id==='nvda':false);
 $('simple-plan').hidden=group!=='plan';detailedViews.forEach(n=>n.hidden=!members.includes(n.id));
 if(group==='models'){
  members=members.filter(v=>v!=='stocks'||Boolean(A.stocks[id]));
  $('research-select').value=R.assets[id]?id:id==='qqq'?'nasdaq':'sp500';researchAsset();
  if(A.stocks[id]){$('stock-select').value=id;$('stock-horizon').value=$('research-horizon').value;renderStock()}
  detailedViews.forEach(n=>n.hidden=!members.includes(n.id));
 }
 if(group==='company')syncResearchTicker();
 if(group==='sources'){
  if(!$('index-frame').getAttribute('srcdoc'))$('index-frame').srcdoc=payload.index_html;
  if(!$('analysis-json').value)$('analysis-json').value=JSON.stringify(A,null,2);
 }
 if(group==='company'&&id==='nvda'&&!$('nvda-frame').getAttribute('srcdoc'))$('nvda-frame').srcdoc=payload.nvda_html;
 // Put the selected asset's research first, ahead of cross-asset comparisons.
 const visibleOrder=[...$('advanced-content').children].filter(node=>node.classList.contains('view')&&!node.hidden).map(node=>node.id);
 if(members.some((view,i)=>visibleOrder[i]!==view))members.forEach(view=>{const node=$(view);if(node&&!node.hidden)$('advanced-content').appendChild(node)});
 $('compact-research-note').textContent=(group==='company'&&!members.length?'No separate company filings or option model is retained for this fund. Its history and portfolio comparisons are available in the other groups. ':group==='models'&&!R.assets[id]?id.toUpperCase()+' is not modeled directly. Showing '+(id==='qqq'?'Nasdaq Composite':'S&P 500')+' research as market context; these index return definitions differ from the fund. ':'')+'Saved model and filing cutoff: 29 September 2026. Refreshing prices does not rerun these analyses.';
}
detailShow=function(id){
 const group=compactGroups[id]?id:Object.keys(compactGroups).find(k=>compactGroups[k].includes(id));
 if(!group)return;$('advanced-section').value=group;$('advanced-details').open=true;compactGroup(group);
 $('advanced-details').scrollIntoView?.({behavior:'smooth',block:'start'});
};
show=detailShow;
simpleShow=function(id){if(id==='simple-research')detailShow('company');else if(id==='simple-plan')detailShow('plan');else $('simple-stocks').scrollIntoView?.({behavior:'smooth',block:'start'})};
const retainedStockRender=simpleStock;
simpleStock=function(){retainedStockRender();compactStock();if($('advanced-details').open&&['company','models'].includes($('advanced-section').value))compactGroup($('advanced-section').value)};
function quoteAge(c){return Math.max(0,(Date.now()-Date.parse(c.time))/60000)}
function quoteTime(c){return new Date(c.time).toLocaleString('en-GB',{timeZone:'Asia/Jakarta',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false})+' WIB'}
function quoteStatus(c){
 if(!livePayload)return'Saved';if(liveFailures.has(c.q.symbol))return'Refresh failed';
 const age=quoteAge(c);if(c.q.session==='Closed')return'Closed';
 if(age>5)return 'Quote '+Math.round(age)+'m old';return c.q.session||c.session;
}
function quoteChange(c){return c.q.previous_close>0?c.price/c.q.previous_close-1:null}
function paintIntraday(id){
 const c=currentQuote(id),rows=c.q.intraday||[],target=$('simple-stock-history');
 if(!rows.length){target.innerHTML='<p class="quiet">'+(livePayload?'Intraday bars are unavailable for this refresh. Select the 5-year history above.':'Connecting to intraday data… The saved 5-year history remains available.')+'</p>';return}
 const values=rows.map(q=>q.price),start=Date.parse(rows[0].time),end=Date.parse(rows.at(-1).time),W=1000,H=230,L=65,Rt=16,T=15,B=30;
 const low=Math.min(...values),high=Math.max(...values),pad=(high-low)*.12||low*.001,min=low-pad,max=high+pad;
 const x=t=>L+(Date.parse(t)-start)*(W-L-Rt)/(end-start||1),y=p=>T+(max-p)*(H-T-B)/(max-min);
 let svg='<svg class="chart" role="img" aria-label="'+id.toUpperCase()+' intraday USD price" viewBox="0 0 '+W+' '+H+'">';
 for(let i=0;i<4;i++){const p=min+(max-min)*i/3,yy=y(p);svg+='<line x1="'+L+'" x2="'+(W-Rt)+'" y1="'+yy+'" y2="'+yy+'" stroke="#2b3648"/><text x="'+(L-8)+'" y="'+(yy+4)+'" text-anchor="end" font-size="11" fill="#a6b5c9">'+num(p,2)+'</text>'}
 svg+='<polyline fill="none" stroke="'+colors[id]+'" stroke-width="2" points="'+rows.map(q=>x(q.time)+','+y(q.price)).join(' ')+'"/>';
 for(const t of [start,(start+end)/2,end]){const label=new Date(t).toLocaleTimeString('en-GB',{timeZone:'Asia/Jakarta',hour:'2-digit',minute:'2-digit',hour12:false});svg+='<text x="'+x(new Date(t).toISOString())+'" y="'+(H-5)+'" text-anchor="middle" font-size="11" fill="#a6b5c9">'+label+'</text>'}
 target.innerHTML=svg+'</svg>';
}
function compactStock(){
 const id=$('simple-stock-select').value||'spy',c=currentQuote(id),fx=Number($('plan-fx').value),{weights}=selectedPlan(),a=A.assets[id];
 $('compact-ticker-name').textContent=id.toUpperCase();
 $('simple-stock-metrics').innerHTML=[['Latest USD price',simpleMoney(c.price,'USD')],['IDR / share · plan FX',fx>0?simpleMoney(c.price*fx):'—'],['Budget allocation',pct(weights[id]||0)]].map(([label,value])=>'<div class="metric"><div class="label">'+label+'</div><div class="value">'+value+'</div></div>').join('');
 const change=quoteChange(c);$('live-company-change').innerHTML=change==null?'':signed(change)+' <small>vs previous close</small>';
 const reading=$('simple-stock-reading');reading.firstElementChild.innerHTML='<strong>'+esc(quoteStatus(c))+'</strong> · '+esc(quoteTime(c))+(liveFailures.has(c.q.symbol)?' · last successful quote retained':'');
 const f=R.filings[id],eps=f?.ttm?.eps,pe=id!=='tsm'&&eps>0?c.price/eps:null;
 const facts=[['Historical max drawdown',pct(a.max_drawdown)],['Historical annual volatility',pct(a.volatility)]];
 if(f){facts.push(['Retained statement period',f.latest_period.end]);if(pe!==null)facts.push(['Price / retained GAAP EPS',num(pe)+'×']);else if(id==='intc')facts.push(['GAAP P/E','Loss-making']);else if(id==='tsm')facts.push(['Statements','TWD · quote USD ADR'])}
 $('compact-stock-facts').innerHTML=facts.map(([k,v])=>'<span>'+esc(k)+': <b>'+esc(v)+'</b></span>').join('');
 if($('live-chart-mode').value==='today'){paintIntraday(id);const bars=c.q.intraday||[],largeJump=bars.some((q,i)=>i>0&&Math.abs(q.price/bars[i-1].price-1)>.05);$('compact-history-note').textContent='Intraday public-feed prices · times WIB · last quote '+quoteTime(c)+'. Risk and earnings inputs: 29 Sep; valuation updates price only.'+(largeJump?' Large jumps appear in provider bars; verify those prints with your broker.':'')}
 else{$('compact-history-note').textContent='5-year adjusted-price history through 29 Sep 2026, indexed to 1×. Latest refreshing quote is shown separately; historical models and earnings are unchanged.'}
 renderWatchlist();
}
function renderWatchlist(){
 const selected=$('simple-stock-select').value;
 $('live-watchlist').innerHTML=simpleInvestmentIds.map(id=>{const c=currentQuote(id),change=quoteChange(c);return'<button type="button" class="watch-chip" data-live-ticker="'+id+'" aria-pressed="'+(id===selected)+'" title="'+esc(quoteStatus(c)+' · '+quoteTime(c))+'"><strong>'+id.toUpperCase()+'</strong><span>'+simpleMoney(c.price,'USD')+'</span><small>'+ (change==null?'Saved quote':(change>=0?'+':'')+pct(change))+' · '+esc(quoteStatus(c))+'</small></button>'}).join('');
 document.querySelectorAll('[data-live-ticker]').forEach(n=>n.addEventListener('click',()=>{$('simple-stock-select').value=n.dataset.liveTicker;simpleStock()}));
 const indices=[['^gspc','S&P 500'],['^ixic','Nasdaq'],['^jkse','IHSG']];
 const fxq=quoteMap['idr=x'],fxc=currentQuote('idr=x');
 $('live-market-strip').innerHTML=indices.map(([id,name])=>{const c=currentQuote(id);return c?'<span title="'+esc(quoteStatus(c)+' · '+quoteTime(c))+'">'+name+' <b>'+num(c.price)+'</b></span>':''}).join('')+'<span title="'+esc(quoteStatus(fxc)+' · '+quoteTime(fxc))+'">USD/IDR <b>Rp'+num(fxc.price,0)+'</b> · '+esc(quoteStatus(fxc))+'</span><span id="live-fx-use"><button type="button" id="live-use-fx" class="fx-use">Use feed FX in plan</button></span>';
 $('live-use-fx').addEventListener('click',()=>{$('plan-fx').value=fxc.price;renderSimplePlan();$('live-use-fx').textContent='FX applied ✓'});
}
function liveState(message,connected=false){$('live-state').textContent=message;$('live-state').classList.toggle('connected',connected)}
async function refreshLive(){
 if(liveBusy)return;liveBusy=true;$('live-refresh').disabled=true;
 if(!liveLastSuccess)liveState('Connecting…');
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),30000);
 try{
  const base=location.protocol==='file:'?'http://127.0.0.1:8767':'';
  const response=await fetch(base+'/api/quotes',{cache:'no-store',signal:controller.signal});
  if(!response.ok)throw new Error('Quote service returned '+response.status);
  const data=await response.json();if(!Array.isArray(data.quotes))throw new Error('Invalid quote response');
  const ok=data.quotes.filter(q=>!q.error&&q.latest_minute_bar?.price>0);
  if(!ok.length)throw new Error('No valid quotes received');
  liveFailures=new Set(data.quotes.filter(q=>q.error).map(q=>q.symbol));
  for(const q of ok)quoteMap[q.symbol.toLowerCase()]=q;
  livePayload=data;liveLastSuccess=Date.now();compactStock();
  liveState(liveFailures.size?'Connected · '+liveFailures.size+' feed error(s)':'Auto-refresh ON · 60s',liveFailures.size===0);
  $('live-updated').textContent='Retrieved '+new Date(data.fetched_utc).toLocaleTimeString('en-GB',{timeZone:'Asia/Jakarta',hour12:false})+' WIB · quote times vary';
  $('live-updated').title='Yahoo public feed; exchange delays may apply. Hover a price for its quote time. Refreshing prices does not update saved models or earnings.';
 }catch(error){
  liveState('Disconnected · saved prices');
  $('live-updated').textContent=(liveLastSuccess?'Last connection '+new Date(liveLastSuccess).toLocaleTimeString('en-GB',{timeZone:'Asia/Jakarta',hour12:false})+' WIB. ':'')+'Open the live dashboard or run Start-Live-Dashboard.cmd.';
  $('live-updated').title=String(error.message||error);compactStock();
 }finally{clearTimeout(timer);liveBusy=false;$('live-refresh').disabled=false}
}
$('live-refresh').addEventListener('click',refreshLive);
$('live-chart-mode').addEventListener('change',simpleStock);
$('simple-stock-select').addEventListener('change',()=>{compactStock();if($('advanced-details').open&&['company','models'].includes($('advanced-section').value))compactGroup($('advanced-section').value)});
$('simple-stock-select').value=plan.default_profile==='aggressive'?'tsm':'spy';
$('research-select').addEventListener('change',()=>{
 const id=$('research-select').value;
 if(simpleInvestmentIds.includes(id)){$('simple-stock-select').value=id;simpleStock()}
 else if($('advanced-section').value==='models'){$('stocks').hidden=true;$('compact-research-note').textContent='Showing '+names[id]+' index models as selected research context. The live watchlist quote remains separate. Saved model cutoff: 29 September 2026.'}
});
$('research-horizon').addEventListener('change',()=>{const id=$('simple-stock-select').value;if(A.stocks[id]&&$('research-select').value===id){$('stock-horizon').value=$('research-horizon').value;renderStock()}});
$('stock-horizon').addEventListener('change',()=>{const id=$('stock-select').value;if(R.assets[id]){$('research-horizon').value=$('stock-horizon').value;$('research-select').value=id;researchAsset()}});
$('simple-plan').hidden=true;detailedViews.forEach(n=>n.hidden=true);
// The former four-section router is replaced; company detail remains on this page.
$('simple-stock-more').addEventListener('click',()=>detailShow('company'));
$('advanced-details').addEventListener('toggle',()=>{if($('advanced-details').open)compactGroup($('advanced-section').value)});
const liveProviderLink=document.createElement('a');liveProviderLink.href='https://help.yahoo.com/kb/finance/article-exchanges-data-delays-sln2310.html';liveProviderLink.target='_blank';liveProviderLink.rel='noreferrer';liveProviderLink.textContent='Feed delays';
document.querySelector('.footer').append(' · ',liveProviderLink);
simpleStock();refreshLive();
setInterval(()=>{if(!document.hidden)refreshLive()},60000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&(!liveLastSuccess||Date.now()-liveLastSuccess>60000))refreshLive()});
