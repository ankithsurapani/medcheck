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

  unknownField: 'Not published',
  unknownFieldHint: 'CDSCO did not publish this field for this record',

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

export const SECTION_DESCRIPTIONS: Record<string, string> = {
  central_lab: 'Tested by a CDSCO or central laboratory, as recorded by the regulator.',
  state_lab: 'Tested by a state drug testing laboratory, as recorded by the regulator.',
  spurious: 'Published by CDSCO on its list of spurious drugs.',
};
