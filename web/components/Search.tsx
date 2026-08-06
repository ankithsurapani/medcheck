'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type MiniSearch from 'minisearch';
import { ResultCard } from '@/components/ResultCard';
import { COPY } from '@/lib/copy';
import {
  buildMiniSearch,
  hydrate,
  search,
  type IndexPayload,
  type SearchHit,
  type SearchMode,
} from '@/lib/search';

const MODES: { key: SearchMode; label: string; placeholder: string; hint: string }[] = [
  {
    key: 'all',
    label: 'Everything',
    placeholder: 'Medicine, batch number or manufacturer',
    hint: 'Searches medicine names, batch numbers and manufacturers at once.',
  },
  {
    key: 'drug',
    label: 'Medicine',
    placeholder: 'e.g. Pantoprazole, Amoxycillin',
    hint: 'Spelling does not have to be exact — close matches are shown.',
  },
  {
    key: 'batch',
    label: 'Batch number',
    placeholder: 'e.g. SIF2736A',
    hint: 'Batch search is exact. Batch numbers are reused by different companies, so a close-but-different number is a different medicine.',
  },
  {
    key: 'manufacturer',
    label: 'Manufacturer',
    placeholder: 'e.g. Zee Laboratories',
    hint: 'Matches the manufacturer text exactly as CDSCO published it, including the address.',
  },
];

const PAGE_SIZE = 25;

