import json,re,sys
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')
def load(f):
    d=json.load(open(f,encoding='utf-8'))
    return {p['title']:p.get('revisions',[{}])[0].get('slots',{}).get('main',{}).get('*','') for p in d['query']['pages'].values()}
B=load('fandom/wikitext-B-rooms.json'); C=load('fandom/wikitext-C-courses.json'); D=load('fandom/wikitext-D-items.json')

def infobox(c,name):
    m=re.search(r'\{\{\s*(?:Template:)?%s\s*\n(.*?)\n\}\}'%name,c,re.S)
    if not m: return {}
    out={}; last=None
    for ln in m.group(1).split('\n'):
        mm=re.match(r'\|\s*([A-Za-z0-9]+)\s*=\s?(.*)',ln)
        if mm:
            last=mm.group(1); out[last]=mm.group(2).strip()
        elif last and ln.startswith('{{'):
            out[last]+='\n'+ln.strip()
    return {k:v for k,v in out.items()}

def i2names(s): return [m.group(1).strip() for m in re.finditer(r'\{\{i[23]\|([^}|]+)',s)]
def catlink(s): return [x.group(1) for x in re.finditer(r'\[+:Category:([^\]|]+)',s)]
def plain(s):
    s=re.sub(r'\[+:Category:[^\]|]+\|([^\]]+)\]',r'\1',s)   # keep category link label
    s=re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]',r'\2',s)          # keep wikilink label
    s=re.sub(r'<[^>]+>','',s)
    return re.sub(r'\s+',' ',s).strip()

rows=[]
def add(sk,sn,verb,ok,on,card=None,notes=None,page=None):
    rows.append({"subjectKind":sk,"subjectName":sn,"relationVerb":verb,"objectKind":ok,"objectName":on,
                 **({"cardinalityClaim":card} if card else {}),**({"notes":notes} if notes else {}),
                 "sourcePage":page})

for t,c in sorted(C.items()):
    ib=infobox(c,'Infobox Course')
    unl=i2names(ib.get('unlock',''))
    if unl: add('course',t,'unlocked-at','campus',unl[0],page=t)
    for rm in i2names(ib.get('room','')): add('course',t,'requires-room','room',rm,page=t)
    for a in i2names(ib.get('archetype','')): add('course',t,'enrolls-archetype','archetype',a,page=t)
    diff=plain(ib.get('difficulty','')); dur=plain(ib.get('duration',''))
    if diff: add('course',t,'classified-difficulty','difficulty-class',diff,page=t)
    if dur: add('course',t,'classified-duration','duration-class',dur,page=t)

for t,c in sorted(B.items()):
    ib=infobox(c,'Infobox Room')
    for s in i2names(ib.get('staff','')): add('room',t,'staffed-by','staff-kind',s,page=t)
    cap=ib.get('capacity','').strip()
    if cap: add('room',t,'capacity-students','count',cap,card='max %s students per room'%cap,page=t)
    unl=i2names(ib.get('unlock',''))
    if unl: add('room',t,'unlocked-at','campus',unl[0],page=t)
    ty=re.findall(r'\[\[Rooms#([A-Za-z]+)\|([^\]]+)\]\]',ib.get('type',''))
    if ty: add('room',t,'classified-type','room-class',ty[0][1],page=t)
    else:
        wl=[x.split('|')[0].strip() for x in re.findall(r'\[\[([^\]|]+)(?:\|[^\]]*)?\]\]',ib.get('type',''))]
        for w in wl[:1]: add('room',t,'classified-type','room-class',w,page=t)
    plc=i2names(ib.get('placement',''))
    if plc:
        add('room',t,'classified-placement','placement-class',plc[0].lstrip(':').replace(':Category:','').replace('Category:',''),page=t)
    pr=ib.get('price','').replace(',','').strip()
    if pr: add('room',t,'base-price-money','cost',pr,page=t)
    sz=ib.get('size','').strip()
    if sz: add('room',t,'minimum-size-tiles','size',sz,page=t)

for t,c in sorted(D.items()):
    ib=infobox(c,'[Ii]nfobox [Ii]tem')
    for rm in i2names(ib.get('room','')): add('item',t,'placed-in','room',rm,page=t)
    eff=ib.get('effect','')
    for pm in re.finditer(r'\{\{\s*\+?\s*([A-Za-z ]+?)(?:\s*\|\s*(\d+))?\s*\}\}',eff):
        nm,val=pm.group(1).strip(),pm.group(2)
        if 'Power' in nm: add('item',t,'grants-power','power-axis',nm,card=(nm+' +'+val+'%' if val else None),page=t)
        else: add('item',t,'raises-need-axis','need-axis',nm,page=t)
    for pm in re.finditer(r'\{\{\s*-\s*([A-Za-z ]+?)\s*[|}]',eff):
        add('item',t,'reduces-need-axis','need-axis',pm.group(1).strip(),page=t)
    if 'Provides Income' in eff: add('item',t,'provides-income','mechanic','Money over time',page=t)
    for req in i2names(eff):
        if req.startswith('Requires'): add('item',t,'requires-staff-kind','staff-kind',req.replace('Requires ',''),notes='effect-field requirement',page=t)
    filt=ib.get('filter','')
    for cl in [x for x in i2names(filt) if x.endswith(' Club')]: add('item',t,'recruits-for','club',cl,page=t)
    cats=set(i2names(filt))|set(catlink(filt))
    for fc in sorted(x.lstrip(':').replace('Category:','') for x in cats if not x.endswith(' Club'))[:3]:
        add('item',t,'classified-filter','item-class',fc,page=t)
    unl=i2names(ib.get('unlock',''))
    for u in unl[:1]:
        if u.startswith('Research#'): add('item',t,'unlocked-by-research','research-project',u.split('#',1)[1],page=t)
        elif u: add('item',t,'unlocked-at','campus-or-source',u,page=t)
    ku=ib.get('kudosh','').strip()
    if ku and ku.lower()!='none': add('item',t,'purchasable-kudosh','cost',ku,page=t)
    pr=ib.get('price','').replace(',','').strip()
    if pr: add('item',t,'purchase-price-money','cost',pr,page=t)
    at=re.search(r'==\s*Assignments\s*==\n(.*?)(?=\n==[^=]|\Z)',c,re.S)
    if at:
        tbl=re.search(r'\{\|.*?\|\-(.*)\|\}',at.group(1),re.S)
        if tbl:
            seen=set()
            for chunk in re.split(r'\|\-',tbl.group(1)):
                cells=[re.sub(r'\s+',' ',ln.lstrip('|')).strip() for ln in chunk.split('\n') if ln.startswith('|') and not ln.startswith('|}')]
                if len(cells)>=3:
                    desc=plain(cells[1])
                    for co in i2names(cells[2]):
                        if co in seen: continue
                        seen.add(co)
                        add('assignment','%s (%s item)'%(desc,t),'used-in-course','course',co,notes='assignment satisfied by %s'%t,page=t)

with open('fandom/model.jsonl','w',encoding='utf-8') as f:
    for r in rows: f.write(json.dumps(r,ensure_ascii=False)+'\n')
print('rows:',len(rows)); print(Counter(r['relationVerb'] for r in rows).most_common())
