'use strict';
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const root = path.join(__dirname, '..');
let fail = 0;
const err = (m) => { console.error('FAIL: ' + m); fail++; };
const readJson = (f) => {
  try { return JSON.parse(fs.readFileSync(path.join(root, f), 'utf8')); }
  catch (e) { err(f + ': ' + e.message); return null; }
};
const pkg = readJson('package.json');
const exists = (p) => { if (!fs.existsSync(path.join(root, p))) err('missing file ' + p); };
if (pkg) {
  exists(pkg.main);
  const c = pkg.contributes || {};
  (c.languages || []).forEach((l) => l.configuration && exists(l.configuration));
  (c.grammars || []).forEach((g) => exists(g.path));
  (c.snippets || []).forEach((s) => { exists(s.path); readJson(s.path.replace('./', '')); });
}
const g = readJson('syntaxes/sipl.tmLanguage.json');
if (g) {
  const repo = g.repository || {};
  const checkIncludes = (node, where) => {
    if (Array.isArray(node)) return node.forEach((n) => checkIncludes(n, where));
    if (node && typeof node === 'object') {
      if (typeof node.include === 'string') {
        const inc = node.include;
        if (inc === '$self' || inc === '$base') {}
        else if (inc.startsWith('#')) { if (!repo[inc.slice(1)]) err('unresolved include ' + inc + ' in ' + where); }
        else if (!inc.startsWith('source.') && !inc.startsWith('text.')) err('bad include ' + inc);
      }
      for (const k of Object.keys(node)) checkIncludes(node[k], where);
    }
  };
  checkIncludes(g.patterns, 'patterns');
  checkIncludes(repo, 'repository');
  const rx = (n) => {
    if (Array.isArray(n)) return n.forEach(rx);
    if (n && typeof n === 'object') {
      for (const k of ['match', 'begin', 'end']) if (typeof n[k] === 'string') { try { new RegExp(n[k]); } catch (e) { err('bad regex ' + n[k]); } }
      Object.values(n).forEach(rx);
    }
  };
  rx(g);
}
const lc = readJson('language-configuration.json');
if (lc) {
  for (const r of Object.values(lc.indentationRules || {})) { try { new RegExp(r); } catch (e) { err('bad regex ' + r); } }
}
try { execFileSync(process.execPath, ['--check', path.join(root, 'extension.js')]); }
catch (e) { err('node --check extension.js'); }
if (fail) { console.error(fail + ' problem(s)'); process.exit(1); }
console.log('validate: OK');
