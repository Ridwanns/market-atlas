// One compact map to retained research and the investment decision workspace.
const navTicker=$('nav-ticker'),navDestination=$('nav-destination'),navStatus=$('nav-status');
navTicker.innerHTML=simpleInvestmentIds.map(id=>'<option value="'+id+'">'+id.toUpperCase()+'</option>').join('');
let navLastTicker='';
function navSynchronize(){
 const id=!$('investment-decision').hidden?$('decision-ticker').value:!$('quant-workspace').hidden?$('quant-ticker').value:!$('ai-portfolio').hidden&&window.aiPortfolioSelection?window.aiPortfolioSelection:$('simple-stock-select').value;navTicker.value=id;
 const company=Boolean(R.filings[id])||id==='nvda';
 const missingModel=!Q.assets[id]&&!simpleInvestmentIds.includes(id),modelRoutes=['models','monte-carlo','forecasts','volatility','tail-risk','regimes'];
 const unavailable=route=>(route==='investment-decision'&&!D.assets[id])||(['financials','options'].includes(route)&&!company)||(missingModel&&modelRoutes.includes(route));
 [...navDestination.options].forEach(option=>option.disabled=unavailable(option.value));
 document.querySelectorAll('[data-nav-route]').forEach(button=>button.disabled=unavailable(button.dataset.navRoute));
 $('nav-map-context').textContent=id.toUpperCase()+(Q.assets[id]?' · refreshed quant models through '+Q.assets[id].data.cutoff:missingModel?' · no fitted stock model':' · retained fund and index research');
 if(navDestination.selectedOptions[0]?.disabled)navDestination.value='overview';
 if(navLastTicker!==id){navLastTicker=id;navStatus.textContent=id.toUpperCase()+' · choose a section'}
}
const navStockRender=compactStock;
compactStock=function(){navStockRender();navSynchronize()};
navTicker.addEventListener('change',()=>{const id=navTicker.value;if(!$('investment-decision').hidden){if(D.assets[id]){decisionOpen(id);navSynchronize();return}if(Q.assets[id]){quantNavigate(id,'summary');return}navJump('overview');return}if(!$('quant-workspace').hidden&&Q.assets[id]){quantOpen(id,$('quant-view').value);navSynchronize();return}if(!simpleInvestmentIds.includes(id)){if(aiHoldings.some(h=>h.id===id)){aiSelect(id);navJump('ai-portfolio')}else if(Q.assets[id])quantNavigate(id,'summary');navSynchronize();return}if(!$('ai-portfolio').hidden&&aiHoldings.some(h=>h.id===id)){aiSelect(id);return}$('simple-stock-select').value=id;simpleStock();if(!$('ai-portfolio').hidden||!$('quant-workspace').hidden)navJump('overview')});
function navRoute(destination,id){
 const stock=Boolean(A.stocks[id]),nvda=id==='nvda';
 return ({
  overview:{target:'simple-stocks'},'ai-portfolio':{target:'ai-portfolio'},plan:{group:'plan',target:'simple-plan'},
  models:{group:'models',target:'research'},'monte-carlo':{group:'models',target:'mc-section'},forecasts:{group:'models',target:'research-models'},
  volatility:{group:'models',target:stock?'stock-vol-table':'research-har-table'},
  'tail-risk':{group:stock?'models':'portfolios',target:stock?'stock-risk-table':'asset-interpretation',assetInterpretation:!stock},
  regimes:{group:'models',target:'research-regime-chart'},
  financials:{group:nvda?'portfolios':'company',target:nvda?'fundamental-metrics':'financials'},
  options:{group:nvda?'portfolios':'company',target:nvda?'option-table':'options-new'},
  portfolios:{group:'portfolios',target:'sector'},sources:{group:'sources',target:'coverage'}
 })[destination];
}
function navOpenSection(event){
 event.preventDefault();const id=navTicker.value,destination=navDestination.value;
 if(destination==='investment-decision'&&D.assets[id]){
  navCloseMap();navWorkspace('decision');
  if($('decision-ticker').value!==id){decisionOpen(id);return}
  navSynchronize();navStatus.textContent=id.toUpperCase()+' · Investment Decision';$('nav-open').dataset.state='success';
  $('investment-decision').scrollIntoView?.({behavior:'instant',block:'start'});$('decision-title').focus({preventScroll:true});return;
 }
 if(Q.assets[id]&&['models','monte-carlo','forecasts','volatility','tail-risk','regimes'].includes(destination)){quantNavigate(id,destination==='models'?'summary':destination);return}
 if(destination==='overview'&&!simpleInvestmentIds.includes(id)&&Q.assets[id]){quantNavigate(id,'summary');return}
 const route=navRoute(destination,id);
 if(!route||navDestination.selectedOptions[0]?.disabled){navStatus.textContent='This section is unavailable for '+id.toUpperCase()+'.';$('nav-open').dataset.state='error';return}
 navCloseMap();navWorkspace(route.group?'research':destination==='ai-portfolio'?'ai':'overview');
 if(simpleInvestmentIds.includes(id)){$('simple-stock-select').value=id;compactStock()}
 if(route.group){$('advanced-section').value=route.group;$('advanced-details').open=true;compactGroup(route.group)}
 else $('advanced-details').open=false;
 if(route.assetInterpretation){$('asset-select').value=id;renderAsset()}
 const node=$(route.target);
 if(!node||node.hidden){navStatus.textContent='No retained section for this selection.';$('nav-open').dataset.state='error';return}
 const landing=node.classList.contains('view')||node.tagName==='SECTION'?node:node.closest('section')||node;
 const heading=landing.querySelector('h2')||landing;
 heading.setAttribute('tabindex','-1');
 landing.scrollIntoView?.({behavior:'instant',block:'start'});heading.focus({preventScroll:true});
 navSynchronize();navStatus.textContent=navTicker.value.toUpperCase()+' · '+navDestination.selectedOptions[0].textContent;
 $('nav-open').dataset.state='success';
}
$('model-nav-form').addEventListener('submit',navOpenSection);
function navWorkspace(active){
 $('simple-stocks').hidden=active!=='overview';$('ai-portfolio').hidden=active!=='ai';
 $('quant-workspace').hidden=active!=='quant';
 $('investment-decision').hidden=active!=='decision';
 $('advanced-details').hidden=active!=='research';
 [['nav-home','overview'],['nav-ai','ai'],['nav-explore','research']].forEach(([id,value])=>$(id).setAttribute('aria-pressed',String(active===value||(value==='research'&&['quant','decision'].includes(active)))));
 $('pro-portfolio-context').textContent=active==='decision'?'IDR → US · business evidence, valuation and risk':active==='ai'?'IDR → US · 3 stocks + SPY · '+(window.aiPortfolioStyleName||'Aggressive & Concentrated'):active==='quant'?'4 holdings + 3 indices · quant research · 5 / 20 sessions':'Your targets · NVDA 40% · TSM 25% · MU 20% · SPY 15%';
}
function navCloseMap(){ $('nav-explorer').hidden=true;$('nav-explore').setAttribute('aria-expanded','false') }
function navJump(destination){navDestination.value=destination;navOpenSection({preventDefault(){}})}
$('nav-home').addEventListener('click',()=>{navTicker.value=$('simple-stock-select').value;navJump('overview')});
$('nav-ai').addEventListener('click',()=>navJump('ai-portfolio'));
$('nav-explore').addEventListener('click',()=>{const open=$('nav-explorer').hidden;$('nav-explorer').hidden=!open;$('nav-explore').setAttribute('aria-expanded',String(open))});
$('nav-map-close').addEventListener('click',()=>{navCloseMap();$('nav-explore').focus()});
document.querySelectorAll('[data-nav-route]').forEach(button=>button.addEventListener('click',()=>navJump(button.dataset.navRoute)));
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!$('nav-explorer').hidden){navCloseMap();$('nav-explore').focus()}});
document.addEventListener('pointerdown',event=>{if(!$('nav-explorer').hidden&&!event.target.closest('.model-nav'))navCloseMap()});
const navOldDetails=detailShow;
detailShow=function(id){navWorkspace('research');navOldDetails(id)};show=detailShow;
navWorkspace('overview');
navSynchronize();
