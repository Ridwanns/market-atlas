"""Auditable, filing-cutoff-aware fundamentals for the investment decision panel.

Only standard-library modules are used. Monetary amounts are absolute currency
units and shares are absolute shares, never implicitly millions or ADR units.
"""
import argparse
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
CUTOFF = '2026-10-01'
FOLDER = ROOT / 'data' / CUTOFF / 'investment-decision'
OUTPUT = ROOT / 'results' / CUTOFF / 'decision-fundamentals.json'
CIKS = {'nvda':1045810, 'tsm':1046179, 'intc':50863, 'amd':2488,
        'mu':723125, 'avgo':1730168, 'etn':1551182, 'vrt':1674101,
        'alab':1736297, 'crdo':1807794}
MANIFEST = []
ERRORS = []
FLOW_KEYS = ('revenue','gross_profit','operating_income','net_income','cfo','capex','tax','pretax_income')
US_TAGS = {
    'revenue':['RevenueFromContractWithCustomerExcludingAssessedTax','Revenues','SalesRevenueNet'],
    'gross_profit':['GrossProfit'], 'operating_income':['OperatingIncomeLoss'],
    'net_income':['NetIncomeLoss','ProfitLoss'], 'eps_diluted':['EarningsPerShareDiluted'],
    'shares_diluted':['WeightedAverageNumberOfDilutedSharesOutstanding'],
    'cfo':['NetCashProvidedByUsedInOperatingActivities','NetCashProvidedByUsedInOperatingActivitiesContinuingOperations'],
    'capex':['PaymentsToAcquirePropertyPlantAndEquipment','PaymentsToAcquireProductiveAssets'],
    'tax':['IncomeTaxExpenseBenefit'],
    'pretax_income':['IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
                     'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments'],
    'cash':['CashAndCashEquivalentsAtCarryingValue'], 'short_term_investments':['ShortTermInvestments'],
    'assets':['Assets'], 'equity':['StockholdersEquity','StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'], 'liabilities':['Liabilities'],
    'current_assets':['AssetsCurrent'], 'current_liabilities':['LiabilitiesCurrent'],
    'debt_current':['DebtCurrent','LongTermDebtCurrent','LongTermDebtAndCapitalLeaseObligationsCurrent'],
    'debt_noncurrent':['LongTermDebtNoncurrent','LongTermDebtAndCapitalLeaseObligations'],
    'debt_total':['LongTermDebt'], 'short_term_borrowings':['ShortTermBorrowings'],
    'shares_outstanding':['EntityCommonStockSharesOutstanding','CommonStockSharesOutstanding'],
}
IFRS_TAGS = {
    'revenue':['RevenueFromContractsWithCustomers','Revenue'], 'gross_profit':['GrossProfit'],
    'operating_income':['ProfitLossFromOperatingActivities'],
    'net_income':['ProfitLossAttributableToOwnersOfParent'],
    'eps_diluted':['DilutedEarningsLossPerShare'],
    'shares_diluted':['WeightedAverageNumberOfDilutedSharesOutstanding'],
    'cfo':['CashFlowsFromUsedInOperatingActivities'],
    'capex':['PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities'],
    'tax':['IncomeTaxExpenseContinuingOperations'], 'pretax_income':['ProfitLossBeforeTax'],
    'cash':['CashAndCashEquivalents'], 'short_term_investments':[],
    'assets':['Assets'],'current_assets':['CurrentAssets'],'liabilities':['Liabilities'],
    'current_liabilities':['CurrentLiabilities'],'equity':['EquityAttributableToOwnersOfParent'],
    'debt_current':['CurrentBorrowings'], 'debt_noncurrent':['NoncurrentBorrowings'],
    'debt_total':[], 'short_term_borrowings':[],
    'shares_outstanding':['EntityCommonStockSharesOutstanding'],
}
MU_URL = 'https://investors.micron.com/news/press-release/2026/Micron-Technology-Inc--Reports-Record-Fiscal-Fourth-Quarter-and-Full-Year-2026-Results/default.aspx'
TSM_Q2_URL = 'https://www.sec.gov/Archives/edgar/data/1046179/000104617926000541/a2026q2consolidatedreport-.htm'
TSM_Q1_URL = 'https://www.sec.gov/Archives/edgar/data/1046179/000104617926000278/a2026q1consolidatedreport-.htm'
TSM_ANNUAL_URL = 'https://www.sec.gov/Archives/edgar/data/1046179/000162828026025362/tsm-20251231.htm'
FED_URL = 'https://www.federalreserve.gov/releases/h10/current/'

def download(filename, url):
    FOLDER.mkdir(parents=True, exist_ok=True)
    path = FOLDER / filename
    if not path.exists():
        request = urllib.request.Request(url, headers={'User-Agent':'QuantResearch/1.0 research@example.com'})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    raw = response.read()
                path.write_bytes(raw)
                break
            except Exception:
                if attempt == 2: raise
                time.sleep(1 + attempt)
    raw = path.read_bytes()
    row = {'file':str(path.relative_to(ROOT)).replace('\\','/'), 'url':url,
           'sha256':hashlib.sha256(raw).hexdigest(), 'bytes':len(raw),
           'retrieved_utc':dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).isoformat()}
    if not any(s['file']==row['file'] for s in MANIFEST): MANIFEST.append(row)
    return raw, row

