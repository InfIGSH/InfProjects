const {chromium}=require('playwright');
const {TOOL,FIXTURES,launchOpts}=require('./config');
(async()=>{
const b=await chromium.launch(launchOpts());
const pg=await b.newPage();pg.on('dialog',d=>d.accept());
await pg.goto(TOOL);
await pg.setInputFiles('#personFile',FIXTURES+'fair150.csv');await pg.click('#loadBtn');await pg.waitForTimeout(500);
const out=await pg.evaluate(()=>{
  const st={versuche:0, gleicheGruppe:0, invalid:0, invalid_topf:0, angenommen:0, verbessert:0};
  const origValid=swapValid;
  window.swapValid=function(a,bb,ctx){const ok=origValid(a,bb,ctx);
    if(!ok){st.invalid++; if(a.topf!==bb.topf)st.invalid_topf++;}
    return ok;};
  // Iterationszähler über eine Nachbildung der Solver-Schleife
  greedyFallback();
  const ctx=buildSolverContext();
  const unlocked=persons.filter(p=>!p.locked);
  let cur=computeSolverScore(ctx,'struktur');
  for(let it=0;it<80000;it++){
    const a=unlocked[Math.floor(Math.random()*unlocked.length)];
    const bb=unlocked[Math.floor(Math.random()*unlocked.length)];
    st.versuche++;
    if(a.id===bb.id||a.group===bb.group){st.gleicheGruppe++;continue;}
    if(!window.swapValid(a,bb,ctx))continue;
    const ga=a.group,gb=bb.group,ia=groups[ga].indexOf(a.id),ib=groups[gb].indexOf(bb.id);
    groups[ga][ia]=bb.id;groups[gb][ib]=a.id;a.group=gb;bb.group=ga;
    const ns=computeSolverScore(ctx,'struktur');
    if(ns>=cur){if(ns>cur)st.verbessert++;cur=ns;st.angenommen++;}
    else{groups[ga][ia]=a.id;groups[gb][ib]=bb.id;a.group=ga;bb.group=gb;}
  }
  const topfCounts=[1,2,3,4,5].map(t=>persons.filter(p=>p.topf===t).length);
  return {...st, topfGesamt:topfCounts,
    teilbar_durch_5:topfCounts.filter(c=>c%5===0).length,
    anteil_invalid:Math.round(100*st.invalid/st.versuche)+'%',
    anteil_angenommen:(100*st.angenommen/st.versuche).toFixed(2)+'%'};
});
console.log(JSON.stringify(out,null,2));
await b.close();})();
