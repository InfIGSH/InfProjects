const {chromium}=require('playwright');
const {TOOL,FIXTURES,launchOpts}=require('./config');
const fs=require('fs'),os=require('os'),pathm=require('path');
const tmp=fs.mkdtempSync(pathm.join(os.tmpdir(),'kp-'));
(async()=>{
const b=await chromium.launch(launchOpts());
const ctx=await b.newContext({acceptDownloads:true});
const pg=await ctx.newPage();
const errs=[];pg.on('pageerror',e=>errs.push(e.message));
const dialogs=[];pg.on('dialog',d=>{dialogs.push(d.message().split('\n')[0]);d.accept();});
await pg.goto(TOOL);
await pg.setInputFiles('#personFile',FIXTURES+'fair150.csv');await pg.click('#loadBtn');await pg.waitForTimeout(500);
const out={};

/* --- 1) Klassen-CSV: echter Export -> echter Import --- */
await pg.evaluate(()=>hillClimbSolve('struktur'));
await pg.evaluate(()=>{renderGroups();updateStats();});
const vorher=await pg.evaluate(()=>persons.map(p=>p.group).join(','));
const dl=await Promise.all([pg.waitForEvent('download'),pg.click('#exportBtn')]).then(r=>r[0]);
const csvOut=pathm.join(tmp,'klassen.csv');await dl.saveAs(csvOut);
out.export_datei=dl.suggestedFilename();
// Klassen im Tool zerstoeren, dann die exportierte Datei importieren
await pg.evaluate(()=>{persons.forEach(p=>p.group=null);groups=[[],[],[],[],[]];renderGroups();updateStats();});
await pg.setInputFiles('#importFile',csvOut);await pg.waitForTimeout(600);
const nachher=await pg.evaluate(()=>persons.map(p=>p.group).join(','));
out.klassen_roundtrip={meldung:(await pg.textContent('#msgArea')).trim().slice(0,90),
  identisch_wiederhergestellt:vorher===nachher,
  zugeordnet:await pg.evaluate(()=>persons.filter(p=>p.group!==null).length)};

/* --- 2) Semikolon in Notiz: Export -> zurueckparsen --- */
out.semikolon=await pg.evaluate(()=>{
  persons[0].notiz='Mutter angerufen; bitte beachten';
  const d=exportKlasseData(persons[0].group);
  const r=d.rows.find(x=>x.notiz.includes(';'));
  const zeile=rowToArr(r).map(v=>csvEscape(String(v??''))).join(';');
  const zurueck=csvParse(EXP_COLS.join(';')+'\n'+zeile,';')[0];
  return {felder_nach_parse:Object.keys(zurueck).length, erwartet:EXP_COLS.length,
          notiz_intakt:zurueck['Notiz']==='Mutter angerufen; bitte beachten'};
});

/* --- 3) Mehrzeilige Notiz im Import --- */
out.mehrzeilig=await pg.evaluate(()=>{
  const t='NAME;VORNAME;Topf;Geschlecht;Notiz\nTest;Anna;1;weiblich;"Zeile1\nZeile2"\n';
  const r=csvParse(t,';');
  return {zeilen:r.length, notiz:JSON.stringify(r[0]&&r[0].Notiz)};
});

/* --- 4) ID-Vergabe nach Loeschen (echter Pfad) --- */
await pg.setInputFiles('#personFile',FIXTURES+'fair150.csv');await pg.click('#loadBtn');await pg.waitForTimeout(400);
out.ids=await pg.evaluate(()=>{
  const opfer=persons[10].id;
  groups[persons[10].group]=groups[persons[10].group].filter(i=>i!==opfer);
  persons=persons.filter(x=>x.id!==opfer);totalStudents=persons.length;
  const neue=nextPersonId();
  return {laenge:persons.length, naechste_id:neue,
          kollidiert:persons.some(p=>p.id===neue)};
});

/* --- 5) wishAliases-Reset beim Neu-Import --- */
out.aliasReset=await pg.evaluate(()=>{
  wishAliases={'irgendein alter name':3}; confirmedAbsent=new Set(['xy']);
  return {vorher:Object.keys(wishAliases).length};
});
/* Reset wird durch den echten CSV-Load darunter geprueft */
await pg.setInputFiles('#personFile',FIXTURES+'fair150.csv');await pg.click('#loadBtn');await pg.waitForTimeout(400);
out.aliasReset.nach_neuem_import=await pg.evaluate(()=>
  ({aliase:Object.keys(wishAliases).length, absent:confirmedAbsent.size}));

/* --- 6) Fixierte Karte nicht ziehbar + Rueckfrage bei Struktur --- */
out.fixierung=await pg.evaluate(()=>{
  persons[0].locked=true;renderGroups();
  const card=document.querySelector(`.person[data-id="${persons[0].id}"]`);
  return {draggable_attr:card.getAttribute('draggable')};
});
dialogs.length=0;
await pg.click('#strukturBtn');await pg.waitForTimeout(900);
out.fixierung.struktur_dialog=dialogs.slice();
out.fixierung.locked_bleibt=await pg.evaluate(()=>persons.find(p=>p.locked)!==undefined);

/* --- 7) Sitzungsdaten loeschen --- */
dialogs.length=0;
await pg.click('#clearDataBtn');await pg.waitForTimeout(2200);
out.loeschen={dialog:dialogs[0]||null,
  localStorage:await pg.evaluate(()=>localStorage.getItem('kbplaner_v3')),
  personen:await pg.evaluate(()=>persons.length),
  meldung:(await pg.textContent('#msgArea')).trim().slice(0,60)};

out.pageerrors=errs;
console.log(JSON.stringify(out,null,2));
await b.close();})();