function IconSearch({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className={className}>
      <circle cx="11" cy="11" r="6.25" stroke="currentColor" strokeWidth="1.7" />
      <path d="m15.6 15.6 3.9 3.9" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

function IconSpinner({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className={`animate-spin ${className}`}>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function Search({ recordCount }: { recordCount: number }) {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<SearchMode>('all');
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [shown, setShown] = useState(PAGE_SIZE);
  const msRef = useRef<MiniSearch<SearchHit> | null>(null);
  const loadStarted = useRef(false);

  /**
   * The index is ~1.7 MB (≈300 KB over the wire). Loading it on mount would
   * make a phone pay for it before knowing whether the visitor intends to
   * search. It is fetched on the first real intent instead — focus, typing, or
   * browser idle — so the page itself is usable immediately.
   */
  const loadIndex = useCallback(async () => {
    if (loadStarted.current) return;
    loadStarted.current = true;
    setStatus('loading');
    try {
      const res = await fetch('/data/search-index.json');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const payload = (await res.json()) as IndexPayload;
      const h = hydrate(payload);
      setHits(h);
      msRef.current = buildMiniSearch(h);
      setStatus('ready');
    } catch {
      setStatus('error');
      loadStarted.current = false;
    }
  }, []);

  useEffect(() => {
    const w = window as Window & { requestIdleCallback?: (cb: () => void) => number };
    if (typeof w.requestIdleCallback === 'function') {
      const id = w.requestIdleCallback(() => void loadIndex());
      return () => (window as unknown as { cancelIdleCallback?: (h: number) => void })
        .cancelIdleCallback?.(id);
    }
    const t = setTimeout(() => void loadIndex(), 1200);
    return () => clearTimeout(t);
  }, [loadIndex]);

  const { results, total } = useMemo(() => {
    if (!hits) return { results: [] as SearchHit[], total: 0 };
    return search(query, mode, hits, msRef.current, 500);
  }, [query, mode, hits]);

  useEffect(() => setShown(PAGE_SIZE), [query, mode]);

  const active = MODES.find((m) => m.key === mode)!;
  const trimmed = query.trim();
  const searching = status === 'loading' && trimmed.length > 0;
  const hasQuery = trimmed.length > 0;

  return (
    <section aria-labelledby="search-heading">
      <h1
        id="search-heading"
        className="font-display text-2xl font-bold leading-tight tracking-tight text-foreground sm:text-3xl"
      >
        {COPY.tagline}
      </h1>
      <p className="mt-2 max-w-2xl text-[0.9375rem] leading-relaxed text-muted-foreground">
        Search {recordCount.toLocaleString('en-IN')} batches that India’s drug regulator, CDSCO, has
        published as Not of Standard Quality or spurious. Look up a medicine name, a batch number
        from a pack, or a manufacturer.
      </p>

      {/* Mode selector. Radio semantics, not tabs: this changes how the query is
          interpreted, and screen-reader users need that stated. */}
      <fieldset className="mt-5">
        <legend className="sr-only">What are you searching by?</legend>
        <div role="radiogroup" aria-label="Search by" className="flex flex-wrap gap-2">
          {MODES.map((m) => {
            const selected = m.key === mode;
            return (
              <button
                key={m.key}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => setMode(m.key)}
                className={[
                  'inline-flex min-h-11 cursor-pointer items-center rounded-full border px-4 text-sm font-medium transition-colors duration-200',
                  selected
                    ? 'border-primary bg-primary text-on-primary'
                    : 'border-border bg-card text-muted-foreground hover:border-secondary hover:text-foreground',
                ].join(' ')}
              >
                {m.label}
              </button>
            );
          })}
        </div>
      </fieldset>

      <div className="mt-3">
        <label htmlFor="q" className="block text-sm font-medium text-foreground">
          Search by {active.label.toLowerCase()}
        </label>
        <div className="relative mt-1.5">
          <IconSearch className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
          <input
            id="q"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => void loadIndex()}
            placeholder={active.placeholder}
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            enterKeyHint="search"
            aria-describedby="q-hint"
            className="min-h-12 w-full rounded-lg border border-border bg-card py-3 pl-11 pr-4 text-base text-foreground placeholder:text-muted-foreground"
          />
          {searching ? (
            <IconSpinner className="absolute right-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
          ) : null}
        </div>
        <p id="q-hint" className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
          {active.hint}
        </p>
      </div>

      {status === 'error' ? (
        <p className="mt-4 rounded-lg border border-notice-border bg-notice-soft p-3 text-sm text-foreground">
          The search index could not be loaded.{' '}
          <button
            type="button"
            onClick={() => void loadIndex()}
            className="cursor-pointer font-medium underline underline-offset-2"
          >
            Try again
          </button>
          .
        </p>
      ) : null}

      {/* Announced politely so screen readers hear the count without the list
          being re-read on every keystroke. */}
      <p aria-live="polite" className="sr-only">
        {hasQuery && status === 'ready'
          ? `${total} ${total === 1 ? 'record' : 'records'} found`
          : ''}
      </p>

      <div className="mt-6">
        {!hasQuery ? (
          <EmptyPrompt />
        ) : status !== 'ready' ? (
          <p className="text-sm text-muted-foreground">Preparing search…</p>
        ) : total === 0 ? (
          <NoResults query={trimmed} mode={mode} />
        ) : (
          <>
            <p className="text-sm text-muted-foreground">
              {total.toLocaleString('en-IN')} {total === 1 ? 'record' : 'records'}
              {total > shown ? ` · showing first ${Math.min(shown, total)}` : ''}
            </p>
            <ul className="mt-3 grid gap-3">
              {results.slice(0, shown).map((r) => (
                <ResultCard key={r.id} r={r} />
              ))}
            </ul>
            {total > shown ? (
              <button
                type="button"
                onClick={() => setShown((s) => s + PAGE_SIZE)}
                className="mt-4 inline-flex min-h-11 w-full cursor-pointer items-center justify-center rounded-lg border border-border bg-card px-4 text-sm font-medium text-foreground transition-colors duration-200 hover:border-secondary sm:w-auto"
              >
                Show {Math.min(PAGE_SIZE, total - shown)} more
              </button>
            ) : null}
          </>
        )}
      </div>
    </section>
  );
}

function EmptyPrompt() {
  return (
    <div className="rounded-lg border border-dashed border-border p-5">
      <h2 className="font-display text-base font-semibold text-foreground">
        What you can look up
      </h2>
      <ul className="mt-2 space-y-1.5 text-sm leading-relaxed text-muted-foreground">
        <li>
          <strong className="font-medium text-foreground">A batch number</strong> printed on your
          pack — the most precise search, because CDSCO flags specific batches.
        </li>
        <li>
          <strong className="font-medium text-foreground">A medicine name</strong> — spelling does
          not have to be exact.
        </li>
        <li>
          <strong className="font-medium text-foreground">A manufacturer</strong> as printed on the
          packaging.
        </li>
      </ul>
      <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
        Finding nothing is the common case and it is good news in the narrow sense that this batch
        was not flagged — but it is not a safety check. Most medicines are never tested.
      </p>
    </div>
  );
}

/** plan.md Phase 3a — "no results" must not read as "verified safe". */
function NoResults({ query, mode }: { query: string; mode: SearchMode }) {
  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <h2 className="font-display text-lg font-bold text-foreground">{COPY.noResults.heading}</h2>
      <p className="mt-2 text-[0.9375rem] leading-relaxed text-foreground">
        Nothing matches <span className="font-medium break-anywhere">“{query}”</span>.{' '}
        {COPY.noResults.body.replace('Nothing in MedCheck matches that search. ', '')}
      </p>
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
        {COPY.noResults.detail}
      </p>
      <div className="mt-4 border-t border-border pt-4">
        <h3 className="text-sm font-semibold text-foreground">Things to try</h3>
        <ul className="mt-1.5 space-y-1 text-sm leading-relaxed text-muted-foreground">
          {mode === 'batch' ? (
            <li>
              Batch search is exact. Check the pack for letters and digits that look alike — 0 and
              O, 1 and I.
            </li>
          ) : null}
          {mode === 'manufacturer' ? (
            <li>
              Try just the company name without “M/s.”, “Pvt.” or “Ltd.” — CDSCO writes these
              inconsistently.
            </li>
          ) : null}
          <li>Search the medicine’s generic name rather than the brand, or the other way round.</li>
          <li>Try the “Everything” tab, which searches all three fields at once.</li>
        </ul>
      </div>
    </div>
  );
}
