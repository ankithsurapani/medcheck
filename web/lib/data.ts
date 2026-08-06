/**
 * Build-time data access. Server components only.
 *
 * These JSON files are produced by scripts/export_static.py and are never sent
 * to the browser — they are read while rendering static pages. The only thing a
 * client downloads is public/data/search-index.json.
 */

import records from '@/data/records.json';
import manufacturers from '@/data/manufacturers.json';

export interface MedRecord {
  id: string;
  alertMonth: string | null;
  alertSection: string | null;
  drugName: string | null;
  dosageForm: string | null;
  batchNumber: string | null;
  mfgDate: string | null;
  expiryDate: string | null;
  manufacturer: string;
  manufacturerSlug: string;
  labelClaimDisputed: number | null;
  failureReason: string | null;
  failureCategories: string[];
  testingLab: string | null;
  state: string | null;
  sourceUrl: string;
  sourceType: string | null;
  parseConfidence: number | null;
  parseFlags: string[];
}

export interface Manufacturer {
  slug: string;
  name: string;
  state: string | null;
  recordIds: string[];
  count: number;
}

const ALL = records as MedRecord[];
const ALL_MFRS = manufacturers as Manufacturer[];

const byId = new Map(ALL.map((r) => [r.id, r]));
const mfrBySlug = new Map(ALL_MFRS.map((m) => [m.slug, m]));

export function allRecords(): MedRecord[] {
  return ALL;
}

export function getRecord(id: string): MedRecord | undefined {
  return byId.get(id);
}

export function allManufacturers(): Manufacturer[] {
  return ALL_MFRS;
}

export function getManufacturer(slug: string): Manufacturer | undefined {
  return mfrBySlug.get(slug);
}

export function recordsFor(m: Manufacturer): MedRecord[] {
  return m.recordIds.map((id) => byId.get(id)!).filter(Boolean);
}

export function stats() {
  const months = new Set<string>();
  let disputed = 0;
  for (const r of ALL) {
    if (r.alertMonth) months.add(r.alertMonth);
    if (r.labelClaimDisputed === 1) disputed += 1;
  }
  const sorted = [...months].sort();
  return {
    recordCount: ALL.length,
    manufacturerCount: ALL_MFRS.length,
    monthCount: months.size,
    earliestMonth: sorted[0] ?? null,
    latestMonth: sorted[sorted.length - 1] ?? null,
    disputedCount: disputed,
  };
}
