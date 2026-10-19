const fs=require('fs');
const vor=['Lena','Paul','Mia','Finn','Emma','Luca','Hanna','Jonas','Marie','Elias','Sofia','Noah','Lina','Ben','Clara','Max','Ida','Tim','Nele','Jan'];
const nach=['Müller','Schmidt','Schneider','Fischer','Weber','Meyer','Wagner','Becker','Hoffmann','Schäfer','Koch','Bauer','Richter','Klein','Wolf','Neumann','Schwarz','Zimmermann','Braun','Krüger'];
const rows=[];const names=[];
for(let i=0;i<150;i++){
  const v=vor[i%vor.length], n=nach[Math.floor(i/vor.length)%nach.length];
  let full=v+' '+n,sfx=0;
  while(names.includes(full)){sfx++;full=v+' '+n+' '+String.fromCharCode(64+sfx);}
  names.push(full);const parts=full.split(' ');
  rows.push({vorname:parts[0],name:parts.slice(1).join(' '),
    topf:1+(i%5), geschlecht:(i%20<10)?'weiblich':'männlich',
    av:['A','B','C','C','D','E'][i%6], sv:['C','B','C','D','C','E'][i%6],
    lernen:i%17===0?'Ja':'',emotionale:i%23===0?'Ja':'',sprache:i%29===0?'Ja':''});
}
// Wunschpaare: 0<->1, 2<->3 ... nur in der ersten Hälfte
for(let i=0;i<70;i+=2){rows[i].erstwunsch=rows[i+1].vorname+' '+rows[i+1].name;rows[i+1].erstwunsch=rows[i].vorname+' '+rows[i].name;}
// Ausschlusspaare: KOMPLETT disjunkt von den Wunschpaaren (Indizes 100..119), 10 Paare, einseitig notiert
for(let i=100;i<120;i+=2){rows[i].nichtinein=rows[i+1].vorname+' '+rows[i+1].name;}
const cols=['name','vorname','topf','geschlecht','av','sv','erstwunsch','zweitwu','nichtinein','notiz','emotionale','lernen','sprache'];
const head=['NAME','VORNAME','Topf','Geschlecht','AV','SV','Erstwunsch','Zweitwunsch','Nichtinein','Notiz','EMOTIONALE','LERNEN','SPRACHE'];
fs.writeFileSync(process.argv[2],'﻿'+[head.join(';'),...rows.map(r=>cols.map(c=>r[c]??'').join(';'))].join('\r\n'),'utf8');
console.log('ok');
