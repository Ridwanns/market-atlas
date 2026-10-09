"""One compact dashboard with all detailed research retained in a disclosure."""
import re
import json
from pathlib import Path
from investment_decision_data import build_decision_data
ROOT=Path(__file__).resolve().parent

def simplify(template):
    header=(ROOT/'pro-header.html').read_text(encoding='utf-8')+'\n'+(ROOT/'pro-navigation.html').read_text(encoding='utf-8')
    template=re.sub(r'<header class="hero">.*?</header>',lambda _:header,template,count=1,flags=re.S)
    plan=re.search(r'<section id="simple-plan".*?</section>',(ROOT/'simple-panels.html').read_text(encoding='utf-8'),re.S).group()
    compact=(ROOT/'pro-panels.html').read_text(encoding='utf-8').replace('__PLAN__',plan)
    compact=compact.replace('<details id="advanced-details"',(ROOT/'ai-portfolio.html').read_text(encoding='utf-8')+'\n'+(ROOT/'quant-workspace.html').read_text(encoding='utf-8')+'\n'+(ROOT/'investment-decision.html').read_text(encoding='utf-8')+'\n<details id="advanced-details"',1)
    template=re.sub(r'<nav class="nav".*?</nav>',lambda _:compact,template,count=1,flags=re.S)
    styles='\n'.join((ROOT/name).read_text(encoding='utf-8') for name in ['simple-style.css','compact-style.css','fonts.css','tokens.css','pro-design.css','model-visuals.css','ai-portfolio.css','quant-workspace.css','investment-decision.css','focus-portfolio.css'])
    template=template.replace('<style>','<style>\n/* Hallmark · macrostructure: Workbench · tone: modern-minimal · anchor hue: cobalt\n * pre-emit critique: P4 H5 E4 S5 R4 V4 · responsive and contrast: design-references/receipt.json */',1)
    template=template.replace('</style>',styles+'\n</style>',1)
    quant=json.loads((ROOT/'results/2026-10-09/focused-portfolio.json').read_text(encoding='utf-8'))
    quant_data=json.dumps(quant,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('<','\\u003c').replace('&','\\u0026')
    decision_data=json.dumps(build_decision_data(),ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('<','\\u003c').replace('&','\\u0026')
    scripts='const Q='+quant_data+';\nconst D='+decision_data+';\n'+'\n'.join((ROOT/name).read_text(encoding='utf-8') for name in ['simple-ui.js','live-ui.js','pro-design.js','pro-navigation.js','model-visuals.js','ai-portfolio.js','quant-workspace.js','quant-integration.js','decision-math.js','investment-decision.js','decision-integration.js','focus-portfolio.js'])
    template=template.replace('</script></body>',scripts+'\n</script></body>',1)
    template=template.replace('Built for the retained 29 September 2026 market snapshot · One offline English artifact · No automated trades or live-data claims.','Auto-refresh: 60 seconds · Public-feed delays may apply · Models & filings: 29 September 2026')
    template=template.replace('Auto-refresh: 60 seconds · Public-feed delays may apply · Models & filings: 29 September 2026','Quotes refresh every 60 seconds · Quant inputs through 30 September 2026 · Retained financials and options are separately dated')
    return template
