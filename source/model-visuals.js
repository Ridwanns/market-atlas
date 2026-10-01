// Graphs read the retained model outputs. Only scenario paths are reproduced at build time.
function visualFrame(target,title,height=300){
 const el=$(target),width=Math.max(220,Math.min(1000,el.clientWidth||520));
 return {el,w:width,h:height,svg:'<svg class="visual-chart" role="img" aria-label="'+esc(title)+'" viewBox="0 0 '+width+' '+height+'"><title>'+esc(title)+'</title>'};
}
function visualLegend(items){return '<div class="visual-legend">'+items.map(([label,color,band])=>'<span><i class="'+(band?'band-key':'')+'" style="--legend-color:'+color+'"></i>'+esc(label)+'</span>').join('')+'</div>'}
function visualBars(target,title,items,format=pct){
 const f=visualFrame(target,title,Math.max(150,items.length*38+48)),L=Math.min(132,f.w*.34),right=66,W=f.w-L-right;
 const low=Math.min(0,...items.map(q=>q.value)),high=Math.max(0,...items.map(q=>q.value));const span=high-low||1,x=v=>L+(v-low)/span*W;
 let svg=f.svg+'<line class="chart-zero" x1="'+x(0)+'" x2="'+x(0)+'" y1="8" y2="'+(f.h-28)+'"/>';
 items.forEach((q,i)=>{const y=i*38+12,zero=x(0),end=x(q.value);svg+='<text class="bar-label" x="'+(L-10)+'" y="'+(y+15)+'" text-anchor="end">'+esc(q.label)+'</text><rect x="'+Math.min(zero,end)+'" y="'+y+'" width="'+Math.max(1,Math.abs(end-zero))+'" height="23" rx="3" fill="'+(q.color||'var(--color-accent)')+'" opacity=".8"><title>'+esc(q.label+': '+format(q.value))+'</title></rect><text class="bar-value" x="'+(f.w-4)+'" y="'+(y+15)+'" text-anchor="end">'+esc(format(q.value))+'</text>'});
 f.el.innerHTML=svg+'<text x="'+L+'" y="'+(f.h-4)+'">'+esc(format(low))+'</text><text x="'+(f.w-right)+'" y="'+(f.h-4)+'" text-anchor="end">'+esc(format(high))+'</text></svg>';
}
function visualCollapse(id,label){
 const el=$(id);if(!el||el.parentElement.classList.contains('visual-details'))return;
 const d=document.createElement('details');d.className='visual-details';const s=document.createElement('summary');s.textContent=label;el.before(d);d.append(s,el);
}
function visualMount(){
 const panel=document.createElement('section');panel.className='panel visual-panel';panel.id='mc-section';
 panel.innerHTML='<div class="eyebrow">Explore the range, not a price target</div><div class="visual-toolbar"><h2 id="mc-heading">Monte Carlo · scenario explorer</h2><div class="visual-controls"><select id="mc-method" aria-label="Monte Carlo method"><option value="bootstrap">Block bootstrap</option><option value="gbm_zero_log_drift">GBM · zero log drift</option></select><select id="mc-horizon" aria-label="Monte Carlo horizon"><option value="20">20 sessions</option><option value="5">5 sessions</option></select><label><input id="mc-paths" type="checkbox" checked> Show paths</label></div></div><p id="mc-context" class="visual-subtitle"></p><div class="mc-layout"><div><p class="visual-subtitle">Simulated return paths · relative to the retained close</p><div id="mc-fan"></div><div id="mc-legend"></div><div class="mc-inspector"><label for="mc-day">Inspect session</label><input id="mc-day" type="range" min="1" max="20" value="20"><output id="mc-day-label" for="mc-day">20</output></div></div><div><p id="mc-terminal-title" class="visual-subtitle"></p><div id="mc-histogram"></div><p id="mc-negative" class="visual-subtitle"></p></div></div><div id="mc-readout" class="mc-readout" aria-live="polite"></div><details class="visual-details"><summary>Simulation assumptions &amp; source</summary><p id="mc-protocol" class="report-caption"></p></details>';
 $('research').prepend(panel);
 [['research-models','Model scores · exact values'],['research-conformal','Coverage and interval statistics'],['research-factors','Factor estimates and uncertainty'],['research-har-table','Volatility scores · exact values'],['research-technical','Technical indicators · exact values'],['research-timing','Timing performance and costs'],['stock-forecast-table','Forecast scores · exact values'],['stock-vol-table','Volatility scores and diagnostics'],['stock-risk-table','VaR / ES statistics and exceptions'],['stock-scenario-table','Scenario percentiles · exact values']].forEach(([id,label])=>visualCollapse(id,label));
 const additions=[['research-models','research-score-chart','Out-of-sample error · lower is better'],['research-models','research-current-chart','Current model estimates · log return'],['research-conformal','research-interval-chart','Observed outcomes inside and outside the interval'],['research-factors','research-factor-chart','FF5 factor exposures · approximate ±1.96 HAC standard errors'],['research-technical','research-technical-chart','Momentum and distance from moving averages'],['research-timing','research-timing-chart','Maximum drawdown · matched historical study'],['stock-risk-table','stock-tail-chart','One-session loss thresholds · positive loss magnitudes']];
 additions.forEach(([anchor,id,label])=>{const el=document.createElement('div');el.innerHTML='<p class="visual-subtitle">'+label+'</p><div id="'+id+'"></div>';$(anchor).parentElement.before(el)});
 const comparison=document.createElement('div');comparison.className='grid visual-comparison';$('research-score-chart').parentElement.before(comparison);comparison.append($('research-score-chart').parentElement,$('research-current-chart').parentElement);
 const risks=document.createElement('div');risks.className='grid';risks.innerHTML='<section id="research-risk-section" class="panel visual-panel"><h2>Historical tail risk</h2><p class="visual-subtitle">One-session losses · preceding 756 observations</p><div id="research-risk-chart"></div><p class="report-caption">VaR is a loss threshold; ES is the average beyond it. Positive bars show loss magnitudes. Only eight tail observations contribute to 99% ES.</p></section><section class="panel visual-panel"><h2>Drawdown history</h2><p class="visual-subtitle">Below the running peak · last 504 retained sessions</p><div id="research-drawdown-chart"></div><p class="report-caption">The running peak uses the full retained history, including dates before this chart window. It measures the adjusted-return proxy for stocks and the local price index for indices.</p></section>';$('research').append(risks);
 const scenario=document.createElement('div');scenario.id='stock-scenario-chart';$('stock-scenario-table').parentElement.before(scenario);
 ['mc-method','mc-horizon','mc-paths'].forEach(id=>$(id).addEventListener('change',()=>{if(id==='mc-horizon'){$('mc-day').max=$('mc-horizon').value;$('mc-day').value=$('mc-horizon').value}visualMonteCarlo();$('mc-fan').querySelector('svg').classList.add('visual-fade');$('mc-histogram').querySelector('svg').classList.add('visual-fade')}));
 $('mc-day').addEventListener('input',visualMonteCarlo);
}
function visualMonteCarlo(){
 const id=$('research-select').value,s=A.visual_scenarios[id];if(!s)return;
 const horizon=Number($('mc-horizon').value),method=$('mc-method').value,m=s.models[method],day=Math.min(Number($('mc-day').value),horizon),bands=m.bands.slice(0,horizon+1);
 $('mc-heading').textContent=id.toUpperCase()+' · Monte Carlo';$('mc-context').textContent='5,000 simulations · 60 paths shown · '+horizon+' trading sessions · inputs through '+s.cutoff+'.';
 $('mc-day-label').textContent=day;$('mc-protocol').textContent=s.protocol+' Fixed seed '+s.seed+'. '+(s.reproduces_retained_stock_bands?'These bands exactly reproduce the original stock report.':'This visualization applies the same repository scenario protocol to this retained series.');
 const f=visualFrame('mc-fan',id.toUpperCase()+' '+horizon+'-session simulated return paths with pointwise 5th to 95th percentile band',290),L=58,T=16,B=36,R=16,paths=$('mc-paths').checked?m.sample_paths:[],all=[...bands.flat(),...paths.flatMap(p=>p.slice(0,horizon+1))],lo=Math.min(...all,0),hi=Math.max(...all,0),pad=(hi-lo)*.06||.01,min=lo-pad,max=hi+pad;
 const x=i=>L+i/horizon*(f.w-L-R),y=v=>T+(max-v)/(max-min)*(f.h-T-B),points=(a)=>a.map((v,i)=>x(i)+','+y(v)).join(' ');
 let svg=f.svg;
 for(let i=0;i<5;i++){const v=min+(max-min)*i/4,yy=y(v);svg+='<line class="chart-grid" x1="'+L+'" x2="'+(f.w-R)+'" y1="'+yy+'" y2="'+yy+'"/><text x="'+(L-8)+'" y="'+(yy+4)+'" text-anchor="end">'+esc(pct(v))+'</text>'}
 svg+='<line class="chart-zero" x1="'+L+'" x2="'+(f.w-R)+'" y1="'+y(0)+'" y2="'+y(0)+'"/>';
 svg+='<polygon class="chart-band" points="'+points(bands.map(b=>b[2]))+' '+bands.map((b,i)=>x(i)+','+y(b[0])).reverse().join(' ')+'"/>';
 for(const path of paths)svg+='<polyline class="chart-path" points="'+points(path.slice(0,horizon+1))+'"/>';
 svg+='<polyline class="chart-median" points="'+points(bands.map(b=>b[1]))+'"/><line class="chart-cursor" x1="'+x(day)+'" x2="'+x(day)+'" y1="'+T+'" y2="'+(f.h-B)+'"/>';
 for(const [q,label] of [[0,'Today'],[Math.round(horizon/2),'Session '+Math.round(horizon/2)],[horizon,'Session '+horizon]])svg+='<text x="'+x(q)+'" y="'+(f.h-10)+'" text-anchor="'+(q===0?'start':q===horizon?'end':'middle')+'">'+label+'</text>';
 f.el.innerHTML=svg+'</svg>';$('mc-legend').innerHTML=visualLegend([['Median','var(--color-accent)'],['Pointwise 5–95% band','var(--color-accent)',true],...(paths.length?[['60 sampled paths','var(--color-accent)']]:[])]);
 f.el.querySelector('svg').addEventListener('pointermove',event=>{const box=event.currentTarget.getBoundingClientRect(),v=(event.clientX-box.left)*f.w/box.width,n=Math.max(1,Math.min(horizon,Math.round((v-L)/(f.w-L-R)*horizon)));if(n!==Number($('mc-day').value)){$('mc-day').value=n;visualMonteCarlo()}});
 const b=bands[day];$('mc-readout').innerHTML=[['5th percentile',b[0]],['Median · session '+day,b[1]],['95th percentile',b[2]]].map(([label,value])=>'<div><span>'+label+'</span><strong>'+signed(value)+'</strong></div>').join('');
 const hist=m.histograms[String(horizon)],g=visualFrame('mc-histogram',id.toUpperCase()+' distribution of all 5000 simulated '+horizon+'-session returns',290),left=40,bottom=36,top=16,right=12,counts=hist.counts,peak=Math.max(...counts)/s.paths,bw=(g.w-left-right)/counts.length;
 let chart=g.svg;
 for(let i=0;i<4;i++){const v=peak*i/3,yy=g.h-bottom-v/peak*(g.h-bottom-top);chart+='<line class="chart-grid" x1="'+left+'" x2="'+(g.w-right)+'" y1="'+yy+'" y2="'+yy+'"/><text x="'+(left-6)+'" y="'+(yy+4)+'" text-anchor="end">'+(v*100).toFixed(0)+'%</text>'}
 counts.forEach((n,i)=>{const v=n/s.paths,h=v/peak*(g.h-bottom-top),negative=(hist.edges[i]+hist.edges[i+1])/2<0;chart+='<rect x="'+(left+i*bw)+'" y="'+(g.h-bottom-h)+'" width="'+Math.max(.5,bw-1)+'" height="'+h+'" fill="'+(negative?'var(--color-negative)':'var(--color-accent)')+'" opacity=".75"><title>'+esc(pct(hist.edges[i])+' to '+pct(hist.edges[i+1])+': '+n+' paths ('+pct(v)+')')+'</title></rect>'});
 for(const [v,anchor,i] of [[hist.edges[0],'start',0],[hist.edges.at(-1),'end',1]])chart+='<text x="'+(i?g.w-right:left)+'" y="'+(g.h-10)+'" text-anchor="'+anchor+'">'+esc(pct(v))+'</text>';
 g.el.innerHTML=chart+'</svg>';$('mc-terminal-title').textContent='Session '+horizon+' outcome distribution · share per bin';$('mc-negative').textContent=pct(hist.negative_fraction)+' of simulated outcomes finish below the starting level. This is a simulation frequency, not an estimated real-world loss probability.';
}
function visualIntervals(h){
 const rows=h.conformal.records.slice(-36),f=visualFrame('research-interval-chart','Last 36 conformal test origins: log return intervals and actual outcomes',270),L=55,R=16,T=16,B=40,values=rows.flatMap(q=>[q.low,q.high,q.actual]),lo=Math.min(...values),hi=Math.max(...values),x=i=>L+i/(rows.length-1||1)*(f.w-L-R),y=v=>T+(hi-v)/(hi-lo||1)*(f.h-T-B);
 let svg=f.svg;for(let i=0;i<4;i++){const v=lo+(hi-lo)*i/3;svg+='<line class="chart-grid" x1="'+L+'" x2="'+(f.w-R)+'" y1="'+y(v)+'" y2="'+y(v)+'"/><text x="'+(L-8)+'" y="'+(y(v)+4)+'" text-anchor="end">'+esc(pct(v))+'</text>'}
 rows.forEach((q,i)=>{const hit=q.actual>=q.low&&q.actual<=q.high;svg+='<line x1="'+x(i)+'" x2="'+x(i)+'" y1="'+y(q.low)+'" y2="'+y(q.high)+'" stroke="var(--color-accent)" stroke-width="3" opacity=".35"/><circle class="actual-point '+(hit?'':'miss-point')+'" cx="'+x(i)+'" cy="'+y(q.actual)+'" r="3.5"><title>'+esc(q.origin+': actual '+pct(q.actual)+', interval '+pct(q.low)+' to '+pct(q.high))+'</title></circle>'});
 svg+='<text x="'+L+'" y="'+(f.h-10)+'">'+rows[0].origin+'</text><text x="'+(f.w-R)+'" y="'+(f.h-10)+'" text-anchor="end">'+rows.at(-1).origin+'</text></svg>';
 f.el.innerHTML=svg+visualLegend([['90% nominal interval','var(--color-accent)',true],['Actual · inside','var(--color-positive)'],['Actual · outside','var(--color-negative)']]);
}
function visualFactors(id){
 const factor=R.factors.assets[id]?.ff5;if(!factor){$('research-factor-chart').innerHTML='<p class="muted">No matched factor regression is fitted for this currency.</p>';return}
 const labels=R.factors.labels.slice(1),values=factor.coefficients.slice(1),errors=factor.hac_standard_errors.slice(1),f=visualFrame('research-factor-chart','FF5 factor exposures with approximate HAC uncertainty',250),L=78,Rm=22,T=20,B=30,lo=Math.min(0,...values.map((v,i)=>v-1.96*errors[i])),hi=Math.max(0,...values.map((v,i)=>v+1.96*errors[i])),x=v=>L+(v-lo)/(hi-lo)*(f.w-L-Rm);
 let svg=f.svg+'<line class="chart-zero" x1="'+x(0)+'" x2="'+x(0)+'" y1="'+T+'" y2="'+(f.h-B)+'"/>';
 values.forEach((v,i)=>{const yy=30+i*40,a=x(v-1.96*errors[i]),b=x(v+1.96*errors[i]);svg+='<text class="bar-label" x="'+(L-8)+'" y="'+(yy+4)+'" text-anchor="end">'+esc(labels[i])+'</text><line x1="'+a+'" x2="'+b+'" y1="'+yy+'" y2="'+yy+'" stroke="var(--color-accent)" stroke-width="2"/><circle cx="'+x(v)+'" cy="'+yy+'" r="5" fill="var(--color-accent)"><title>'+esc(labels[i]+': '+num(v,3)+' ± '+num(1.96*errors[i],3))+'</title></circle>'});
 for(let i=0;i<3;i++){const v=lo+(hi-lo)*i/2;svg+='<text x="'+x(v)+'" y="'+(f.h-7)+'" text-anchor="middle">'+num(v,1)+'×</text>'}f.el.innerHTML=svg+'</svg>';
}
function visualResearch(){
 const id=$('research-select').value,z=R.assets[id];if(!z)return;const h=z.forecasts.find(q=>q.horizon===Number($('research-horizon').value));
 visualMonteCarlo();
 visualBars('research-score-chart','Out-of-sample log-return RMSE, lower is better',Object.entries(h.scores).sort((a,b)=>a[1].rmse-b[1].rmse).map(([m,s])=>({label:m==='gbm'?'Boosting':m==='knn50'?'KNN 50':m.toUpperCase(),value:s.rmse,color:m==='mean'?'var(--color-ink-2)':'var(--color-accent)'})));
 visualBars('research-current-chart',h.horizon+'-session current log-return model estimates',Object.entries(h.current).map(([m,v])=>({label:m==='gbm'?'Boosting':m.toUpperCase(),value:v,color:v<0?'var(--color-negative)':'var(--color-positive)'})));
 visualIntervals(h);visualFactors(id);
 visualBars('research-risk-chart','Historical one-session VaR and expected shortfall',Object.entries(A.assets[id].risk756).flatMap(([level,q])=>[{label:(Number(level)*100)+'% VaR',value:q.var,color:'var(--color-warning)'},{label:(Number(level)*100)+'% ES',value:q.es,color:'var(--color-negative)'}]));
 plot('research-drawdown-chart',[{color:'var(--color-negative)',points:A.assets[id].history.slice(-504).map(q=>({date:q.date,value:q.drawdown}))}],pct);
 const t=z.technical;visualBars('research-technical-chart','Observed momentum and distance from moving averages',[...Object.entries(t.momentum).map(([n,v])=>({label:n+' sessions',value:v,color:v<0?'var(--color-negative)':'var(--color-positive)'})),{label:'vs MA50',value:t.distance_ma50},{label:'vs MA200',value:t.distance_ma200}]);
 $('research-technical-chart').insertAdjacentHTML('beforeend','<p class="visual-subtitle">RSI 14 · '+num(t.rsi14,1)+' / 100. Descriptive indicators, not tested entry signals.</p>');
 visualBars('research-timing-chart','Historical maximum drawdown for buy-and-hold and costed timing',[{label:'Buy & hold',value:z.timing.buy_hold_same_dates.max_drawdown},...Object.entries(z.timing.strategies).map(([cost,q])=>({label:'MA · '+cost+' bps',value:q.stats.max_drawdown,color:'var(--color-negative)'}))]);
 const harLegend=visualLegend([['HAR','var(--series-1)'],['EWMA GK','var(--series-2)'],['Rolling 22 GK','var(--series-3)']]);$('research-har-chart').insertAdjacentHTML('beforeend',harLegend);
}
function visualStock(){
 const s=A.stocks[$('stock-select').value];if(!s)return;
 visualBars('stock-tail-chart','Historical one-session VaR and expected shortfall, positive loss magnitudes',Object.entries(s.risk.current).flatMap(([level,q])=>[{label:(Number(level)*100)+'% VaR',value:q.var,color:'var(--color-warning)'},{label:(Number(level)*100)+'% ES',value:q.es,color:'var(--color-negative)'}]));
 const id=$('stock-select').value,rows=Object.entries(A.visual_scenarios[id].models).flatMap(([m,q])=>[5,20].map(n=>({label:(m==='bootstrap'?'Bootstrap':'GBM')+' · '+n,band:q.bands[n]}))),f=visualFrame('stock-scenario-chart','5th, median and 95th percentile scenario sensitivity',220),L=116,Rm=18,B=30,lo=Math.min(...rows.map(q=>q.band[0]),0),hi=Math.max(...rows.map(q=>q.band[2]),0),x=v=>L+(v-lo)/(hi-lo||1)*(f.w-L-Rm);
 let svg=f.svg+'<line class="chart-zero" x1="'+x(0)+'" x2="'+x(0)+'" y1="12" y2="'+(f.h-B)+'"/>';
 rows.forEach((q,i)=>{const yy=28+i*42;svg+='<text class="bar-label" x="'+(L-8)+'" y="'+(yy+4)+'" text-anchor="end">'+esc(q.label)+'</text><line x1="'+x(q.band[0])+'" x2="'+x(q.band[2])+'" y1="'+yy+'" y2="'+yy+'" stroke="var(--color-accent)" stroke-width="10" opacity=".22"/><circle cx="'+x(q.band[1])+'" cy="'+yy+'" r="5" fill="var(--color-accent)"><title>'+esc(q.label+': '+q.band.map(pct).join(' / '))+'</title></circle>'});
 svg+='<text x="'+L+'" y="'+(f.h-5)+'">'+pct(lo)+'</text><text x="'+(f.w-Rm)+'" y="'+(f.h-5)+'" text-anchor="end">'+pct(hi)+'</text></svg>';f.el.innerHTML=svg+visualLegend([['5th–95th percentile','var(--color-accent)',true],['Median','var(--color-accent)']]);
}
// Improve existing time-series charts with screen-sized coordinates and semantic axes.
plot=function(target,series,format,log=false){
 const el=$(target),pts=series.flatMap(s=>s.points).filter(p=>Number.isFinite(p.value)&&(!log||p.value>0));if(!pts.length){el.innerHTML='<p class="muted">No retained observations.</p>';return}
 const f=visualFrame(target,el.closest('section')?.querySelector('h2')?.textContent||target,290),L=60,Rm=18,T=16,B=38,transform=v=>log?Math.log(v):v,times=pts.map(q=>Date.parse(q.date)),start=Math.min(...times),end=Math.max(...times),vals=pts.map(q=>transform(q.value)),pad=(Math.max(...vals)-Math.min(...vals))*.08||.01,lo=Math.min(...vals)-pad,hi=Math.max(...vals)+pad,x=d=>L+(Date.parse(d)-start)/(end-start||1)*(f.w-L-Rm),y=v=>T+(hi-transform(v))/(hi-lo)*(f.h-T-B);
 let svg=f.svg;for(let i=0;i<5;i++){const v=lo+(hi-lo)*i/4,yy=T+(hi-v)/(hi-lo)*(f.h-T-B);svg+='<line class="chart-grid" x1="'+L+'" x2="'+(f.w-Rm)+'" y1="'+yy+'" y2="'+yy+'"/><text x="'+(L-8)+'" y="'+(yy+4)+'" text-anchor="end">'+esc(format(log?Math.exp(v):v))+'</text>'}
 if(!log&&lo<0&&hi>0)svg+='<line class="chart-zero" x1="'+L+'" x2="'+(f.w-Rm)+'" y1="'+y(0)+'" y2="'+y(0)+'"/>';
 series.forEach(s=>{const p=s.points.filter(q=>Number.isFinite(q.value)&&(!log||q.value>0));svg+='<polyline fill="none" stroke="'+s.color+'" stroke-width="1.8" points="'+p.map(q=>x(q.date)+','+y(q.value)).join(' ')+'"/>'});
 [[start,'start'],[end,'end']].forEach(([t,anchor])=>svg+='<text x="'+x(new Date(t).toISOString().slice(0,10))+'" y="'+(f.h-10)+'" text-anchor="'+anchor+'">'+new Date(t).toISOString().slice(0,10)+'</text>');el.innerHTML=svg+'</svg>';
};
visualMount();
const visualOldResearch=researchAsset,visualOldStock=renderStock;
researchAsset=function(){visualOldResearch();visualResearch()};renderStock=function(){visualOldStock();visualStock()};
['research-select','research-horizon'].forEach(id=>$(id).addEventListener('change',visualResearch));
['stock-select','stock-horizon'].forEach(id=>$(id).addEventListener('change',visualStock));
researchAsset();renderStock();
let visualResizeTimer;window.addEventListener('resize',()=>{clearTimeout(visualResizeTimer);visualResizeTimer=setTimeout(()=>{if(!$('research').hidden)researchAsset();if(!$('stocks').hidden)renderStock()},150)});
