/**
 * Every user-facing string that isn't a failure-category explanation.
 *
 * Centralised for the same reason as failure-categories.ts: Phase 3b adds Hindi,
 * and that must not mean hunting strings out of JSX. Components import from here.
 *
 * The SAFETY and BATCH_NOT_PRODUCT strings are quoted verbatim from plan.md §1.2
 * and §1.3. They are non-negotiable copy — do not reword them to fit a layout.
 */

export const COPY = {
  siteName: 'MedCheck',
  tagline: 'Search medicines flagged by India’s drug regulator',

  /** plan.md §1.2 — verbatim, non-dismissible, on every result. */
  safety: {
    heading: 'Do not stop taking your medicine because of this page',
    body:
      'This batch was flagged by CDSCO. This does not mean you should stop taking your medicine. Show this page to your pharmacist or doctor and ask them.',
  },

  /** plan.md §1.3 — must be visible on every result, not footnoted. */
  batchNotProduct: {
    heading: 'One batch, not the whole product',
    body:
      'CDSCO tested this specific batch. A flag here does not mean other batches of the same medicine are affected, and it is not a judgement about the manufacturer overall.',
  },

  /** plan.md §5.5 — shown only when label_claim_disputed is true. */
  disputed: {
    heading: 'The named manufacturer says this batch is not theirs',
    body:
      'CDSCO recorded that the company named on the label has told the regulator they did not make this batch, and that it appears to be counterfeit. The regulator’s own wording is included below. Treat the company name here as the name printed on the packaging, not a finding against that company.',
  },

  noResults: {
    heading: 'No matching records',
    body:
      'Nothing in MedCheck matches that search. This means the medicine has not been flagged in the CDSCO data we hold — it does not mean it has been checked and found safe.',
    detail:
      'MedCheck only holds what CDSCO has published. Most medicines are never tested, and a medicine that was never tested cannot appear here.',
  },

  samplingCaveat:
    'CDSCO does not test medicines at random, so counts here describe the samples the regulator chose to test — they are not a failure rate for the market.',

  /**
   * Phase 2a merged spellings onto companies, so the Phase 3a "one spelling only"
   * disclaimer is no longer true. What replaces it says the same honest thing at
   * lower volume: the merge is real, it is checked, and it is not finished.
   */
  manufacturerPage: {
    mergedNotice: 'Different spellings of this company have been combined',
    mergedBody:
      'CDSCO re-types the manufacturer name and address every month, so one company appears under many spellings. We have grouped the spellings below into this one company. Every spelling is listed so you can check the grouping yourself.',
    partialNotice:
      'This grouping is not finished. Pairs we were not confident about were left apart rather than merged, so a company may still have more than one page here. We would rather show you two pages for one company than put one company’s failures on another company’s page.',
    aliasHeading: (n: number) =>
      n === 1 ? 'The 1 spelling CDSCO published' : `The ${n} spellings CDSCO published`,
    aliasBody:
      'These are the exact manufacturer entries, reproduced as published — punctuation, addresses and all.',
    addressHeading: 'Address, as published',
  },

  /** Shown on a record whose manufacturer field is a placeholder, not a company. */
  notACompany: {
    heading: 'CDSCO did not name a manufacturer for this batch',
    body:
      'The manufacturer field on this record reads “{text}”. That is not a company — it is what the regulator publishes when the real maker of a batch is not known, which is usual for a suspected counterfeit. There is no manufacturer page for it, because there is no company to attribute it to.',
  },

  /**
   * Laboratory type. CDSCO's own "reporting source" field contradicts itself —
   * it files the same laboratory as a central lab on one record and a state lab
   * on the next, on 857 records. MedCheck shows the type derived from which
   * laboratory it actually is, and says so where CDSCO's own field disagrees,
   * rather than silently correcting the regulator (plan.md §1.1).
   */
  labType: {
    central: 'Central laboratory (CDSCO)',
    state: 'State laboratory',
    unknown: 'Laboratory not identified',
    centralHint:
      'One of the Central Drugs Standard Control Organisation’s own laboratories.',
    stateHint: 'A laboratory run by a state drugs control authority.',
    unknownHint:
      'CDSCO named a reporting source we could not match to a specific laboratory, so no type is shown rather than guessing.',
    disputed:
      'CDSCO’s own alert filed this under “{published}”, which does not match the laboratory it names. We show the laboratory’s type and leave CDSCO’s wording visible above — the regulator’s two records disagree, and hiding that would be worse than showing it.',
    publishedAs: 'CDSCO published this as',
  },

  unknownField: 'Not published',
  unknownFieldHint: 'CDSCO did not publish this field for this record',

  state: {
    // CDSCO usually does not write the state down — the address just ends in a
    // PIN code. Reading the state back out of the PIN is a real answer but a
    // weaker one than the regulator stating it, and §1.4 says a weaker source
    // has to be visible as one, not rendered identically to a stronger one.
    fromPin:
      'CDSCO did not name a state in this address. This is the state the address’s PIN code ({pin}) belongs to, not something the regulator wrote down.',
    ambiguousPinHint:
      'The address ends in a PIN code whose range covers more than one state, so no state is shown rather than guessing.',
  },

  lowConfidence: {
    heading: 'Some fields on this record are uncertain',
    body:
      'Our processing flagged something about this record. The regulator’s original wording and the link to the source are shown so you can check it yourself.',
  },
} as const;

export const SECTION_LABELS: Record<string, string> = {
  central_lab: 'Central lab',
  state_lab: 'State lab',
  spurious: 'Spurious',
};

/**
 * These describe CDSCO's OWN filing of a record, which is not always consistent
 * with the laboratory it names — hence "as filed by", not "tested by". The
 * laboratory's actual type is shown separately, under Tested by.
 */
export const SECTION_DESCRIPTIONS: Record<string, string> = {
  central_lab: 'How CDSCO filed this record in its own alert. See the laboratory above for what it actually is.',
  state_lab: 'How CDSCO filed this record in its own alert. See the laboratory above for what it actually is.',
  spurious: 'Published by CDSCO on its list of spurious drugs.',
};
