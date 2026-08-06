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

// manufacturer: substring on raw
check('mfr "Zee Laboratories" substring', search('Zee Laboratories','manufacturer',hits,ms).total, n=>n>5);
check('mfr address fragment "Paonta Sahib"', search('Paonta Sahib','manufacturer',hits,ms).total, n=>n>3);
check('mfr nonsense', search('qqqqqqq','manufacturer',hits,ms).total, 0);

// all mode merges
check('all "SIF2736A" finds the batch', search('SIF2736A','all',hits,ms).total, n=>n>=1);
check('empty query', search('   ','all',hits,ms).total, 0);

// disputed flag + slug integrity
const disputed = hits.filter(h=>h.disputed);
check('disputed records present', disputed.length, 43);
check('every hit has a manufacturer slug', hits.every(h=>h.manufacturerSlug.length>0), true);
check('every hit has an id', hits.every(h=>h.id.length>0), true);

console.log(`\n${fails === 0 ? 'ALL PASS' : fails + ' FAILURES'}`);
process.exit(fails ? 1 : 0);
