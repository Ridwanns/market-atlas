"""Rebuild the focused shell from frozen research without rewriting originals."""
import json
import re
from pathlib import Path
from simple_shell import simplify

ROOT=Path(__file__).resolve().parent

def main():
    current=(ROOT/'combined-market-report.html').read_text(encoding='utf-8')
    match=re.search(r'<script type="application/json" id="combined-data">(.*?)</script>',current,re.S)
    payload=json.loads(match.group(1))
    payload['analysis']=json.loads((ROOT/'results/2026-09-29/combined-analysis.json').read_text(encoding='utf-8'))
    snapshot=ROOT/'.github-publish/market-atlas/site/data/quotes.json'
    if snapshot.exists():
        payload['analysis']['entry_snapshot']['quotes']=json.loads(snapshot.read_text())['quotes']
    data=json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('<','\\u003c').replace('&','\\u0026')
    template=(ROOT/'combined-template.html').read_text(encoding='utf-8')
    template=template.replace('<div id="methods"',(ROOT/'research-panels.html').read_text(encoding='utf-8')+'\n<div id="methods"',1)
    template=template.replace('<button data-view="methods"','<button data-view="research">Repository research</button><button data-view="financials">Financial history</button><button data-view="sector">Sector portfolios</button><button data-view="options-new">Stock options</button><button data-view="coverage">Repository coverage</button><button data-view="methods"',1)
    template=template.replace('</script></body>',(ROOT/'research-ui.js').read_text(encoding='utf-8')+'\n</script></body>',1)
    template=template.replace('The added stocks do not extend the existing portfolio simulations or NVDA options calibration.','Retained repository studies are archived separately. Your current dashboard focuses on NVDA, TSM, MU and SPY, with three indices kept for context.')
    template=template.replace('Colors: equal weight green,','Colors: buy-and-hold gray, equal weight green,')
    template=template.replace(".textContent='Heston and Bates each cover '",".textContent='The retained NVDA Heston and Bates models each cover '")
    (ROOT/'combined-market-report.html').write_text(simplify(template).replace('__COMBINED_DATA__',data),encoding='utf-8')
    print('Built four-asset dashboard; original research files preserved')

if __name__=='__main__':main()
