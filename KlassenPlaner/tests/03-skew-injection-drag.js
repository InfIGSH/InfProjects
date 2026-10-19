const {chromium}=require('playwright');
const {TOOL,FIXTURES,launchOpts}=require('./config');
const fs=require('fs');
// Fixture: Geschlecht korreliert mit Topf (Topf1+2 fast nur Mädchen, Topf4+5 fast nur Jungen)
{const vor=['Lena','Paul','Mia','Finn','Emma','Luca','Hanna','Jonas','Marie','Elias'];
 const nach=['Müller','Schmidt','Schneider','Fischer','Weber','Meyer','Wagner','Becker','Hoffmann','Schäfer','Koch','Bauer','Richter','Klein','Wolf'];
 const rows=[];const seen=new Set();
 for(let i=0;i<150;i++){const topf=1+(i%5);
  let v=vor[i%vor.length],n=nach[Math.floor(i/vor.length)%nach.length],full=v+' '+n,s=0;
  while(seen.has(full)){s++;full=v+' '+n+' '+String.fromCharCode(64+s);}seen.add(full);
  const parts=full.split(' ');
  const g = topf<=2 ? (i%10===0?'männlich':'weiblich') : topf>=4 ? (i%10===0?'weiblich':'männlich') : (i%2?'weiblich':'männlich');
  rows.push([parts.slice(1).join(' '),parts[0],topf,g,'C','C','','','','','','','']);}
 const head=['NAME','VORNAME','Topf','Geschlecht','AV','SV','Erstwunsch','Zweitwunsch','Nichtinein','Notiz','EMOTIONALE','LERNEN','SPRACHE'];
 fs.writeFileSync(FIXTURES+'skew150.csv','﻿'+[head.join(';'),...rows.map(r=>r.join(';'))].join('\r\n'));}
(async()=>{
const b=await chromium.launch(launchOpts());
const pg=await b.newPage();const errs=[];pg.on('pageerror',e=>errs.push(e.message));
let dialogs=[];pg.on('dialog',d=>{dialogs.push(d.message().slice(0,60));d.accept();});
await pg.goto(TOOL);
await pg.setInputFiles('#personFile',FIXTURES+'skew150.csv');await pg.click('#loadBtn');await pg.waitForTimeout(500);
const out={};
out.vorher=await pg.evaluate(()=>({w:groups.map(g=>g.filter(i=>persons.find(p=>p.id===i).geschlecht==='weiblich').length)}));
// echter Button-Klick: gibt es eine Rückfrage?
dialogs=[];
await pg.click('#strukturBtn');await pg.waitForTimeout(1200);
out.struktur_rueckfrage=dialogs.slice();
out.nachher=await pg.evaluate(()=>({
  w:groups.map(g=>g.filter(i=>persons.find(p=>p.id===i).geschlecht==='weiblich').length),
  topf:[1,2,3,4,5].map(t=>groups.map(g=>g.filter(i=>persons.find(p=>p.id===i).topf===t).length))}));
out.gesamt_weiblich=await pg.evaluate(()=>persons.filter(p=>p.geschlecht==='weiblich').length);
// Injection mit Warten auf onerror
out.injection=await pg.evaluate(async()=>{
  window.__pwned=false;
  const t='NAME;VORNAME;Topf;Geschlecht\n<img src=q onerror="window.__pwned=true">;A;1;weiblich\n<img src=q onerror="window.__pwned=true">;A;1;weiblich';
  applyParsedRows(csvParse(t,';'),document.getElementById('msgArea'));
  await new Promise(r=>setTimeout(r,500));
  return {pwned:window.__pwned, html:document.getElementById('msgArea').innerHTML.slice(0,160)};
});
// Drag entsperrt Fixierung?
await pg.setInputFiles('#personFile',FIXTURES+'skew150.csv');await pg.click('#loadBtn');await pg.waitForTimeout(400);
out.dragUnlock=await pg.evaluate(()=>{
  persons[0].locked=true;renderGroups();
  const card=document.querySelector(`.person[data-id="${persons[0].id}"]`);
  const dt={setData(){},getData(){return String(persons[0].id);}};
  const ev=new Event('dragstart',{bubbles:true});ev.dataTransfer=dt;
  card.dispatchEvent(ev);
  return {locked_nach_dragstart:persons[0].locked};
});
out.pageerrors=errs;
console.log(JSON.stringify(out,null,2));
await b.close();})();
