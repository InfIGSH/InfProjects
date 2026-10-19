// Renders taskcards-vorlage.html headlessly and exercises loadSpec, renderBoard, the store
// fallback and the progress export/import round trip.
//
//   node tests/taskcards.test.js taskcards-vorlage.html            # with a working localStorage
//   node tests/taskcards.test.js taskcards-vorlage.html nostore     # localStorage throws
//
// Pass a file with embedded data to test a filled export. Watch for: "nostore" must raise the
// banner and still round-trip the progress file, and no board may be "angelegt" without a link.
const fs = require('fs'), vm = require('vm');
const tpl = fs.readFileSync(process.argv[2], 'utf8');
const WITH_LS = process.argv[3] !== 'nostore';
let js = tpl.slice(tpl.indexOf('<script>') + 8, tpl.lastIndexOf('</script>'));
js += '\n;globalThis.__X = {get SPEC(){return SPEC}, store, current, renderBoard, cardHash, cardState, progress, linkFor, linkSeeded, boardUrl, saveProgress, restoreProgress, loadSpec, findCard};\n';

class El {
  constructor(id){ this.id=id; this._html=''; this._text=''; this.dataset={}; this.style={}; this.children=[];
    this.classList={_s:new Set(),add(...c){c.forEach(x=>this._s.add(x))},remove(...c){c.forEach(x=>this._s.delete(x))},
      toggle(c,f){f===undefined?(this._s.has(c)?this._s.delete(c):this._s.add(c)):(f?this._s.add(c):this._s.delete(c))},
      contains(c){return this._s.has(c)}}; }
  set innerHTML(v){ this._html=String(v); } get innerHTML(){ return this._html; }
  set textContent(v){ this._text=String(v); } get textContent(){ return this._text; }
  click(){ this.clicked=true; } remove(){} appendChild(c){ this.children.push(c); }
  querySelector(){ return null; } querySelectorAll(){ return []; } closest(){ return null; }
}
const els={}; let downloads=[];
const document={
  getElementById(id){ return els[id]||(els[id]=new El(id)); },
  createElement(t){ const e=new El(t); if(t==='a'){ const self=e; e.click=()=>downloads.push({name:self.download,href:self.href}); } return e; },
  addEventListener(){}, querySelectorAll(){return[]}, querySelector(){return null},
  body:Object.assign(new El('body'),{appendChild(){}}), execCommand(){return true}, createRange(){return{selectNodeContents(){}}},
};
const localStorage = WITH_LS ? { _m:new Map(), get length(){return this._m.size}, key(i){return [...this._m.keys()][i]},
    getItem(k){return this._m.has(k)?this._m.get(k):null}, setItem(k,v){this._m.set(k,String(v))}, removeItem(k){this._m.delete(k)} }
  : { get length(){throw new Error('blocked')}, key(){throw new Error('blocked')},
      getItem(){throw new Error('blocked')}, setItem(){throw new Error('blocked')}, removeItem(){throw new Error('blocked')} };
let blobs=[];
const ctx={document,localStorage,console,Date,JSON,Math,Object,Array,Set,Map,String,Number,Boolean,RegExp,Error,
  isNaN,parseInt,parseFloat,setTimeout:(f)=>0,clearTimeout(){},getSelection(){return null},
  Blob:class{constructor(p,o){this.parts=p;this.type=o&&o.type;blobs.push(this)}},
  URL:{createObjectURL:b=>{return 'blob:'+(blobs.indexOf(b))},revokeObjectURL(){}},
  FileReader:class{readAsText(){}}, navigator:{}, ClipboardItem:class{}, addEventListener(){}};
