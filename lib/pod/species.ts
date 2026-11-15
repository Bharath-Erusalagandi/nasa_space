// The 8 species the mosquito model knows (the HumBugDB species task), with what each can carry and its photo.
// Sources for the roles are in docs/REFERENCES.md (WHO fact sheets, Zambia NMESP 2022-2026, CDC DPDx).

export type VectorGroup = "anopheles" | "aedes" | "culex" | "mansonia";

export const GENUS: Record<VectorGroup, string> = { anopheles: "Anopheles", aedes: "Aedes", culex: "Culex", mansonia: "Mansonia" };

type Photo = { file: string; shows: string; credit: string; page: string };

export type Species = { label: string; name: string; group: VectorGroup; role: string; primaryMalaria: boolean; photo: Photo; clip: string };

const PHOTOS = {
  arabiensis: { file: "an-arabiensis.jpg", shows: "Anopheles arabiensis", credit: "CDC / James Gathany, public domain", page: "https://commons.wikimedia.org/wiki/File:Anopheles-arabiensis.png" },
  funestus: { file: "an-funestus.jpg", shows: "Anopheles funestus", credit: "James Gathany, Frank Collins, CDC, CC0", page: "https://commons.wikimedia.org/wiki/File:Anopheles_Funetus.jpg" },
  gambiae: { file: "an-gambiae.jpg", shows: "Anopheles gambiae (no open photo of An. squamosus found)", credit: "CDC / James D. Gathany, public domain", page: "https://commons.wikimedia.org/wiki/File:Anopheles_gambiae_mosquito_feeding_(CDC_PHIL_1354).jpg" },
  coustani: { file: "an-coustani.jpg", shows: "Anopheles coustani", credit: "Jens N. Lallensack, CC BY 4.0", page: "https://commons.wikimedia.org/wiki/File:Anopheles_coustani.jpg" },
  pipiens: { file: "cx-pipiens.jpg", shows: "Culex pipiens, male", credit: "Volkmar Becher, CC0", page: "https://commons.wikimedia.org/wiki/File:Culex_pipiens_male.jpg" },
  aegypti: { file: "ae-aegypti.jpg", shows: "Aedes aegypti", credit: "Graham Snodgrass, Army Medicine, CC BY 2.0", page: "https://commons.wikimedia.org/wiki/File:Aedes_aegypti_(14717750942).jpg" },
  mansonia: { file: "mansonia.jpg", shows: "Mansonia titillans (no open photo of the African species found)", credit: "Alex Abair, CC BY 4.0", page: "https://commons.wikimedia.org/wiki/File:Mansonia_titillans_281557011.jpg" },
} satisfies Record<string, Photo>;

const clip = (label: string) => `/clips/${label.replace(". ", "-").replace(/ /g, "-").toLowerCase()}.wav`;

const MAIN_MALARIA = "Main malaria carrier in Zambia";
const OTHER_ANOPHELES = "Anopheles, not a main malaria carrier in Zambia";

const LIST: Omit<Species, "clip">[] = [
  { label: "An. arabiensis", name: "Anopheles arabiensis", group: "anopheles", role: MAIN_MALARIA, primaryMalaria: true, photo: PHOTOS.arabiensis },
  { label: "An. funestus", name: "Anopheles funestus", group: "anopheles", role: MAIN_MALARIA, primaryMalaria: true, photo: PHOTOS.funestus },
  { label: "An. squamosus", name: "Anopheles squamosus", group: "anopheles", role: OTHER_ANOPHELES, primaryMalaria: false, photo: PHOTOS.gambiae },
  { label: "An. coustani", name: "Anopheles coustani", group: "anopheles", role: OTHER_ANOPHELES, primaryMalaria: false, photo: PHOTOS.coustani },
  { label: "Cx. pipiens complex", name: "Culex pipiens complex", group: "culex", role: "West Nile virus, filariasis", primaryMalaria: false, photo: PHOTOS.pipiens },
  { label: "Ae. aegypti", name: "Aedes aegypti", group: "aedes", role: "Dengue, chikungunya, Zika, yellow fever", primaryMalaria: false, photo: PHOTOS.aegypti },
  { label: "Ma. uniformis", name: "Mansonia uniformis", group: "mansonia", role: "Filariasis", primaryMalaria: false, photo: PHOTOS.mansonia },
  { label: "Ma. africanus", name: "Mansonia africanus", group: "mansonia", role: "Filariasis", primaryMalaria: false, photo: PHOTOS.mansonia },
];

export const SPECIES: Species[] = LIST.map((s) => ({ ...s, clip: clip(s.label) }));

export const speciesFor = (label: string | null | undefined) => SPECIES.find((s) => s.label === label);
