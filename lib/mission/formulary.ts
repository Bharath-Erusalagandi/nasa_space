import type { TriageOutcome } from "./triage";

export type FormularyItem = { id: string; name: string; source: string; needsCheck: boolean };

const WHO_MALARIA = "https://www.who.int/publications/i/item/guidelines-for-malaria";
const ZAMBIA_MALARIA = "https://static1.squarespace.com/static/58d002f017bffcf99fe21889/t/5cb9738a42ffca0001aaedbc/1555657626933/NationalMalariaTreatmentGuidelines2017_Final20170917+%281%29.pdf";
const WHO_IMCI = "https://www.who.int/publications/m/item/integrated-management-of-childhood-illness---chart-booklet-(march-2014)";

export const ITEMS = {
  referral_transport: { id: "referral_transport", name: "Referral transport to the nearest hospital", source: WHO_IMCI, needsCheck: false },
  malaria_rdt: { id: "malaria_rdt", name: "Malaria rapid diagnostic tests", source: WHO_MALARIA, needsCheck: false },
  artemether_lumefantrine: { id: "artemether_lumefantrine", name: "Artemether-lumefantrine tablets", source: ZAMBIA_MALARIA, needsCheck: false },
} satisfies Record<string, FormularyItem>;

export function itemsFor(outcome: TriageOutcome, fever = false): FormularyItem[] {
  if (outcome === "urgent_referral") return [ITEMS.referral_transport, ITEMS.malaria_rdt, ITEMS.artemether_lumefantrine];
  return fever ? [ITEMS.malaria_rdt] : [];
}
