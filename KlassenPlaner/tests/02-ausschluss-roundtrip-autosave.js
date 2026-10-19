const {chromium}=require('playwright');
const {TOOL,FIXTURES,launchOpts}=require('./config');
(async()=>{
const b=await chromium.launch(launchOpts());
const pg=await b.newPage();
const errs=[];pg.on('pageerror',e=>errs.push(e.message));
pg.on('dialog',d=>d.accept());
await pg.goto(TOOL);
await pg.setInputFiles('#personFile',FIXTURES+'fair150.csv');await pg.click('#loadBtn');await pg.waitForTimeout(600);
const v=()=>pg.evaluate(()=>getExclusionViolations().length);
const out={};
out.geladen=await pg.evaluate(()=>persons.length);
out.viol_nach_import=await v();
await pg.evaluate(()=>hillClimbSolve('struktur'));
out.viol_nach_struktur=await v();
await pg.evaluate(()=>hillClimbSolve('wuensche'));
out.viol_nach_wuensche=await v();
out.wunsch=await pg.evaluate(()=>{const p=computeWishPairs();
 return {paare:p.length,erfuellt:p.filter(pr=>persons.find(x=>x.id===pr.i).group===persons.find(x=>x.id===pr.j).group).length};});
out.zaehler=await pg.evaluate(()=>{updateStats();
 return {statsText:(document.getElementById('stats').textContent.match(/Ausschluss[^\n]*/)||[''])[0].trim(),
         roteBox:getExclusionViolations().length};});
// Wird eine künstlich erzeugte Verletzung vom Solver aufgelöst?
out.selbstheilung=await pg.evaluate(()=>{
  const ctx=buildSolverContext();const pair=[...ctx.exclSet][0].split('_').map(Number);
  const a=persons.find(p=>p.id===pair[0]), bb=persons.find(p=>p.id===pair[1]);
  // a zwangsweise in die Klasse von bb legen
  groups[a.group]=groups[a.group].filter(i=>i!==a.id);groups[bb.group].push(a.id);a.group=bb.group;
  const vorher=getExclusionViolations().length;
  hillClimbSolve('struktur');
  return {verletzungen_vorher:vorher, verletzungen_nachher:getExclusionViolations().length};
});
// CSV-Roundtrip: Export erzeugen, Klassen zerstören, importieren
out.roundtrip=await pg.evaluate(async()=>{
  const snapshot=persons.map(p=>p.group);
  // Export-String exakt wie im Tool erzeugen
  const header='NAME,VORNAME,Klasse,TutorKürzel,Topf,GESCHLECHT,AV,SV,EMOTIONALE,GEISTIGEEN,HÖREN,KÖRPERLMOT,LERNEN,SEHEN,SPRACHE,ERSTWUNSCH,ZWEITWU,NICHTINEIN,Locked,Notiz';
  const yn=x=>x?'Ja':'Nein';
  const rows=persons.map(p=>[p.name,p.vorname,p.group!=null?klasseName(p.group):'','',p.topf,p.geschlecht,p.av,p.sv,
    yn(p.emotionale),yn(p.geistigeen),yn(p.hören),yn(p.körperlmot),yn(p.lernen),yn(p.sehen),yn(p.sprache),
    p.erstwunsch,p.zweitwu,p.nichtinein,p.locked,p.notiz||''].join(','));
  const text=[header,...rows].join('\n');
  // Klassen zerstören
  persons.forEach(p=>p.group=null);groups=[[],[],[],[],[]];
  // Import-Logik des Tools nachvollziehen
  const parsed=csvParse(text);
  let gesetzt=0;
  const byFull={};persons.forEach(p=>{byFull[displayName(p).toLowerCase()]=p;byFull[(p.name+' '+p.vorname).toLowerCase()]=p;});
  parsed.forEach(r=>{const pp=byFull[((r.VORNAME||'')+' '+(r.NAME||'')).trim().toLowerCase()]||byFull[((r.NAME||'')+' '+(r.VORNAME||'')).trim().toLowerCase()];
    if(!pp)return;const raw=String(r.Klasse??r.Gruppe??'').replace(/^(Klasse|Gruppe)\s*/i,'').replace(/^5\./,'').trim();
    if(raw){pp.group=+raw-1;gesetzt++;}});
  return {zeilen:parsed.length, spaltenNamen:Object.keys(parsed[0]).slice(0,4),
          klassen_wiederhergestellt:gesetzt, alle_null:persons.every(p=>p.group===null), vorher_gesetzt:snapshot.filter(x=>x!==null).length};
});
// Semikolon in Notiz -> Spaltenbruch im Klassen-CSV-Export?
out.semikolon=await pg.evaluate(()=>{
  persons[0].notiz='Mutter angerufen; bitte beachten';
  persons[0].group=0; if(!groups[0].includes(persons[0].id))groups[0].push(persons[0].id);
  const d=exportKlasseData(0);const r=d.rows.find(x=>x.notiz&&x.notiz.includes(';'));
  const zeile=rowToArr(r).map(x=>csvEscape(String(x??''))).join(';');
  const zurueck=csvParse(EXP_COLS.join(';')+'\n'+zeile,';')[0];
  return {zeile, felder:Object.keys(zurueck).length, erwartet:EXP_COLS.length,
          notiz_intakt:zurueck['Notiz']==='Mutter angerufen; bitte beachten'};
});
// Autosave nach AV/SV- bzw. Notiz-Änderung?
out.autosave=await pg.evaluate(async()=>{
  localStorage.removeItem('kbplaner_v3');
  renderGroups(); await new Promise(r=>setTimeout(r,1700));
  const base=localStorage.getItem('kbplaner_v3');
  const sel=document.querySelector('.av-sel'); sel.value='E'; sel.dispatchEvent(new Event('change'));
  const inp=document.querySelector('.notiz-inp'); inp.value='WICHTIG-TEST'; inp.dispatchEvent(new Event('input'));
  await new Promise(r=>setTimeout(r,1800));
  const after=localStorage.getItem('kbplaner_v3');
  return {gespeichert_enthaelt_notiz:(after||'').includes('WICHTIG-TEST'),
          speicher_unveraendert:base===after,
          hat_zeitstempel:/_ts/.test(after||'')};
});
// HTML aus CSV-Feld in Fehlermeldung
out.injection=await pg.evaluate(()=>{
  const csvText='NAME;VORNAME;Topf;Geschlecht\n<img src=x onerror=window.__pwned=1>;Test;1;weiblich\n<img src=x onerror=window.__pwned=1>;Test;1;weiblich';
  const msg=document.getElementById('msgArea');
  applyParsedRows(csvParse(csvText,';'),msg);
  return {meldung:msg.textContent.slice(0,80), img_im_dom:!!msg.querySelector('img'), pwned:!!window.__pwned};
});
out.pageerrors=errs;
console.log(JSON.stringify(out,null,2));
await b.close();})();
