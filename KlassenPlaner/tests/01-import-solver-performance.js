const {chromium}=require('playwright');
const {TOOL,FIXTURES,launchOpts}=require('./config');
(async()=>{
const b=await chromium.launch(launchOpts());
const pg=await b.newPage();
const errs=[];
pg.on('console',m=>{if(m.type()==='error')errs.push(m.text());});
pg.on('pageerror',e=>errs.push('PAGEERROR: '+e.message));
await pg.goto(TOOL);
await pg.setInputFiles('#personFile',FIXTURES+'fair150.csv');
await pg.click('#loadBtn');
await pg.waitForTimeout(800);
const r={};
r.msg=await pg.textContent('#msgArea');
r.n=await pg.evaluate(()=>persons.length);
r.groupSizes=await pg.evaluate(()=>groups.map(g=>g.length));

// Render-Performance Hauptansicht
r.renderMs=await pg.evaluate(()=>{const t=performance.now();renderGroups();return Math.round(performance.now()-t);});
r.statsMs=await pg.evaluate(()=>{const t=performance.now();updateStats();return Math.round(performance.now()-t);});

// Struktur optimieren: Laufzeit
pg.on('dialog',d=>d.accept());
r.solverMs=await pg.evaluate(()=>{const t=performance.now();hillClimbSolve('struktur');return Math.round(performance.now()-t);});
r.afterSolver=await pg.evaluate(()=>{
  const f=groups.map(g=>g.filter(id=>persons.find(p=>p.id===id).geschlecht==='weiblich').length);
  const topf=[1,2,3,4,5].map(t=>groups.map(g=>g.filter(id=>persons.find(p=>p.id===id).topf===t).length));
  return {weiblich:f, topfPerGroup:topf};
});
r.wuenscheMs=await pg.evaluate(()=>{const t=performance.now();hillClimbSolve('wuensche');return Math.round(performance.now()-t);});
r.wishStats=await pg.evaluate(()=>{
  const pairs=computeWishPairs();
  const ok=pairs.filter(pr=>persons.find(x=>x.id===pr.i).group===persons.find(x=>x.id===pr.j).group).length;
  return {pairs:pairs.length, erfuellt:ok};
});

// Ausschluss-Zähler: Statistik-Absatz vs. rote Box
r.exclusion=await pg.evaluate(()=>{
  renderGroups();updateStats();
  const boxCount=getExclusionViolations().length;
  // Nachbau des Zählers aus updateStats()
  const nameMapS={};persons.forEach(p=>{nameMapS[((p.vorname+' '+p.name).trim()).toLowerCase()]=p.id;});
  let c=0;persons.forEach(p=>{if(!p.nichtinein||p.group===null)return;
    const j=nameMapS[p.nichtinein.toLowerCase().trim()];if(j===undefined)return;
    const pJ=persons.find(x=>x.id===j);if(pJ&&pJ.group===p.group)c++;});
  const solverSees=(()=>{const ctx=buildSolverContext();return ctx.exclSet.size;})();
  return {statsParagraph:Math.ceil(c/2), roteBox:boxCount, solverPaare:solverSees,
          statsText:(document.getElementById('stats').textContent.match(/Ausschluss-Verletzungen[^\n]*/)||[''])[0].trim()};
});

// ID-Kollision nach Löschen + manuellem Hinzufügen
r.idCollision=await pg.evaluate(()=>{
  const before=persons.length;
  const victim=persons[10].id;
  // removePerson() ohne confirm nachbauen (gleiche Logik)
  groups[persons.find(p=>p.id===victim).group]=groups[persons.find(p=>p.id===victim).group].filter(i=>i!==victim);
  persons=persons.filter(x=>x.id!==victim); totalStudents=persons.length;
  const newId=nextPersonId();                 // die Funktion, die addPersonBtn nutzt
  const clash=persons.filter(p=>p.id===newId).map(p=>(p.vorname+' '+p.name));
  return {vorher:before, gelöschteId:victim, neueIdWäre:newId, bereitsVergebenAn:clash};
});

// Export-/Import-Spaltenname
r.roundtrip=await pg.evaluate(()=>{
  const src=document.documentElement.innerHTML;
  return {exportSpalteKlasse:/'NAME','VORNAME','Klasse'/.test(src),
          importAkzeptiertKlasse:/r\.Klasse\?\?r\.Gruppe/.test(src)};
});
r.errors=errs;
console.log(JSON.stringify(r,null,2));
await b.close();
})();
