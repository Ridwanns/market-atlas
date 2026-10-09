// Four explicit targets; all older raw research remains available in the archive.
(function(){
 'use strict';
 const targets=Q.focus.weights,ids=Q.focus.ids;
 const focus=document.createElement('section');focus.className='focus-allocation';focus.setAttribute('aria-label','Your portfolio target allocation');
 focus.innerHTML='<div class="focus-allocation-heading"><strong>Your allocation</strong>3 stocks + 1 ETF</div><div class="focus-weight-map">'+ids.map((id,i)=>'<button type="button" data-focus-holding="'+id+'" style="flex:'+targets[id]+';background:'+['#245dcc','#15928b','#9252bd','#53677e'][i]+'" aria-label="'+id.toUpperCase()+' target '+targets[id]*100+' percent">'+id.toUpperCase()+' '+targets[id]*100+'%</button>').join('')+'</div><button type="button" class="fx-use focus-allocation-action" id="focus-open-portfolio">Portfolio & risk ↗</button>';
 $('live-watchlist').after(focus);
 focus.querySelectorAll('[data-focus-holding]').forEach(button=>button.addEventListener('click',()=>{$('simple-stock-select').value=button.dataset.focusHolding;simpleStock();navJump('overview')}));
 $('focus-open-portfolio').addEventListener('click',()=>{aiSelect($('simple-stock-select').value);navJump('ai-portfolio')});
 const oldWatch=renderWatchlist;renderWatchlist=function(){oldWatch();document.querySelectorAll('[data-live-ticker]').forEach(button=>{const tag=document.createElement('span');tag.className='focus-weight';tag.textContent=targets[button.dataset.liveTicker]*100+'%';button.querySelector('strong').append(tag)})};
 const oldStock=compactStock;compactStock=function(){oldStock();const id=$('simple-stock-select').value,f=D.assets[id],z=Q.assets[id];
  $('pro-open-models').textContent=id.toUpperCase()+' quant models';
  $('pro-allocation-value').textContent=pct(targets[id]);$('pro-allocation-fill').style.setProperty('--allocation-fraction',targets[id]);
  const facts=[['Model inputs',z.data.cutoff],['Historical max drawdown',pct(z.summary.max_drawdown)],['20-session annualized vol',pct(z.summary.vol20)]];
  if(f){facts.push(['Reported financial period',f.ttm.end],['Reported net margin',pct(f.ttm.net_margin)]);if(id==='tsm')facts.push(['Listing','USD ADR · statements TWD'])}
  else facts.push(['Instrument','S&P 500 ETF'],['Company valuation','Use fund holdings; no corporate EPS model']);
  $('compact-stock-facts').innerHTML=facts.map(([k,v])=>'<span>'+esc(k)+': <b>'+esc(v)+'</b></span>').join('');
  $('compact-history-note').textContent=proRange==='today'?'Timestamped public-feed prices · '+quoteTime(currentQuote(id))+'. Quant inputs: '+z.data.cutoff+'; prices do not refit models.':'Adjusted-price history through '+z.data.cutoff+'. Current quote and financial reporting dates are separate.';
  const role={nvda:'40% target · largest direct position in compute and software. SPY may add overlapping exposure; current look-through weights are not measured.',tsm:'25% target · manufacturing and advanced packaging. USD ADR; Taiwan, capex, competition and entry valuation matter.',mu:'20% target · memory and HBM. Latest retained fundamentals include the 30 September release; normalize cycle margins before valuing.',spy:'15% target · broad US equity ETF alongside your three stocks. It may overlap with NVDA and MU; it is not cash or a loss cap.'};
  const p=$('simple-stock-reading').querySelectorAll('p');if(p[1])p[1].textContent=role[id];
 };
 $('ai-style').disabled=true;
 document.querySelector('.allocation-mini>div>span').textContent='Equity target weight';
 $('ai-budget').placeholder='Enter your portfolio budget';
 $('ai-quant-risk').open=true;
 document.querySelector('.ai-boundary-grid>div:last-child')?.remove();
 const valuationNote=document.querySelector('.ai-boundary-grid>div:first-child p');if(valuationNote)valuationNote.textContent='The three companies have dated financial evidence and editable 5/10-year valuation cases. These are generic sensitivities, not company forecasts. SPY is an ETF; no corporate earnings scenario is substituted for its holdings.';
 const oldSelect=aiSelect;aiSelect=function(id){oldSelect(id);if(id==='spy'){$('ai-company-evidence').innerHTML='<p>SPY is the State Street SPDR S&P 500 ETF Trust. Fund structure checked 9 October 2026. Fund holdings and their weights are not a live look-through calculation in this dashboard.</p><a class="ai-source-link" href="https://www.ssga.com/us/en/individual/etfs/state-street-spdr-sp-500-etf-trust-spy" target="_blank" rel="noreferrer">Read the official fund information ↗</a>'}};
 const oldDecision=window.decisionOpen;window.decisionOpen=function(id){if(!['nvda','tsm','mu'].includes(id))return null;return oldDecision(id)};
 ['research-select','asset-select','stock-select','financial-select','options-select'].forEach(name=>{const select=$(name);if(select)[...select.options].forEach(option=>{if(!Q.assets[option.value])option.remove()})});
 const chartGrid=document.createElement('div');chartGrid.className='quant-grid equal';chartGrid.innerHTML='<section class="quant-card"><h3>Historical portfolio replay</h3><p class="quant-caption">Your fixed targets · costs included · a retrospective illustration</p><div id="focus-nav-chart"></div></section><section class="quant-card"><h3>Distance below the running peak</h3><p class="quant-caption">Replay drawdown · an observed history, not a future loss limit</p><div id="focus-drawdown-chart"></div></section>';
 $('ai-quant-risk-metrics').after(chartGrid);
 function paintPortfolio(){const records=Q.portfolios.styles.focus.records;let peak=1;const nav=records.map(r=>({date:r.date,value:r.nav})),dd=records.map(r=>{peak=Math.max(peak,r.nav);return{date:r.date,value:r.nav/peak-1}});plot('focus-nav-chart',[{color:'var(--color-accent)',points:nav}],v=>num(v,2)+'×',true);plot('focus-drawdown-chart',[{color:'var(--color-negative)',points:dd}],pct,false)}
 const oldJump=navJump;navJump=function(destination){oldJump(destination);if(destination==='ai-portfolio')paintPortfolio()};
 let portfolioResize;window.addEventListener('resize',()=>{clearTimeout(portfolioResize);portfolioResize=setTimeout(()=>{if(!$('ai-portfolio').hidden)paintPortfolio()},150)});
 $('simple-stock-select').value='nvda';simpleStock();aiSelect('nvda');navJump('overview');
})();