def fetch_all():
    errors = []
    for id, cik in CIKS.items():
        for kind, url in [('companyfacts',f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json'),
                          ('submissions',f'https://data.sec.gov/submissions/CIK{cik:010d}.json')]:
            try:
                raw, _ = download(f'{id}-{kind}-raw.json',url)
                parsed = json.loads(raw)
                if kind=='companyfacts': print(id, parsed.get('entityName'),flush=True)
            except Exception as error:
                errors.append({'id':id,'kind':kind,'url':url,'error':str(error)})
    (FOLDER/'provenance.json').write_text(json.dumps({'cutoff':CUTOFF,'sources':MANIFEST,'errors':errors},indent=2),encoding='utf-8')
    return errors

def days(start,end):
    return (dt.date.fromisoformat(end)-dt.date.fromisoformat(start)).days+1

def next_day(date):
    return (dt.date.fromisoformat(date)+dt.timedelta(days=1)).isoformat()

def prev_day(date):
    return (dt.date.fromisoformat(date)-dt.timedelta(days=1)).isoformat()

def ratio(a,b):
    return a/b if a is not None and b is not None and b!=0 else None

def numeric(text):
    text=text.strip().replace('$','').replace(',','').replace('\u2212','-')
    if text in ('-','—','–'): return 0.0
    if not re.fullmatch(r'\(?[-+]?\d+(?:\.\d+)?\)?',text): return None
    sign=-1 if text.startswith('(') else 1
    return sign*float(text.strip('()'))

class Tables(HTMLParser):
    """Read statement cells without executing any publisher HTML or scripts."""
    def __init__(self):
        super().__init__(); self.rows=[]; self.row=None; self.cell=None; self.text=[]
    def handle_starttag(self,tag,attrs):
        if tag=='tr': self.row=[]
        if tag in ('td','th'): self.cell=''
    def handle_data(self,data):
        self.text.append(data)
        if self.cell is not None: self.cell+=data
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.row is not None and self.cell is not None:
            self.row.append(' '.join(self.cell.split())); self.cell=None
        if tag=='tr' and self.row is not None:
            self.rows.append(self.row); self.row=None
    def find_row(self,label,count=None,start=0,stop=None,prefix=False):
        for n in range(start,len(self.rows) if stop is None else stop):
            row=self.rows[n]
            if not row: continue
            actual=row[0].casefold()
            if actual.startswith(label.casefold()) if prefix else actual==label.casefold():
                values=[numeric(c) for c in row[1:] if numeric(c) is not None]
                if count is None or len(values)==count:
                    return n,row,values
        raise ValueError('Statement row not found: '+label)

class InlineFacts(HTMLParser):
    def __init__(self):
        super().__init__();self.contexts={};self.units={};self.facts=[]
        self.context=None;self.unit=None;self.field=None;self.fact=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='xbrli:context':self.context=a.get('id');self.contexts[self.context]={}
        if tag=='xbrli:unit':self.unit=a.get('id');self.units[self.unit]=''
        if tag in ('xbrli:startdate','xbrli:enddate','xbrli:instant','xbrli:measure'):self.field=tag.split(':')[-1]
        if tag in ('xbrldi:explicitmember','xbrldi:typedmember') and self.context:self.contexts[self.context]['dimensioned']=True
        if tag=='ix:nonfraction':self.fact={'attrs':a,'text':''}
    def handle_data(self,text):
        if self.field and self.context:self.contexts[self.context][self.field]=self.contexts[self.context].get(self.field,'')+text
        if self.field=='measure' and self.unit:self.units[self.unit]+=text
        if self.fact:self.fact['text']+=text
    def handle_endtag(self,tag):
        if tag=='ix:nonfraction' and self.fact:self.facts.append(self.fact);self.fact=None
        if tag=='xbrli:context':self.context=None
        if tag=='xbrli:unit':self.unit=None
        if tag in ('xbrli:startdate','xbrli:enddate','xbrli:instant','xbrli:measure'):self.field=None

def inline_records(filename,url,filed,accn,form):
    raw,source=download(filename,url)
    p=InlineFacts(); p.feed(raw.decode('utf-8'))
    result=[]
    for f in p.facts:
        a=f['attrs'];c=p.contexts.get(a.get('contextref'),{})
        if c.get('dimensioned') or a.get('xsi:nil')=='true':continue
        val=numeric(f['text'])
        if val is None and a.get('format','').endswith('fixed-zero'):val=0
        if val is None:continue
        val*=10**int(a.get('scale','0'))
        if a.get('sign')=='-':val=-abs(val)
        u=p.units.get(a.get('unitref'),'')
        if 'shares' in u:unit='TWD/shares' if 'TWD' in u else 'USD/shares' if 'USD' in u else 'shares'
        elif 'TWD' in u:unit='TWD'
        elif 'USD' in u:unit='USD'
        else:continue
        result.append({'tag':a.get('name'),'start':c.get('startdate'),'end':c.get('enddate',c.get('instant')),
                       'unit':unit,'val':val,'filed':filed,'accn':accn,'form':form,
                       'source_url':url,'source_file':source['file'],'sha256':source['sha256'],
                       'basis':'Consolidated dimension-free inline XBRL fact','element_id':a.get('id')})
    return result

def table_record(measure,value,unit,start,end,filed,accn,source,row_number,row_cells,basis='Reported statement row'):
    return {'measure':measure,'val':value,'unit':unit,'start':start,'end':end,
            'filed':filed,'accn':accn,'form':'6-K' if 'tsm' in source['file'] else '8-K earnings release',
            'tag':'statement:'+measure,'source_url':source['url'],'source_file':source['file'],
            'sha256':source['sha256'],'basis':basis,'row_number':row_number,'row_cells':row_cells}

def mu_records():
    raw,source=download('mu-latest-release-raw.html',MU_URL)
    p=Tables();p.feed(raw.decode('utf-8'))
    # Dates and GAAP financial-statement columns are verified against the issuer release.
    assert 'September 3' in raw.decode('utf-8') and 'September 30, 2026' in raw.decode('utf-8')
    result=[]; accn='0000723125-26-000018'; filed='2026-09-30'
    periods=[('2026-05-29','2026-09-03'),('2026-02-27','2026-05-28'),('2025-05-30','2025-08-28'),
             ('2025-08-29','2026-09-03'),('2024-08-30','2025-08-28')]
    for key,label,scale in [('revenue','Revenue',1e6),('gross_profit','Gross margin',1e6),
                            ('operating_income','Operating income',1e6),('net_income','Net income',1e6),
                            ('eps_diluted','Diluted',1),('shares_diluted','Diluted',1e6),
                            ('tax','Income tax (provision) benefit',-1e6)]:
        start=80 if key=='shares_diluted' else 54
        n,row,values=p.find_row(label,5,start=start)
        for (a,b),v in zip(periods,values):
            result.append(table_record(key,v*scale,'USD/shares' if key=='eps_diluted' else 'shares' if key=='shares_diluted' else 'USD',a,b,filed,accn,source,n,row,'Issuer GAAP statement; unaudited earnings release'))
    # The statement's subtotal immediately before tax is unlabelled. Locate it
    # by the tax row and five GAAP date columns rather than computing NI + tax,
    # which would wrongly include the following equity-method income line.
    tax_n,_,_=p.find_row('Income tax (provision) benefit',5,start=54)
    for n in range(tax_n-1,max(53,tax_n-5),-1):
        row=p.rows[n];values=[numeric(c) for c in row[1:] if numeric(c) is not None]
        if row and row[0]=='' and len(values)==5:
            for (a,b),v in zip(periods,values):
                result.append(table_record('pretax_income',v*1e6,'USD',a,b,filed,accn,source,n,row,'GAAP income before tax/equity-method income: reported subtotal immediately before tax row'))
            break
    else:raise ValueError('Micron reported pretax-income subtotal unavailable')
    # Full-year CFO is independently reported; quarter CFO comes from the release's reconciliation.
    n,row,values=p.find_row('Net cash provided by operating activities',2,start=120)
    for (a,b),v in zip(periods[3:],values):
        result.append(table_record('cfo',v*1e6,'USD',a,b,filed,accn,source,n,row,'Issuer consolidated full-year cash-flow statement; unaudited'))
    n,row,values=p.find_row('Expenditures for property, plant, and equipment',5,start=180)
    for (a,b),v in zip(periods,values):
        result.append(table_record('capex',abs(v)*1e6,'USD',a,b,filed,accn,source,n,row,'Gross cash PP&E expenditures; government incentives and asset sales are not netted'))
    n,row,values=p.find_row('GAAP net cash provided by operating activities',5,start=180)
    for (a,b),v in zip(periods,values):
        result.append(table_record('cfo',v*1e6,'USD',a,b,filed,accn,source,n,row,'GAAP CFO row in the issuer FCF reconciliation; not adjusted free cash flow'))
    balance_periods=['2026-09-03','2026-05-28','2025-08-28']
    for key,label in [('cash','Cash and equivalents'),('short_term_investments','Short-term investments'),
                      ('assets','Total assets'),('liabilities','Total liabilities'),('equity','Total equity'),
                      ('debt_current','Current debt'),('debt_noncurrent','Long-term debt'),
                      ('current_assets','Total current assets'),('current_liabilities','Total current liabilities')]:
        n,row,values=p.find_row(label,3,start=85,stop=120)
        for b,v in zip(balance_periods,values):
            result.append(table_record(key,v*1e6,'USD',None,b,filed,accn,source,n,row,'Issuer consolidated balance sheet; unaudited'))
    return result

def tsm_records():
    result=inline_records('tsm-latest-20f-raw.html',TSM_ANNUAL_URL,'2026-04-16','0001628280-26-025362','20-F')
    for name,url,filed,accn,q in [('tsm-latest-statement-raw.html',TSM_Q2_URL,'2026-08-14','0001046179-26-000541',2),
                                 ('tsm-q1-statement-raw.html',TSM_Q1_URL,'2026-05-15','0001046179-26-000278',1)]:
        raw,source=download(name,url);p=Tables();p.feed(raw.decode('utf-8'))
        periods=[('2026-04-01','2026-06-30'),('2025-04-01','2025-06-30'),('2026-01-01','2026-06-30'),('2025-01-01','2025-06-30')] if q==2 else [('2026-01-01','2026-03-31'),('2025-01-01','2025-03-31')]
        # Income statement uses alternating amounts/percentages; select only amount columns.
        for key,label,scale in [('revenue','NET REVENUE',1000),('gross_profit','GROSS PROFIT',1000),
                               ('operating_income','INCOME FROM OPERATIONS',1000),('net_income','Shareholders of the parent',1000),
                               ('pretax_income','INCOME BEFORE INCOME TAX',1000),('tax','INCOME TAX EXPENSE',1000),
                               ('eps_diluted','Diluted earnings per share',1)]:
            n,row,values=p.find_row(label,start=90,prefix=True)
            # EPS has no percentage columns; primary statement other rows do.
            values=values if key=='eps_diluted' else values[::2]
            assert len(values)==len(periods),(key,values,periods)
            for (a,b),v in zip(periods,values):
                result.append(table_record(key,v*scale,'TWD/shares' if key=='eps_diluted' else 'TWD',a,b,filed,accn,source,n,row,'TIFRS consolidated amount; parent-attributable net income'))
        n,row,values=p.find_row('Weighted average number of common shares used in the computation of diluted EPS',start=600,prefix=True)
        assert len(values)==len(periods)
        for (a,b),v in zip(periods,values):
            result.append(table_record('shares_diluted',v*1000,'shares',a,b,filed,accn,source,n,row,'Reported weighted-average diluted ordinary shares (statement in thousands); ADR ratio 5'))
        ytd_periods=periods[2:] if q==2 else periods
        for key,label in [('cfo','Net cash generated by operating activities'),('capex','Payments for acquisition of property, plant and equipment')]:
            n,row,values=p.find_row(label,2)
            for (a,b),v in zip(ytd_periods,values):
                result.append(table_record(key,v*1000,'TWD',a,b,filed,accn,source,n,row,'TIFRS consolidated cash flow; cash PP&E purchases excluding grants/disposal proceeds' if key=='capex' else 'TIFRS consolidated reported CFO'))
        balance_periods=['2026-06-30','2025-12-31','2025-06-30'] if q==2 else ['2026-03-31','2025-12-31','2025-03-31']
        for key,label in [('cash','Cash and cash equivalents'),('assets','TOTAL'),('equity','Equity attributable to shareholders of the parent'),
                          ('liabilities','Total liabilities'),('current_assets','Total current assets'),('current_liabilities','Total current liabilities')]:
            n,row,values=p.find_row(label,6,start=10,stop=95,prefix=key!='assets')
            values=values[::2]
            assert len(values)==3
            for b,v in zip(balance_periods,values):
                result.append(table_record(key,v*1000,'TWD',None,b,filed,accn,source,n,row,'TIFRS consolidated balance sheet; NT dollars'))
        # All borrowing components are in the balance sheet and accompanying borrowing notes.
        # Current long-term liabilities here contain only current bonds/bank debt (Notes 17/18).
        for key,label in [('debt_current','Long-term liabilities - current portion'),('bonds_noncurrent','Bonds payable'),('bank_noncurrent','Long-term bank loans')]:
            n,row,values=p.find_row(label,start=45,stop=75,prefix=True);values=values[::2]
            for b,v in zip(balance_periods,values):
                result.append(table_record(key,v*1000,'TWD',None,b,filed,accn,source,n,row,'Reported bonds/bank borrowing carrying amount; operating leases excluded'))
    return result

class Facts:
    def __init__(self,id):
        self.id=id;self.cik=CIKS[id];self.currency='TWD' if id=='tsm' else 'USD'
        raw,source=download(f'{id}-companyfacts-raw.json',f'https://data.sec.gov/api/xbrl/companyfacts/CIK{self.cik:010d}.json')
        data=json.loads(raw);self.name=data['entityName'];self.source=source
        subraw,_=download(f'{id}-submissions-raw.json',f'https://data.sec.gov/submissions/CIK{self.cik:010d}.json')
        self.sub=json.loads(subraw)['filings']['recent'];self.urls={}
        for a,p in zip(self.sub['accessionNumber'],self.sub['primaryDocument']):
            self.urls[a]=f'https://www.sec.gov/Archives/edgar/data/{self.cik}/{a.replace("-","")}/{p}'
        supplements=tsm_records() if id=='tsm' else mu_records() if id=='mu' else []
        if id in ('nvda','etn','alab','crdo'):
            n=next(i for i,f in enumerate(self.sub['form']) if f=='10-Q' and self.sub['filingDate'][i]<=CUTOFF)
            a=self.sub['accessionNumber'][n]
            supplements+=inline_records(f'{id}-latest-10q-raw.html',self.urls[a],self.sub['filingDate'][n],a,'10-Q')
        self.tags=IFRS_TAGS if id=='tsm' else US_TAGS
        self.rows={}
        for key,tags in self.tags.items():
            unit='shares' if key.startswith('shares_') else self.currency+'/shares' if key=='eps_diluted' else self.currency
            records=[]
            for priority,tag in enumerate(tags):
                for ns,g in data['facts'].items():
                    for row in g.get(tag,{}).get('units',{}).get(unit,[]):
                        # Compensation/proxy financial facts can use the same tag but are
                        # not replacement primary financial statements or restatements.
                        if row.get('form') not in ('10-K','10-K/A','10-Q','10-Q/A','20-F','20-F/A','40-F','40-F/A','6-K'):
                            continue
                        records.append({**row,'tag':ns+':'+tag,'unit':unit,'priority':priority,
                                        'source_url':self.urls.get(row.get('accn'),f'https://www.sec.gov/Archives/edgar/data/{self.cik}/{row.get("accn","").replace("-","")}/{row.get("accn","")}-index.html'),
                                        'source_file':source['file'],'sha256':source['sha256'],
                                        'basis':'Reported SEC companyfacts consolidated fact'})
            for row in supplements:
                if (row.get('measure')==key or row['tag'].split(':')[-1] in tags) and row['unit']==unit:
                    records.append({**row,'priority':-1})
            chosen={}
            for row in sorted(records,key=lambda r:(r.get('filed',''),-r['priority'],bool(r.get('frame')))):
                if row.get('filed','9999')<=CUTOFF and row.get('end','9999')<=CUTOFF and row.get('end'):
                    chosen[(row.get('start'),row['end'])]=row
            self.rows[key]=chosen
        if id=='tsm':
            for key in ('bonds_noncurrent','bank_noncurrent'):
                self.rows[key]={(r.get('start'),r['end']):r for r in supplements if r.get('measure')==key}
        (FOLDER/f'{id}-supplement-extracted.json').write_text(json.dumps(supplements,indent=2,allow_nan=False),encoding='utf-8')

    def direct(self,key,start,end):
        return self.rows.get(key,{}).get((start,end))

    def instant(self,key,end,exact=True):
        rows=[r for (a,b),r in self.rows.get(key,{}).items() if not a and (b==end if exact else b<=end)]
        return max(rows,key=lambda r:(r['end'],r['filed'])) if rows else None

    def duration(self,key,start,end):
        row=self.direct(key,start,end)
        if row:return row
        if key in ('eps_diluted','shares_diluted'):return None
        # Derive standalone cash-flow/income quarter only from same-start cumulative facts.
        for (a,b),full in sorted(self.rows.get(key,{}).items(),key=lambda x:x[0][0] or ''):
            if a and a<start and b==end and days(a,b)<=385:
                prior=self.direct(key,a,prev_day(start))
                if prior:return derived(full['val']-prior['val'],key,start,end,[full,prior],self.currency,'Same fiscal-start cumulative period less exact preceding cumulative period')
        return None

def audit(row):
    if row is None:return None
    result={'value':row['val'],'unit':row.get('unit'),'period':{'start':row.get('start'),'end':row['end']},
            'filed':row.get('filed'),'accession':row.get('accn'),'form':row.get('form'),
            'tag':row.get('tag'),'basis':row.get('basis'),'source_url':row.get('source_url'),
            'source_file':row.get('source_file'),'sha256':row.get('sha256')}
    for key in ('row_number','row_cells','element_id','formula'):
        if key in row:result[key]=row[key]
    if 'components' in row:result['components']=[audit(r) for r in row['components']]
    return result

def derived(val,key,start,end,components,currency,basis,formula=None):
    return {'val':val,'tag':'derived:'+key,'start':start,'end':end,'unit':currency,
            'filed':max(r.get('filed','') for r in components),'accn':None,'form':'Derived from reported data',
            'source_url':components[0].get('source_url'),'components':components,'basis':basis,'formula':formula or basis}

def period(f,start,end):
    keys=FLOW_KEYS+('eps_diluted','shares_diluted')
    records={key:f.duration(key,start,end) for key in keys}
    cfo,capex=records['cfo'],records['capex']
    records['fcf']=derived(cfo['val']-capex['val'],'fcf',start,end,[cfo,capex],f.currency,'Reported CFO minus reported gross capital asset cash purchases; company adjusted FCF not used','CFO - Capex') if cfo and capex else None
    values={key:r['val'] if r else None for key,r in records.items()}
    values.update({'start':start,'end':end,'days':days(start,end),'currency':f.currency,
                   'filed':max((r['filed'] for r in records.values() if r),default=None),
                   'audit':{k:audit(r) for k,r in records.items()}})
    for name,a,b in [('net_margin','net_income','revenue'),('gross_margin','gross_profit','revenue'),
                     ('operating_margin','operating_income','revenue'),('fcf_margin','fcf','revenue'),
                     ('cfo_to_income','cfo','net_income'),('capex_to_revenue','capex','revenue')]:
        values[name]=ratio(values[a],values[b])
    return values

def ttm(f,latest,annual):
    end=latest['end']
    eligible=[a for a in annual if a['end']<=end]
    if not eligible:return None
    last=eligible[-1]; records={}
    if last['end']==end:
        start=last['start'];basis='Most recently reported complete fiscal year'
        for key in FLOW_KEYS:records[key]=f.direct(key,start,end)
    else:
        current_start=next_day(last['end']);prior_start=last['start']
        current_ytd=f.direct('revenue',current_start,end)
        candidates=[r for (a,b),r in f.rows['revenue'].items() if a==prior_start
                    and 350<=days(b,end)<=380 and abs(days(a,b)-days(current_start,end))<=8]
        if not current_ytd or not candidates:return None
        # Exact reported prior comparative YTD period; never add overlapping cash-flow YTD rows.
        prev=min(candidates,key=lambda r:abs(days(r['start'],r['end'])-days(current_start,end)))
        prior_end=prev['end'];start=next_day(prior_end);basis='Latest fiscal annual + current fiscal YTD - prior comparable fiscal YTD'
        for key in FLOW_KEYS:
            components=[f.direct(key,last['start'],last['end']),f.direct(key,current_start,end),f.direct(key,prior_start,prior_end)]
            records[key]=derived(components[0]['val']+components[1]['val']-components[2]['val'],key,start,end,components,f.currency,basis,'Annual + Current YTD - Prior YTD') if all(components) else None
    cfo,capex=records['cfo'],records['capex']
    records['fcf']=derived(cfo['val']-capex['val'],'fcf',start,end,[cfo,capex],f.currency,'Reported CFO minus gross capital asset cash purchases','CFO - Capex') if cfo and capex else None
    out={key:r['val'] if r else None for key,r in records.items()}
    out.update({'start':start,'end':end,'days':days(start,end),'currency':f.currency,'basis':basis,
                'filed':max((r['filed'] for r in records.values() if r),default=None),'audit':{k:audit(r) for k,r in records.items()}})
    out['net_margin']=ratio(out['net_income'],out['revenue']);out['fcf_margin']=ratio(out['fcf'],out['revenue'])
    out['cfo_to_income']=ratio(out['cfo'],out['net_income']);out['capex_to_revenue']=ratio(out['capex'],out['revenue'])
    out['effective_tax_rate']=ratio(out['tax'],out['pretax_income'])
    return out

def balance(f,end):
    keys=('cash','short_term_investments','assets','equity','liabilities','current_assets','current_liabilities','debt_current','debt_noncurrent')
    records={key:f.instant(key,end) for key in keys}
    if f.id=='tsm':
        pieces=[f.instant('bonds_noncurrent',end),f.instant('bank_noncurrent',end)]
        records['debt_noncurrent']=derived(sum(r['val'] for r in pieces),'debt_noncurrent',None,end,pieces,f.currency,'Noncurrent bonds carrying amount + noncurrent bank loans') if all(pieces) else None
    if f.id=='etn':
        # Eaton's LongTermDebt includes its current portion; adding DebtCurrent would duplicate it.
        pieces=[f.instant('debt_total',end),f.instant('short_term_borrowings',end)]
        records['debt']=derived(sum(r['val'] for r in pieces),'debt',None,end,pieces,f.currency,'Reported total long-term debt including current portion + separate short-term borrowings; no current double-count') if all(pieces) else None
    else:
        pieces=[records['debt_current'],records['debt_noncurrent']]
        records['debt']=derived(sum(r['val'] for r in pieces),'debt',None,end,pieces,f.currency,'Current debt + noncurrent debt carrying amounts; operating lease liabilities excluded') if all(pieces) else None
    cash,debt=records['cash'],records['debt']
    records['net_cash']=derived(cash['val']-debt['val'],'net_cash',None,end,[cash,debt],f.currency,'Cash and cash equivalents - reported borrowing carrying amounts; securities and operating leases excluded','Cash - Debt') if cash and debt else None
    # Outstanding shares on the cover are later than the balance date; retain their own measurement date.
    records['shares_outstanding']=f.instant('shares_outstanding',CUTOFF,False)
    values={key:r['val'] if r else None for key,r in records.items()}
    values.update({'end':end,'currency':f.currency,'audit':{k:audit(r) for k,r in records.items()}})
    values['current_ratio']=ratio(values['current_assets'],values['current_liabilities'])
    return values

def fed_fx():
    raw,source=download('fed-fx-raw.html',FED_URL);p=Tables();p.feed(raw.decode('utf-8'))
    text=' '.join(p.text)
    released=re.search(r'Release Date:\s*([A-Za-z]+ \d{1,2}, \d{4})',text)
    release_date=dt.datetime.strptime(released[1],'%B %d, %Y').date() if released else None
    if not release_date or release_date.isoformat()>CUTOFF:return None
    n,row,values=p.find_row('TAIWAN',5)
    # Use the actual rate's column header, including duplicate rates on different
    # days. Selecting a date by matching the rate would be ambiguous.
    header=next(row for row in p.rows if row[:2]==['COUNTRY','CURRENCY'])
    column=len(values)+1
    observed=dt.datetime.strptime(header[column].replace('.','')+' '+str(release_date.year),'%b %d %Y').date()
    if observed>release_date:
        observed=observed.replace(year=observed.year-1)
    return {'rate':values[-1],'date':observed.isoformat(),'release_date':release_date.isoformat(),
            'pair':'TWD per USD','source_url':FED_URL,'source_file':source['file'],'sha256':source['sha256'],
            'row_number':n,'row_cells':row,'method':'Divide native TWD amounts by dated H.10 spot rate; this is valuation translation, not company historical USD reporting'}

def analyze(id,fx):
    f=Facts(id); rows=list(f.rows['revenue'].values())
    annual_periods=sorted({(r['start'],r['end']) for r in rows if r.get('start') and 330<=days(r['start'],r['end'])<=385 and r['end']>='2017-01-01'},key=lambda p:p[1])
    quarter_periods={(r['start'],r['end']) for r in rows if r.get('start') and 60<=days(r['start'],r['end'])<=110 and r['end']>='2020-01-01'}
    for a,b in annual_periods:
        nine=[r for r in rows if r.get('start')==a and 250<=days(a,r['end'])<=300 and 60<=days(next_day(r['end']),b)<=110]
        if nine:quarter_periods.add((next_day(max(nine,key=lambda r:r['end'])['end']),b))
    quarters=[period(f,a,b) for a,b in sorted(quarter_periods,key=lambda p:p[1])]
    quarters=[q for q in quarters if q['revenue'] is not None]
    annual=[period(f,a,b) for a,b in annual_periods]
    if not quarters and not annual:raise ValueError('No supported financial reporting period for '+id)
    latest=quarters[-1] if quarters else annual[-1]
    for history in (quarters,annual):
        for i,row in enumerate(history):
            prior=[q for q in history[:i] if 350<=days(q['end'],row['end'])<=380]
            row['revenue_yoy']=ratio(row['revenue'],prior[-1]['revenue'])-1 if prior and prior[-1]['revenue'] else None
    trailing=ttm(f,latest,annual); b=balance(f,latest['end'])
    share=latest['shares_diluted'];prior=[q for q in quarters[:-1] if 350<=days(q['end'],latest['end'])<=380 and q['shares_diluted']]
    prior=prior[-1] if prior else None
    dilution={'yoy':share/prior['shares_diluted']-1 if share and prior else None,'basis':'Latest quarter diluted weighted-average shares / same fiscal quarter a year earlier - 1; buybacks and stock splits also affect this measure',
              'latest_shares':share,'prior_shares':prior['shares_diluted'] if prior else None,
              'audit':{'latest':latest['audit']['shares_diluted'],'prior':prior['audit']['shares_diluted'] if prior else None}}
    roic={'value':None,'basis':'TTM operating income × (1 - TTM effective tax rate) / average (equity + borrowing debt - cash), measured at TTM beginning/end; operating leases and marketable securities excluded',
          'reason':'Comparable beginning/end debt, equity and cash plus a valid TTM tax rate are required.','audit':None}
    if trailing:
        old=balance(f,prev_day(trailing['start']))
        rate=trailing['effective_tax_rate']
        missing=[]
        for when,values in [('beginning',old),('ending',b)]:
            missing += [when+' '+key for key in ('equity','debt','cash') if values[key] is None]
        if trailing['operating_income'] is None:missing.append('TTM operating income')
        if rate is None:missing.append('TTM effective tax rate')
        elif not 0<=rate<=1:missing.append('effective tax rate outside 0–100% ('+str(round(rate*100,2))+'%)')
        if missing:roic['reason']='Unavailable: '+', '.join(missing)+'. No zero balance or normalized tax assumption substituted.'
        if all(v is not None for v in [old['equity'],old['debt'],old['cash'],b['equity'],b['debt'],b['cash'],trailing['operating_income'],rate]) and 0<=rate<=1:
            oldic=old['equity']+old['debt']-old['cash'];newic=b['equity']+b['debt']-b['cash'];average=(oldic+newic)/2
            if average>0:
                roic.update(value=trailing['operating_income']*(1-rate)/average,reason=None,
                            audit={'tax':trailing['audit']['tax'],'pretax_income':trailing['audit']['pretax_income'],
                                   'operating_income':trailing['audit']['operating_income'],'beginning':old['audit'],
                                   'ending':b['audit'],'average_invested_capital':average,'effective_tax_rate':rate})
    conversion=fx if id=='tsm' else {'rate':1,'date':latest['end'],'pair':'USD per USD','method':'Issuer reports USD; no currency conversion'}
    required={'revenue':bool(trailing and trailing['revenue'] is not None),'net_margin':bool(trailing and trailing['net_margin'] is not None),'diluted_shares':share is not None,'usd_conversion':conversion is not None}
    available=all(required.values())
    baseline={'available':available,'reason':None if available else 'Unavailable: '+', '.join(k for k,v in required.items() if not v),
              'revenue_billions_usd':trailing['revenue']/conversion['rate']/1e9 if trailing and trailing['revenue'] is not None and conversion else None,
              'diluted_shares_billions':share/(5 if id=='tsm' else 1)/1e9 if share is not None else None,
              'net_margin':trailing['net_margin'] if trailing else None,
              'net_cash_billions_usd':b['net_cash']/conversion['rate']/1e9 if b['net_cash'] is not None and conversion else None,
              'period':{'start':trailing['start'],'end':trailing['end']} if trailing else None,
              'share_period':{'start':latest['start'],'end':latest['end']},'source':trailing['audit']['revenue']['source_url'] if trailing and trailing['audit']['revenue'] else None,
              'conversion':conversion,'adr_ratio':5 if id=='tsm' else 1,'availability':required,
              'share_basis':'Latest reported quarter GAAP diluted weighted-average ordinary shares divided by 5 per US-listed ADR' if id=='tsm' else 'Latest reported quarter GAAP diluted weighted-average listed shares',
              'audit':{'revenue':trailing['audit']['revenue'] if trailing else None,'net_income':trailing['audit']['net_income'] if trailing else None,'shares':latest['audit']['shares_diluted']}}
    financials={}
    for key in ('revenue','net_income','cfo','capex','fcf','net_margin','fcf_margin','cfo_to_income','capex_to_revenue'):
        value=trailing.get(key) if trailing else None;metric_audit=trailing['audit'].get(key) if trailing else None
        ratio_keys={'net_margin':('net_income','revenue'),'fcf_margin':('fcf','revenue'),
                    'cfo_to_income':('cfo','net_income'),'capex_to_revenue':('capex','revenue')}
        if value is not None and key in ratio_keys:
            numerator,denominator=ratio_keys[key]
            metric_audit={'value':value,'unit':'ratio','period':baseline['period'],'filed':trailing['filed'],
                          'accession':None,'form':'Derived from reported data','tag':'derived:'+key,
                          'basis':numerator+' / '+denominator,'source_url':baseline['source'],
                          'components':[trailing['audit'][numerator],trailing['audit'][denominator]]}
        financials[key]={'value':value,'unit':'ratio' if key in ('net_margin','fcf_margin','cfo_to_income','capex_to_revenue') else f.currency,
                         'period':baseline['period'],'source_url':metric_audit['source_url'] if metric_audit else baseline['source'],
                         'basis':metric_audit['basis'] if metric_audit else 'Ratio of TTM reported measures','available':value is not None,
                         'reason':None if value is not None else 'Required comparable reported facts are unavailable; no estimate substituted','audit':metric_audit}
    for key in ('cash','debt','net_cash','current_ratio','shares_outstanding'):
        value=b.get(key);metric_audit=b['audit'].get(key)
        financials[key]={'value':value,'unit':'shares' if key=='shares_outstanding' else 'ratio' if key=='current_ratio' else f.currency,
                         'period':metric_audit['period'] if metric_audit else {'start':None,'end':b['end']},
                         'source_url':metric_audit['source_url'] if metric_audit else None,'basis':metric_audit['basis'] if metric_audit else 'Comparable borrowing facts are not quantified',
                         'available':value is not None,'reason':None if value is not None else 'No quantified comparable borrowing amount extracted; missing is not assumed zero','audit':metric_audit}
    for key,value,basis,metric_audit in [('shares_diluted',share,baseline['share_basis'],latest['audit']['shares_diluted']),('dilution',dilution['yoy'],dilution['basis'],dilution['audit']),('roic',roic['value'],roic['basis'],roic['audit'])]:
        financials[key]={'value':value,'unit':'shares' if key=='shares_diluted' else 'ratio','period':baseline['share_period'] if key!='roic' else baseline['period'],
                         'source_url':baseline['source'],'basis':basis,'available':value is not None,'reason':None if value is not None else roic['reason'] if key=='roic' else 'Prior comparable diluted share count is unavailable','audit':metric_audit}
    notes=['Only sources filed/released on or before the cutoff and economic periods ended before the cutoff are used. Descriptive histories use the latest available comparative/restated figures; this is not a historical point-in-time feature backtest.',
           'TTM cash flows are latest fiscal annual plus current YTD less matching prior YTD. Quarterly cash flows are exact cumulative differences, never sums of overlapping YTD amounts.',
           'FCF is reported CFO less gross cash capital asset purchases; it is not company adjusted FCF, FCFE, or cash distributable to shareholders. Do not automatically discount it as equity cash flow.',
           'Valuation baseline combines TTM revenue/profit margin with the latest quarter diluted weighted-average share count. This EPS proxy can differ from actual reported TTM EPS; historical observations are not future assumptions.',
           'Net cash includes only cash/cash equivalents minus quantified borrowing carrying amounts; marketable investments and operating leases are excluded. Missing debt is not zero.',
           'ROIC is reported only when matched period beginning/end debt, equity and cash plus a 0–100% effective tax rate are available. It uses a simple book capital definition and is not a standardized company metric.']
    if id=='nvda':notes+=['NVIDIA now reports cash purchases of property/equipment and intangible assets together under PaymentsToAcquireProductiveAssets. Its Capex/FCF includes that combined line, explicitly broader than PP&E alone. Financing payments for previously financed assets are excluded.',
                          'Reported GAAP profit includes non-operating gains/losses. Its high trailing net margin should not be assumed to repeat in a revenue-based forecast without review.']
    if id=='mu':notes.append('Latest FY2026 and FQ4 results are the September 30 unaudited issuer GAAP release, furnished as SEC 8-K EX-99.1. The companyfacts feed still ends at FQ3. FY2026 gross cash PP&E is used, not net Capex after grants or adjusted FCF.')
    if id=='tsm':notes+=['Financial statements are TIFRS in TWD. One US-listed ADR represents five ordinary shares. USD baseline translates all native TWD amounts using the explicitly dated Fed H.10 spot rate; this is not company historical USD revenue or TWD EPS divided directly into a USD ADR price.',
                          'The current quarterly financial period is June 30, 2026. Monthly revenue releases after that are not combined with incomplete quarterly income/cash-flow data.']
    sources=[s for s in MANIFEST if s['file'].split('/')[-1].startswith(id+'-')]
    if id=='tsm':sources+=[s for s in MANIFEST if s['url']==FED_URL]
    return {'id':id,'symbol':id.upper(),'ticker':id.upper(),'entity':f.name,'name':f.name,'cik':f.cik,'currency':f.currency,
            'as_of':CUTOFF,'latest_period':latest,'ttm':trailing,'balance':b,'dilution':dilution,'roic':roic,
            'annual':annual,'quarters':quarters,'financials':financials,'decision_baseline':baseline,
            'sources':sources,'notes':notes,'filing_url':f'https://www.sec.gov/edgar/browse/?CIK={f.cik}&owner=exclude'}

def main(fetch_only=False):
    ERRORS.extend(fetch_all())
    if fetch_only:return
    try:fx=fed_fx()
    except Exception as error:
        ERRORS.append({'id':'tsm','kind':'fx','error':str(error),'url':FED_URL});fx=None
    assets={}
    for id in CIKS:
        try:
            assets[id]=analyze(id,fx);a=assets[id]
            print(id,a['latest_period']['end'],'TTM',a['ttm']['end'] if a['ttm'] else None,'baseline',a['decision_baseline']['available'],'FCF',a['ttm']['fcf'] if a['ttm'] else None,flush=True)
        except Exception as error:
            import traceback;traceback.print_exc()
            ERRORS.append({'id':id,'kind':'analysis','error':str(error)})
            assets[id]={'id':id,'symbol':id.upper(),'as_of':CUTOFF,'error':str(error),'decision_baseline':{'available':False,'reason':str(error)}}
    meta={'cutoff':CUTOFF,'as_of':CUTOFF,'timezone':'Asia/Jakarta','retrieved_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
          'units':'Absolute issuer currency units and absolute share counts. Ratios are decimal fractions. Billions are used only in explicitly named decision_baseline fields.',
          'policy':'Filing/release-date and economic-period cutoff; latest restatements available at cutoff; no guidance or estimated fact fills; exact fiscal annual+YTD-priorYTD TTM cash-flow arithmetic.',
          'sources':MANIFEST,'errors':ERRORS,'fx':fx,'schema_version':1}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps({'meta':meta,'as_of':CUTOFF,'assets':assets},indent=2,allow_nan=False),encoding='utf-8')
    (FOLDER/'provenance.json').write_text(json.dumps(meta,indent=2,allow_nan=False),encoding='utf-8')
    print('Saved',OUTPUT,'errors',len(ERRORS),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--fetch-only',action='store_true')
    args=parser.parse_args()
    main(args.fetch_only)
