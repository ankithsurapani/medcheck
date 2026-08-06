/**
 * Display formatting.
 *
 * Rule that governs this whole file (plan.md §1.4): a value MedCheck does not
 * have is rendered as an explicit "Not published", never as an empty cell, a
 * dash, or a plausible-looking guess. A blank space reads as "nothing was
 * wrong"; the truth is "the regulator did not publish this".
 */

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

/** "2025-06" -> "June 2025"; "2025-06-12" -> "12 June 2025". */
export function formatMonth(value: string | null | undefined): string | null {
  if (!value) return null;
  const m = /^(\d{4})-(\d{2})(?:-(\d{2}))?$/.exec(value);
  if (!m) return value;
  const name = MONTHS[Number(m[2]) - 1];
  if (!name) return value;
  return m[3] ? `${Number(m[3])} ${name} ${m[1]}` : `${name} ${m[1]}`;
}

export function formatMonthShort(value: string | null | undefined): string | null {
  const full = formatMonth(value);
  return full ? full.replace(/^(\d+ )?(\w{3})\w*/, (_, d, mon) => `${d ?? ''}${mon}`) : null;
}

/** True when a field is genuinely absent rather than merely falsy-looking. */
export function isMissing(value: unknown): boolean {
  return value === null || value === undefined || value === '';
}

/**
 * Human-readable summary of a parse flag. Flags are machine strings like
 * "state_not_derived:no_match" — shown to users only in plain words, and only
 * where they change how a field should be read.
 */
export function describeFlag(flag: string): string | null {
  const kind = flag.split(':')[0];
  switch (kind) {
    case 'state_not_derived':
      return 'The manufacturing state could not be read from the address CDSCO published.';
    case 'state_ambiguous':
      return 'The published address named more than one state, so no state is shown rather than guessing.';
    case 'manufacturer_unknown_placeholder':
      return 'CDSCO did not name a manufacturer for this batch — the entry reads “Under Investigation”.';
    case 'failure_category_unmapped':
      return 'The stated reason did not match a known test category, so it is listed as Other. The original wording is shown.';
    case 'expiry_before_mfg':
      return 'The published expiry date is earlier than the manufacture date. Both are shown exactly as published.';
    case 'date_unparsed':
      return 'A published date could not be read as a date. It is shown as published.';
    case 'duplicate_source_rows_collapsed':
      return 'CDSCO published this same row more than once; it appears here once.';
    case 'id_collision_disambiguated':
      return 'CDSCO published rows that are identical in every field we hold. They are kept as separate records.';
    case 'missing_required':
      return 'A field we normally expect was not published for this record.';
    case 'alert_section_unrecognised':
    case 'alert_section_missing':
      return 'The reporting source was not stated in a form we recognise.';
    case 'batch_number_implausible':
      return 'The published batch number has an unusual format. It is shown as published.';
    case 'dispute_status_unknown':
      return 'CDSCO published no firm response for this record.';
    default:
      return null;
  }
}

/** Flags worth surfacing on a record page. Others are internal bookkeeping. */
export function userFacingFlags(flags: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const f of flags) {
    const text = describeFlag(f);
    if (text && !seen.has(text)) {
      seen.add(text);
      out.push(text);
    }
  }
  return out;
}

export function confidenceLabel(c: number | null): 'high' | 'medium' | 'low' {
  if (c === null) return 'medium';
  if (c >= 0.95) return 'high';
  if (c >= 0.8) return 'medium';
  return 'low';
}