ctx.globalThis=ctx; ctx.window=ctx;
vm.createContext(ctx);
try{ vm.runInContext(js,ctx,{filename:'taskcards.js'}); }catch(e){ console.error('RUNTIME ERROR:',e.message,'\n',e.stack.split('\n').slice(0,4).join('\n')); process.exit(1); }
const X=ctx.__X, S=X.SPEC;
const g=id=>els[id]?(els[id].innerHTML||els[id].textContent):'';
const count=(s,re)=>(s.match(re)||[]).length;
console.log('localStorage  :', WITH_LS?'verfügbar':'blockiert', '| store.ok =', X.store.ok);
console.log('nostore-Banner:', els.nostore&&els.nostore.classList.contains('open')?'sichtbar':'aus');
if(!S){ console.log('SPEC          : null |', g('warn').replace(/<[^>]+>/g,' ').trim()); }
else {
  console.log('Titel / Meta  :', g('title'),'|',g('meta'));
  console.log('Startpinnwand :', g('bTitle'),'| Status:',g('bState').replace(/<[^>]+>/g,''),'| Link:',g('bLink')?'ja':'nein');
  console.log('Pflegehinweis :', g('bPflege').slice(0,80));
  console.log('Reiter        :', count(g('tabs'),/class="tab/g), '| Fortschritt', (g('tabs').match(/\d+\/\d+/g)||[]).join(' '));
  console.log('Spalten       :', count(g('board'),/<section class="col"/g), '| Karten', count(g('board'),/<article class="card/g));
  console.log('Dateien       :', count(g('board'),/data-file=/g), '| nur lokal', count(g('board'),/nur lokal/g), '| fehlt', count(g('board'),/pill warn">fehlt/g));
  // every board must render without throwing, and existing ones must show a link
  let bad=0, angelegt=0, neu=0;
  for(const b of S.boards){
    try{
      ctx.__X.store.set('board', b.id);
      // re-enter renderBoard via the module's own 'current'
      vm.runInContext(`current = ${JSON.stringify(b.id)}; renderBoard();`, ctx);
      const st=g('bState'); if(/angelegt/.test(st)) angelegt++; else neu++;
      if(/angelegt/.test(st) && !g('bLink')) { bad++; console.log('  FEHLER: angelegt ohne Link:', b.titel); }
    }catch(e){ bad++; console.log('  RENDER FEHLER', b.titel, e.message); }
  }
  console.log('Alle Pinnwände:', S.boards.length,'gerendert |',angelegt,'angelegt,',neu,'neu anlegen |',bad,'Fehler');
  // seeded links
  const slots=[...new Set(S.boards.flatMap(b=>b.spalten.flatMap(c=>c.karten.map(k=>k.link_slot).filter(Boolean))))];
  console.log('Link-Felder   :', slots.length, '| vorbelegt', slots.filter(s=>X.linkSeeded(s)).length,
              '| Platzhalter im Text ersetzt:', !/\[Link nach dem Anlegen eintragen\]/.test(g('board')));
  // progress round trip
  const card=S.boards[0].spalten.flatMap(c=>c.karten)[0];
  X.store.set('done.'+card.id, X.cardHash(card));
  X.store.set('file.x','1');
  console.log('cardState     :', X.cardState(card), '(erwartet done)');
  downloads=[]; X.saveProgress();
  const payload = blobs.length ? JSON.parse(blobs[blobs.length-1].parts[0]) : null;
  console.log('Export        :', downloads.length?downloads[0].name:'(keiner)', '|', payload?Object.keys(payload.entries).length:0, 'Einträge | scope', payload&&payload.scope);
  // wipe and restore
  for(const k of Object.keys(payload.entries)) X.store.set(k,null);
  console.log('nach Löschen  :', X.cardState(card));
  X.restoreProgress(payload);
  console.log('nach Restore  :', X.cardState(card), '(erwartet done)');
  // a changed card must be detected
  const before=X.cardState(card); card.titel += ' (geändert)';
  console.log('nach Änderung :', X.cardState(card), '(erwartet changed; vorher '+before+')');
  try{ X.restoreProgress({}); console.log('Restore ohne entries: KEIN Fehler (schlecht)'); }
  catch(e){ console.log('Restore ohne entries:', e.message); }
}
