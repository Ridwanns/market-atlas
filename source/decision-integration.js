// One decision destination, with the same ticker and quote context as the rest of the dashboard.
(function(){
 'use strict';
 const nativeOpen=window.decisionOpen;
 window.decisionOpen=function(id){id=String(id).toLowerCase();if(D.assets[id])navTicker.value=id;return nativeOpen(id)};
 const aiButton=document.createElement('button');
 aiButton.type='button';aiButton.id='ai-decision-open';aiButton.className='sidebar-plan-link';
 aiButton.textContent='Investment Decision ↗';
 $('ai-model-open').parentElement.append(aiButton);
 aiButton.addEventListener('click',()=>decisionOpen(aiSelected));
 const stockButton=document.createElement('button');
 stockButton.type='button';stockButton.id='pro-open-decision';stockButton.className='sidebar-plan-link';
 stockButton.textContent='Investment Decision ↗';
 $('pro-open-models').parentElement.prepend(stockButton);
 stockButton.addEventListener('click',()=>decisionOpen($('simple-stock-select').value));
 function links(){stockButton.hidden=!D.assets[$('simple-stock-select').value];aiButton.hidden=!D.assets[aiSelected];aiButton.textContent='Investment Decision · '+aiSelected.toUpperCase()+' ↗'}
 const oldStock=compactStock;compactStock=function(){oldStock();links();decisionRefreshPrices()};
 const oldAI=aiRefreshPrices;aiRefreshPrices=function(){oldAI();links();decisionRefreshPrices()};
 const oldStyle=aiApplyStyle;aiApplyStyle=function(style){oldStyle(style);decisionRefreshStyle()};
 $('decision-ticker').addEventListener('change',navSynchronize);
 proCommands.push(...Object.keys(D.assets).filter(id=>simpleInvestmentIds.includes(id)).map(id=>({title:id.toUpperCase()+' Investment Decision',detail:'5/10-year valuation, financial statements, bottlenecks and IDR risk',type:'Decision research',run:()=>decisionOpen(id)})));
 let monitoring=false,lastMonitor=0;
 async function refreshMonitor(){
  if(monitoring||Date.now()-lastMonitor<60000||$('investment-decision').hidden||$('decision-explore').value!=='model-health')return;
  monitoring=true;lastMonitor=Date.now();
  try{
   const response=await fetch('http://127.0.0.1:8767/api/forecast-monitor',{cache:'no-store',signal:AbortSignal.timeout(25000)});
   if(!response.ok)throw new Error('Model monitoring service unavailable');
   decisionUpdateMonitor(await response.json());
  }catch(_){
   const note=document.createElement('p');note.className='decision-caption';note.id='decision-monitor-service';
   note.textContent='Forward ledger uses the embedded dated snapshot. The local monitoring service could not be reached; outcomes have not been assumed.';
   if(!$('decision-monitor-service'))$('decision-content').append(note);
  }finally{monitoring=false}
 }
 $('decision-explore').addEventListener('change',refreshMonitor);
 const oldJump=navJump;navJump=function(destination){oldJump(destination);if(destination==='investment-decision')refreshMonitor()};
 setInterval(refreshMonitor,60000);
 links();navSynchronize();
})();
