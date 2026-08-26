import json,sys
sys.stdout.reconfigure(encoding='utf-8')
rows=[]
def add(sk,sn,verb,ok,on,card=None,notes=None,page=None):
    rows.append({"subjectKind":sk,"subjectName":sn,"relationVerb":verb,"objectKind":ok,"objectName":on,
                 **({"cardinalityClaim":card} if card else {}),**({"notes":notes} if notes else {}),
                 "sourcePage":page})

# ---- fandom cross-cutting rows (pages pulled this session) ----
arch_traits=[("Chef",["Nibbler","Comfort Baker"]),("Class Clown",["Laughing Matters"]),
 ("Goth",["Dark Aura"]),("Jock",["Fun Runner"]),("Musician",["Busker"]),("Posho",["Big Tipper"]),
 ("Rebel",["Sharpest Tool"]),("Spy",["Secret Sources"]),("Swot",["Wise Words"]),
 ("Wizard",["Wicked","Magic Touch"]),("Astronaut",["En-Suit"]),("Space Cadet",["Beam Up"]),
 ("Cheese-Moonger",["Cheesy Fragrance"]),("Ghost Detector",["Suck-Up"]),("Free Spirit",["Ghost Goo","Intangible"])]
for a,ts in arch_traits:
    for t in ts:
        add('archetype',a,'carries-trait','trait',t,
            notes='trait description states its behavioural effect',
            page='Archetypes (fandom/wikitext-A-templates-staff.json)')
for a,d in [("Alien","Space Academy DLC"),("Astronaut","Space Academy DLC"),("Space-Knight","Space Academy DLC"),
            ("Ghost Detector","School Spirits DLC"),("Doctor","Medical School DLC"),("Nurse","Medical School DLC"),
            ("Blaggard Knight","Challenge Mode"),("Egg Hunter","Challenge Mode")]:
    add('archetype',a,'grouped-under','content-axis',d,page='Archetypes (fandom/wikitext-A-templates-staff.json)')

add('event','*','hosted-in','room','(varies by room)',notes='"Different Rooms can host different events, and some events may require specific Items"',page='Events (fandom/wikitext-F-hubs.json)')
add('event','Campus Cook Off','unlocked-at','campus','Piazza Lanatra',page='Events (fandom/wikitext-F-hubs.json)')
add('event','Campus Cook Off','requires-course-level','course','Gastronomy Course Level 1 + 3 Gastronomy Students',
    card='course Level 1 gate',page='Events (fandom/wikitext-F-hubs.json)')
add('event','Campus Cook Off','rewards-currency','cost','2,000 money + 4 Kudosh',page='Events (fandom/wikitext-F-hubs.json)')

add('research-project','*','performed-in','room','Research Lab',
    notes='research carried out by Teachers; speed scales with Research Power items',page='Research (fandom/wikitext-F-hubs.json)')
add('research-project','Lectern Upgrade','grants-upgrade','item','Lectern (Lecture Theatre)',notes='community priority research',page='Research (fandom/wikitext-F-hubs.json)')
add('research-project','*','may-require-qualification','staff-kind','Teacher with course-specific qualification',page='Research (fandom/wikitext-F-hubs.json)')

add('campus','Mitton University','features-course','course','Robotics',page='Mitton University (fandom/wikitext-E-campus-clubs.json)')
add('campus','Mitton University','unlocked-after','campus','Piazza Lanatra',card='linear campus progression chain',page='Mitton University (fandom/wikitext-E-campus-clubs.json)')
add('campus','Mitton University','starting-intake','count','10',page='Mitton University (fandom/wikitext-E-campus-clubs.json)')

with open('fandom/model.jsonl','a',encoding='utf-8') as f:
    for r in rows: f.write(json.dumps(r,ensure_ascii=False)+'\n')
print('appended',len(rows))

# ---- steam-guides model rows ----
sg=[]
def adds(sk,sn,verb,ok,on,card=None,notes=None,page=None):
    sg.append({"subjectKind":sk,"subjectName":sn,"relationVerb":verb,"objectKind":ok,"objectName":on,
               **({"cardinalityClaim":card} if card else {}),**({"notes":notes} if notes else {}),
               "sourcePage":page})
T='guide 2852555025 "Tips and tricks..."'; L='guide 2853410023 "All Levels (All DLCs)"'
K='guide 2875066931 "Kudos, Loans and R&D"'; M='guide 2849835291 "How to be wealthy"'
adds('room','classrooms','capacity-students','count','8',card='max 8 students per classroom',page=T)
adds('course','any course','recommended-intake-multiple','count','multiples of 8 (8/16/24/32)',notes='derived from room capacity',page=T)
adds('teacher','one teacher','manages-students','count','up to 16 students in year 1',page=T)
adds('dormitory-bed','1 bed','supports-students','count','up to 5 students',notes='beds x prestige drive accommodation rating -> rent',page=T)
adds('item-effect','Learning Power items','stacks-in','room','same-room only',card='+1% per item; diminishing returns',notes='Brain Jar example: ~2300 jars for <1 day training at level 1',page=T)
adds('staff-kind','teachers/janitors/assistants','negative-trait-list','trait','Bin-Blindness, Bottomless Pit, Dry-Mouth, Gross, Lollygagger, Weak Bladder',notes='"Reference" category on recruitment screen',page=T)
adds('skill','Aerodynamics','increases','stat','movement speed',page=T)
adds('skill','Comic Timing','buffs-student','need-axis','entertainment + happiness',notes='does not trigger in Library',page=T)
adds('skill','Private Tuition','increases-teaching-skill','stat','+5% per level',notes='course qualification skills give +10% per rank; both stack',page=T)
adds('club-recruitment-stand','club stands','optionally-requires','staff-kind','Assistant',notes='tooltip says required; actually optional; assistant shifts application chance',page=T)
adds('kudosh','Kudosh','earned-via','mechanic','campus goals, awards, stars, Career Hub claims',page=T)
adds('research','first priorities','grants-upgrade','item','Lectern Upgrades (Lecture Theatre)',notes='community priority advice',page=T)
adds('loan','loans','enables-building','room','vital classrooms early',page=K)
for lvl,camp in enumerate(["Freshleigh Meadows","Piazza Lanatra","Mitton University","Noblestead","Spiffinmoore",
  "Fluffborough","Pebberley Ruins","Upper Etching","Blundergrad","Urban Bungle","Breaking Point","Two Point University"],start=1):
    adds('level-order','Level %d'%lvl,'maps-to-campus','campus',camp,notes='base-game campus ladder',page=L)
for dlc,camps in [("Space Academy DLC",["Universe City","Cape Shrapnull","Cheesy Heap: Delta-Rye"]),
                  ("School Spirits DLC",["Lifeless Estate"]),
                  ("Medical School DLC",["Lake Tumble","Molten Rock","Pointy Peak"])]:
    for cp in camps: adds('dlc',dlc,'adds-campus','campus',cp,page=L)
adds('goal','Freshleigh Meadows objectives','requires-building','room','Science Lab, Dormitory, Bathroom',page=L)
adds('goal','Freshleigh Meadows objectives','requires-placing','item','Cheesy Gubbins Machine, Burp! Machine',page=L)

with open('steam-guides/model.jsonl','w',encoding='utf-8') as f:
    for r in sg: f.write(json.dumps(r,ensure_ascii=False)+'\n')
print('steam-guides rows:',len(sg))
