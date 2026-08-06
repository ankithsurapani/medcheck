/**
 * Client-side search over the static index.
 *
 * Three modes, because the ticket asks for three different matching behaviours
 * and they genuinely need different algorithms:
 *
 *   drug         fuzzy / typo-tolerant  -> MiniSearch, prefix + fuzzy
 *   batch        exact                  -> normalised equality, no fuzz
 *   manufacturer substring              -> plain substring on manufacturer_raw
 *
 * Batch deliberately does NOT fuzzy-match. plan.md §5.4: batch numbers are not
 * unique across manufacturers and are often short strings like "2451". A fuzzy
 * batch search would surface a different company's batch as if it were yours,
 * which is precisely the confusion this site exists to remove.
 *
 * The index is columnar (parallel arrays) to keep the download small; it is
 * rehydrated into records here, once.
 */

import MiniSearch from 'minisearch';

export interface IndexPayload {
  manufacturers: string[];
  manufacturerSlugs: string[];
  id: string[];
  drug: (string | null)[];
  batch: (string | null)[];
  mfr: number[];
  month: (string | null)[];
  categories: string[][];
  section: (string | null)[];
  disputed: number[];
}

export interface SearchHit {
  id: string;
  drug: string;
  batch: string;
  manufacturer: string;
  manufacturerSlug: string;
  month: string;
  categories: string[];
  section: string;
  disputed: boolean;
}

export type SearchMode = 'all' | 'drug' | 'batch' | 'manufacturer';

export function hydrate(payload: IndexPayload): SearchHit[] {
  const out: SearchHit[] = new Array(payload.id.length);
  for (let i = 0; i < payload.id.length; i++) {
    const m = payload.mfr[i];
    out[i] = {
      id: payload.id[i],
      drug: payload.drug[i] ?? '',
      batch: payload.batch[i] ?? '',
      manufacturer: payload.manufacturers[m] ?? '',
      manufacturerSlug: payload.manufacturerSlugs[m] ?? '',
      month: payload.month[i] ?? '',
      categories: payload.categories[i] ?? [],
      section: payload.section[i] ?? '',
      disputed: payload.disputed[i] === 1,
    };
  }
  return out;
}

export function buildMiniSearch(hits: SearchHit[]): MiniSearch<SearchHit> {
  const ms = new MiniSearch<SearchHit>({
    fields: ['drug', 'manufacturer'],
    storeFields: ['id'],
    idField: 'id',
    searchOptions: {
      prefix: true,
      fuzzy: 0.2,
      boost: { drug: 3 },
    },
  });
  ms.addAll(hits);
  return ms;
}

/** Batch numbers vary in punctuation between sources: "1-3098" vs "1 3098". */
function normaliseBatch(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]/g, '');
}

export function search(
  query: string,
  mode: SearchMode,
  hits: SearchHit[],
  ms: MiniSearch<SearchHit> | null,
  limit = 100,
): { results: SearchHit[]; total: number } {
  const q = query.trim();
  if (!q) return { results: [], total: 0 };

  let matched: SearchHit[];

  if (mode === 'batch') {
    const nq = normaliseBatch(q);
    matched = nq ? hits.filter((h) => normaliseBatch(h.batch) === nq) : [];
  } else if (mode === 'manufacturer') {
    const nq = q.toLowerCase();
    matched = hits.filter((h) => h.manufacturer.toLowerCase().includes(nq));
  } else if (mode === 'drug') {
    matched = fuzzyDrug(q, hits, ms);
  } else {
    // "All" runs every mode and merges, so a user who pastes a batch number into
    // the default box still finds it without having to know which tab to pick.
    const seen = new Set<string>();
    matched = [];
    const nq = normaliseBatch(q);
    if (nq) {
      for (const h of hits) {
        if (normaliseBatch(h.batch) === nq && !seen.has(h.id)) {
          seen.add(h.id);
          matched.push(h);
        }
      }
    }
    for (const h of fuzzyDrug(q, hits, ms)) {
      if (!seen.has(h.id)) {
        seen.add(h.id);
        matched.push(h);
      }
    }
    const lq = q.toLowerCase();
    for (const h of hits) {
      if (!seen.has(h.id) && h.manufacturer.toLowerCase().includes(lq)) {
        seen.add(h.id);
        matched.push(h);
      }
    }
  }

  return { results: matched.slice(0, limit), total: matched.length };
}

function fuzzyDrug(
  q: string,
  hits: SearchHit[],
  ms: MiniSearch<SearchHit> | null,
): SearchHit[] {
  if (!ms) {
    const lq = q.toLowerCase();
    return hits.filter((h) => h.drug.toLowerCase().includes(lq));
  }
  const byId = new Map(hits.map((h) => [h.id, h]));
  return ms
    .search(q, { prefix: true, fuzzy: 0.2, boost: { drug: 3 } })
    .map((r) => byId.get(r.id as string))
    .filter((h): h is SearchHit => Boolean(h));
}
