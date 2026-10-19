// Renders jap-netz.html headlessly against a snapshot and prints what came out, so the tool can
// be checked without a browser. A minimal DOM stub stands in for the page.
//
//   node tests/jap-netz.test.js jap-netz.html pfad/zu/jap-data.json
//
// Watch for: "alte .dot" must be 0, no FEHLER lines, and the counts must match the build report.
const fs = require('fs'), vm = require('vm');
const tpl = fs.readFileSync(process.argv[2], 'utf8');
const data = fs.readFileSync(process.argv[3], 'utf8');
let js = tpl.slice(tpl.indexOf('<script>') + 8, tpl.lastIndexOf('</script>'));
js = js.replace(/^const EMBED = null;.*$/m, 'const EMBED = ' + data + ';');
// top-level const/let are not context properties in a vm, so hand the bindings out explicitly
js += '\n;globalThis.__X = {S, D, IX, TODAY, ALIAS_OK, STATE_TXT, render, related, showDetail, showSol, kompState, aliasTreffer};\n';

class El {
  constructor(id){ this.id = id; this._html = ''; this._text = ''; this.dataset = {}; this.style = {};
    this.classList = { _s:new Set(), add(...c){c.forEach(x=>this._s.add(x))}, remove(...c){c.forEach(x=>this._s.delete(x))},
      toggle(c,f){ f===undefined ? (this._s.has(c)?this._s.delete(c):this._s.add(c)) : (f?this._s.add(c):this._s.delete(c)); },
      contains(c){return this._s.has(c)} }; }
  set innerHTML(v){ this._html = String(v); } get innerHTML(){ return this._html; }
  set textContent(v){ this._text = String(v); } get textContent(){ return this._text; }
  querySelector(){ return null; } querySelectorAll(){ return []; }
  getBoundingClientRect(){ return {top:0,bottom:0}; } scrollIntoView(){} click(){}
}
const els = {};
const document = {
  getElementById(id){ return els[id] || (els[id] = new El(id)); },
  querySelectorAll(){ return []; }, querySelector(){ return null; },
  addEventListener(){}, createElement(){ return new El('tmp'); },
  body: Object.assign(new El('body'), { appendChild(){}, classList: new El('b').classList }),
};
const localStorage = { _m:new Map(), getItem(k){ return this._m.has(k)?this._m.get(k):null; },
  setItem(k,v){ this._m.set(k,String(v)); }, removeItem(k){ this._m.delete(k); } };
const window = { addEventListener(){} };
const ctx = { document, localStorage, window, console, Date, JSON, Math, Object, Array, Set, Map,
  String, Number, Boolean, RegExp, Error, isNaN, parseInt, parseFloat, FileReader: class {}, getSelection(){ return null; } };
ctx.globalThis = ctx;
vm.createContext(ctx);
try { vm.runInContext(js, ctx, {filename:'jap-netz.js'}); } catch (e) { console.error('RUNTIME ERROR:', e.message, '\n', e.stack.split('\n').slice(0,4).join('\n')); process.exit(1); }

// ---- assertions
const X = ctx.__X;
const out = {};
for (const k of ['L1','L2','L3','L4','summary','notes','mStand','bNotes','c1','c2','c3','c4'])
  out[k] = (els[k] ? (els[k].innerHTML || els[k].textContent) : '');
const count = (s, re) => (s.match(re) || []).length;
console.log('Fach/Jg       :', X.S.fach, X.S.jg);
if (!X.D){ console.log('Leere Vorlage : L2 =', out.L2.replace(/<[^>]+>/g,'').trim()); console.log('Fehlermeldung : ok, kein Absturz'); process.exit(0); }
console.log('Heute / Stand :', X.TODAY, '/', X.D.meta.stichtag, '| Alter', X.S._age, 'Tage | Horizont', X.S._horizon);
console.log('Spaltenzähler :', out.c1, out.c2, out.c3, out.c4);
console.log('Statuszeichen : gehalten', count(out.L1,/class="st gehalten"/g),
            '| geplant', count(out.L1,/class="st geplant"/g),
            '| schwach', count(out.L1,/class="st schwach"/g),
            '| offen', count(out.L1,/class="st offen"/g),
            '| neutral', count(out.L1,/class="st" role/g));
console.log('alte .dot     :', count(out.L1+out.L2+out.L3+out.L4,/class="dot/g), '(muss 0 sein)');
console.log('Prüf-Chips L3 :', count(out.L3,/chip[^"]*pruefen/g));
console.log('past-Stunden  :', count(out.L3,/node[^"]*past/g), 'von', X.S._sc.ds.length);
console.log('S._weak       :', X.S._weak);
console.log('Summary       :', out.summary.replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim());
console.log('Stand-Zeile   :', out.mStand.replace(/<[^>]+>/g,'|').replace(/\s+/g,' ').trim());
console.log('Hinweis-Button:', out.bNotes);
console.log('Legende       :', (out.notes.match(/<div class="legend">[\s\S]*?<\/div>/)||[''])[0].replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim());
console.log('Nicht dargest.:', (out.notes.split('<b>Nicht dargestellt</b>')[1]||'(fehlt)').replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim().slice(0,300));
// showSol must not throw
try { X.showSol(); console.log('showSol       : ok,', els.dTitle.textContent); } catch(e){ console.log('showSol FEHLER:', e.message); }
// switch grade + subject: render must survive every combination in the data
const japs = X.D.nodes.filter(n=>n.type==='jap'&&n.fach&&n.jahrgang!=null);
const combos = [...new Set(japs.map(n=>n.fach+'|'+n.jahrgang))];
let bad = 0;
for (const c of combos){ const [f,g] = c.split('|');
  try { X.S.fach=f; X.S.jg=+g; X.S.sel=null; X.render(); } catch(e){ bad++; console.log('  RENDER FEHLER', c, e.message); } }
console.log('Render über alle Fach/Jg-Kombis:', combos.length, 'getestet,', bad, 'Fehler');
// selection path for every node type must not throw
X.S.fach='NW'; X.S.jg=5; X.render();
let selBad = 0, tested = 0;
for (const t of ['kc','kompetenz','jap','ds','material']){
  const n = X.D.nodes.find(x=>x.type===t);
  if (!n) continue; tested++;
  try { X.related(n.id); X.showDetail(n.id); } catch(e){ selBad++; console.log('  DETAIL FEHLER', t, e.message); }
}
console.log('related+showDetail:', tested, 'Typen getestet,', selBad, 'Fehler');
