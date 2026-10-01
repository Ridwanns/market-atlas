// Refreshed research stays independent of the retained financial and options modules.
function quantNavigate(id,view='summary'){
 if(!Q.assets[id])return;
 navCloseMap();navWorkspace('quant');quantOpen(id,view);navTicker.value=id;
 navDestination.value=view==='summary'?'models':view;
 if(!navDestination.value)navDestination.value='models';
 $('nav-open').dataset.state='success';navSynchronize();navStatus.textContent=id.toUpperCase()+' · Quant models';
 const heading=$('quant-workspace').querySelector('h2');heading.setAttribute('tabindex','-1');
 $('quant-workspace').scrollIntoView?.({behavior:'instant',block:'start'});heading.focus({preventScroll:true});
}
Object.keys(Q.assets).forEach(id=>{if(![...navTicker.options].some(q=>q.value===id)){const option=document.createElement('option');option.value=id;option.textContent=Q.assets[id].meta.symbol;navTicker.append(option)}});
$('quant-ticker').addEventListener('change',navSynchronize);
$('pro-open-models').addEventListener('click',()=>{const id=$('simple-stock-select').value;if(Q.assets[id])quantNavigate(id,'summary')});
const quantCompactStock=compactStock;
compactStock=function(){quantCompactStock();quantRefreshPrices();aiMapQuotes()};
function aiMapQuotes(){
 document.querySelectorAll('[data-ai-company]').forEach(button=>{
  const id=button.dataset.aiCompany,q=quoteMap[id],bar=q?.latest_minute_bar;
  let label=button.querySelector('.ai-map-price');if(!label){label=document.createElement('small');label.className='ai-map-price';button.querySelector('strong').append(label)}
  label.textContent='$'+num(bar?.price>0?bar.price:Q.assets[id].latest_unadjusted_close,2);
  label.title=bar?.price>0?(liveFailures.has(q.symbol)?'Retained quote after feed failure · ':'Public quote · ')+bar.time_utc+' · '+q.session:'Saved daily close · '+Q.assets[id].data.cutoff;
 });
}
const quantAIRefresh=aiRefreshPrices;
aiRefreshPrices=function(){quantAIRefresh();if(!quoteMap[aiSelected]?.latest_minute_bar?.price&&Q.assets[aiSelected]){$('ai-company-price').textContent='$'+num(Q.assets[aiSelected].latest_unadjusted_close,2);$('ai-company-quote').textContent='Saved daily close · '+Q.assets[aiSelected].data.cutoff+' · public quote unavailable'}aiMapQuotes()};
function aiQuantRisk(){
 const study=Q.portfolios?.styles?.[aiStyle];if(!study)return;
 // The pipeline owns these diagnostics; no browser-side fit or invented probabilities.
 const target=$('ai-quant-risk');if(!target)return;
 target.hidden=false;
 $('ai-quant-risk-note').textContent=Q.portfolios.first+' to '+Q.portfolios.last+' · '+Q.portfolios.observations+' shared sessions. '+Q.portfolios.protocol;
 const vol=study.annual_volatility;
 const risk=study.historical_risk;
 const dd=study.historical?.max_drawdown;
 $('ai-quant-risk-metrics').innerHTML=[['Covariance-implied annual volatility',Number.isFinite(vol)?pct(vol):'—'],['Historical maximum drawdown',Number.isFinite(dd)?pct(dd):'—'],['1-session 95% expected shortfall',risk?.['0.95']?.es!=null?pct(risk['0.95'].es):'—']].map(([label,value])=>'<div class="metric"><span class="label">'+esc(label)+'</span><strong class="value">'+value+'</strong></div>').join('');
 const contribution=study.risk_contributions||{};
 const items=Array.isArray(contribution)?study.ids.map((id,i)=>({label:id.toUpperCase(),value:contribution[i]})):Object.entries(contribution).map(([id,value])=>({label:id.toUpperCase(),value}));
 if(items.length)visualBars('ai-quant-risk-chart','Contribution to modeled portfolio variance',items);
}
const quantStyleApply=aiApplyStyle;aiApplyStyle=function(style){quantStyleApply(style);aiQuantRisk()};
proCommands.push(...Object.entries(Q.assets).map(([id,z])=>({title:id.toUpperCase()+' quant models',detail:z.meta.name+' · forecasts, volatility, risk and scenarios',type:'Quant research',run:()=>quantNavigate(id,'summary')})));
aiRefreshPrices();aiQuantRisk();quantRefreshPrices();navSynchronize();
