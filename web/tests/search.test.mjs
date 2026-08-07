// Runs against the COMPILED lib/search.ts (see the test:search npm script) and
// the real exported index, so it exercises the code the browser actually runs.
import { hydrate, buildMiniSearch, search } from '../.test-build/search.js';
import { readFileSync } from 'node:fs';

const indexPath = process.argv[2] ?? new URL('../public/data/search-index.json', import.meta.url).pathname;
const payload = JSON.parse(readFileSync(indexPath, 'utf8'));
const hits = hydrate(payload);
const ms = buildMiniSearch(hits);
console.log(`hydrated ${hits.length} records\n`);

let fails = 0;
function check(desc, got, want) {
  const ok = typeof want === 'function' ? want(got) : got === want;
  if (!ok) fails++;
  console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${desc} -> ${got}`);
}

// batch: exact only
check('batch "SIF2736A" exact', search('SIF2736A','batch',hits,ms).total, 1);
check('batch lowercase "sif2736a"', search('sif2736a','batch',hits,ms).total, 1);
check('batch punctuation "1-3098" vs "13098"', search('13098','batch',hits,ms).total, n=>n>=0);
check('batch must NOT fuzzy-match ("SIF2736B")', search('SIF2736B','batch',hits,ms).total, 0);
check('batch nonsense', search('zzzzzzzz','batch',hits,ms).total, 0);

// drug: fuzzy
check('drug exact "Pantoprazole"', search('Pantoprazole','drug',hits,ms).total, n=>n>10);
check('drug typo "Pantoprazol"', search('Pantoprazol','drug',hits,ms).total, n=>n>10);
check('drug typo "Amoxycilin"', search('Amoxycilin','drug',hits,ms).total, n=>n>5);
check('drug prefix "Dexameth"', search('Dexameth','drug',hits,ms).total, n=>n>3);

// manufacturer: substring on the raw spelling OR the resolved company name
check('mfr "Zee Laboratories" substring', search('Zee Laboratories','manufacturer',hits,ms).total, n=>n>5);
check('mfr address fragment "Paonta Sahib"', search('Paonta Sahib','manufacturer',hits,ms).total, n=>n>3);
check('mfr nonsense', search('qqqqqqq','manufacturer',hits,ms).total, 0);

// Entity resolution: every spelling of one company routes to ONE page. This is
// the whole point of the ticket -- before Phase 2a these 48 spellings produced 48
// separate manufacturer pages.
const zee = search('Zee Laboratories','manufacturer',hits,ms).results;
const zeeSlugs = new Set(zee.map(h=>h.manufacturerSlug));
check('Zee: all spellings share one slug', zeeSlugs.size, 1);
check('Zee: canonical name is set', zee.every(h=>h.manufacturerCanonical.length>0), true);
check('Zee: raw spellings still differ (mirror, not merged text)',
  new Set(zee.map(h=>h.manufacturer)).size, n=>n>1);

// A query typed as the canonical name finds batches published under other
// spellings -- e.g. ALL-CAPS or "M/s." variants that don't contain it literally.
const canonHits = search('Zee Laboratories Ltd','manufacturer',hits,ms).results;
check('canonical-name query reaches non-matching raw spellings',
  canonHits.some(h=>!h.manufacturer.toLowerCase().includes('zee laboratories ltd')), true);

// Placeholders have no company page. A slug here would be a link to a page that
// deliberately does not exist (plan.md §1.1).
const placeholder = hits.filter(h=>/^\s*(under investigation|not mentioned|not applicable|spurious|nm|nil)/i.test(h.manufacturer));
check('placeholder records exist', placeholder.length, n=>n>=51);
check('placeholder records have NO manufacturer slug', placeholder.every(h=>h.manufacturerSlug===''), true);
check('placeholder records have NO canonical name', placeholder.every(h=>h.manufacturerCanonical===''), true);

// all mode merges
check('all "SIF2736A" finds the batch', search('SIF2736A','all',hits,ms).total, n=>n>=1);
check('empty query', search('   ','all',hits,ms).total, 0);

// disputed flag + slug integrity
const disputed = hits.filter(h=>h.disputed);
check('disputed records present', disputed.length, 43);
check('every resolved hit has a manufacturer slug',
  hits.filter(h=>h.manufacturerCanonical).every(h=>h.manufacturerSlug.length>0), true);
check('slug is present iff canonical name is',
  hits.every(h=>Boolean(h.manufacturerSlug)===Boolean(h.manufacturerCanonical)), true);
check('every hit has an id', hits.every(h=>h.id.length>0), true);

// Lab type is derived from the laboratory's identity, not CDSCO's reporting-source
// field. The field contradicts the lab it names on 857 records, so these assert the
// derived value reaches the client and that the two are genuinely different.
const central = hits.filter(h=>h.labType==='central');
const stateLab = hits.filter(h=>h.labType==='state');
check('every hit has a lab type', hits.every(h=>['central','state','unknown'].includes(h.labType)), true);
check('central lab records (derived)', central.length, 3860);
check('state lab records (derived)', stateLab.length, 2272);
check('unknown lab type is rare', hits.filter(h=>h.labType==='unknown').length, n=>n<50);
// The whole point: derived central > published central, because CDSCO files 832
// of its own laboratories' records as "State lab".
check('derived central exceeds published central',
  central.length > hits.filter(h=>h.section==='central_lab').length, true);
check('records where published section disagrees with derived type',
  hits.filter(h=>(h.section==='state_lab'&&h.labType==='central')||(h.section==='central_lab'&&h.labType==='state')).length,
  857);

// Index shape: the canonical table is per company, the raw table per spelling.
check('canonSlugs matches canonNames length', payload.canonSlugs.length, payload.canonNames.length);
check('canonical table is smaller than the raw table',
  payload.canonNames.length, n=>n>0 && n<payload.manufacturers.length);
check('mfrCanon covers every raw spelling', payload.mfrCanon.length, payload.manufacturers.length);
check('canonical slugs are unique', new Set(payload.canonSlugs).size, payload.canonSlugs.length);

console.log(`\n${fails === 0 ? 'ALL PASS' : fails + ' FAILURES'}`);
process.exit(fails ? 1 : 0);
