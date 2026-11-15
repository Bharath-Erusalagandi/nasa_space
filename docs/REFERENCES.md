# References

Every entry below was opened on the publisher, DOI registry, agency or dataset page on 2026-11-14. Numbers are copied from the page named beside them. A claim with no primary source is listed at the end and must not be used.

## Methods

**Mann, H. B. (1945).** Nonparametric tests against trend. *Econometrica*, 13(3), 245-259.
https://doi.org/10.2307/1907187
Used for: the Mann-Kendall trend test in `trend/trend_detective.py`.

**Kendall, M. G. (1975).** *Rank Correlation Methods*, 4th edition. Charles Griffin, London.
Catalogue record: https://www.marine.gov.scot/sma/node/16946 (ISBN 0852641990). No DOI.
Used for: the variance of the Mann-Kendall S statistic, with the ties correction.

**Sen, P. K. (1968).** Estimates of the regression coefficient based on Kendall's tau. *Journal of the American Statistical Association*, 63(324), 1379-1389.
https://doi.org/10.1080/01621459.1968.10480934
Used for: the Sen (Theil-Sen) slope, reported per decade.

**Gilbert, R. O. (1987).** *Statistical Methods for Environmental Pollution Monitoring*. Pacific Northwest Laboratory report PNL-4660, OSTI ID 7037501. The OSTI record names no publisher.
https://www.osti.gov/biblio/7037501
Used for: the rank method that gives the confidence range of the Sen slope (nonparametric trend methods, chapters 16 and 17).

**Benjamini, Y., and Hochberg, Y. (1995).** Controlling the false discovery rate: a practical and powerful approach to multiple testing. *Journal of the Royal Statistical Society Series B: Statistical Methodology*, 57(1), 289-300.
https://doi.org/10.1111/j.2517-6161.1995.tb02031.x
Used for: the false discovery rate correction across grid cells (`q`, `significant_fdr`).

**Bland, J. M., and Altman, D. G. (1986).** Statistical methods for assessing agreement between two methods of clinical measurement. *The Lancet*, 327(8476), 307-310.
https://doi.org/10.1016/S0140-6736(86)90837-8
Used for: bias and limits of agreement between the pod and the reference device (`validation/agreement.py`).

**Gelaro, R., McCarty, W., Suárez, M. J., Todling, R., and others (2017).** The Modern-Era Retrospective Analysis for Research and Applications, Version 2 (MERRA-2). *Journal of Climate*, 30(14), 5419-5454.
https://doi.org/10.1175/JCLI-D-16-0758.1
Used for: the reanalysis behind the NASA POWER daily rain and temperature series.

**NASA POWER methodology.** NASA Langley Research Center, POWER Docs, Methodology; meteorological sources and validation page.
https://power.larc.nasa.gov/docs/methodology/ and https://power.larc.nasa.gov/docs/methodology/data/sources_meteorology/
Used for: what the POWER daily series is built from (MERRA-2 from 1981, GEOS near real time after it) and the corrected precipitation field PRECTOTCORR.

**Kiskin, I., Sinka, M., Cobb, A., Rafique, W., Wang, L., Zilli, D., Gutteridge, B., Dam, R., Marinos, T., Li, Y., Msaky, D., Kaindoa, E., Killeen, G., Herreros-Moya, E., Willis, K., and Roberts, S. J. (2021).** HumBugDB: A Large-scale Acoustic Mosquito Dataset. *Proceedings of the Neural Information Processing Systems Track on Datasets and Benchmarks 1* (NeurIPS Datasets and Benchmarks 2021).
https://datasets-benchmarks-proceedings.neurips.cc/paper/2021/hash/65ded5353c5ee48d0b7d48c591b8f430-Abstract-round2.html (preprint arXiv:2110.07607; data https://doi.org/10.5281/zenodo.4904800, CC BY 4.0)
Used for: training and testing the two mosquito models (`models/mosquito/train.py`), and the held-out recordings played from the species cards (`public/clips/`). Data: CC BY 4.0.

**Luxen, D., and Vetter, C. (2011).** Real-time routing with OpenStreetMap data. *Proceedings of the 19th ACM SIGSPATIAL International Conference on Advances in Geographic Information Systems*, 513-516.
https://doi.org/10.1145/2093973.2094062
Used for: OSRM, the router that computed `public/map/routes.json` offline.

### NASA POWER acknowledgement

Copied from https://power.larc.nasa.gov/docs/referencing/ (the page asks for both sentences):

> The data was obtained from National Aeronautics and Space Administration (NASA) Langley Research Center's Prediction Of Worldwide Energy Resources (POWER) project funded through the NASA Earth Science Division.

Data reference, the page's template ("The data was obtained from the POWER Project's Hourly 2.x.x version on YYYY/MM/DD.") filled in from the API response header (`POWER Daily API`, version `v2.10.3`) and the `generated` date in `public/trends/index.json`:

> The data was obtained from the POWER Project's Daily 2.10.3 version on 2026/11/14.

## Data

**NASA POWER daily point API**, NASA Langley Research Center; source MERRA-2 (NASA GMAO). Fields PRECTOTCORR and T2M. Citation and acknowledgement as above.
https://power.larc.nasa.gov/api/temporal/daily/point
Used for: the seven seasonal indicators and the pod-site normals.

**geoBoundaries Zambia ADM1 and ADM2.** Runfola, D. et al. (2020) geoBoundaries: A global database of political administrative boundaries. PLoS ONE 15(4): e0231866. https://doi.org/10.1371/journal.pone.0231866 (short form requested at https://www.geoboundaries.org/). Licence CC BY 4.0. ADM2 lineage: GRID3, Office of the Surveyor General.
https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/ZMB/ADM1/geoBoundaries-ZMB-ADM1.geojson and .../ADM2/geoBoundaries-ZMB-ADM2.geojson
Used for: province outline, district outlines and facility districts.

**Natural Earth 1:10m admin 0 boundary lines and countries.** "Made with Natural Earth. Free vector and raster map data @ naturalearthdata.com." Public domain (https://www.naturalearthdata.com/about/terms-of-use/).
https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_boundary_lines_land.zip and https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip
Used for: international borders, country names and label points.

**Public health facilities in sub Saharan Africa.** Maina, J., Ouma, P.O., Macharia, P.M. et al. A spatial database of health facilities managed by the public health sector in sub Saharan Africa. Sci Data 6, 134 (2019). https://doi.org/10.1038/s41597-019-0142-2. Data on figshare, licence CC0 1.0 (DataCite record).
https://doi.org/10.6084/m9.figshare.7725374.v1
Used for: health facility names, types and locations.

**OpenStreetMap Zambia extract (Geofabrik).** "© OpenStreetMap contributors", data under the Open Database License 1.0 (https://www.openstreetmap.org/copyright).
https://download.geofabrik.de/africa/zambia-latest.osm.pbf
Used for: roads, rivers, towns and the OSRM road routes.

**Copernicus DEM GLO-90.** "Copernicus Digital Elevation Model (DEM) was accessed on 2026-11-14 from https://registry.opendata.aws/copernicus-dem." Required notice for modified data: produced using Copernicus WorldDEM-90 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved. Free licence (https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM).
https://copernicus-dem-90m.s3.amazonaws.com
Used for: hillshade relief.

**ECMWF ERA5 via the Open-Meteo archive API** (second source for the trend cross-check, `trend/cross_check.py`). The first two citations are the ones requested at https://open-meteo.com/en/docs/historical-weather-api; the third is the ERA5 description paper:
- Zippenfenig, P. (2023). Open-Meteo.com Weather API [Computer software]. Zenodo. https://doi.org/10.5281/ZENODO.7970649
- Hersbach, H., Bell, B., Berrisford, P., Biavati, G., Horányi, A., Muñoz Sabater, J., Nicolas, J., Peubey, C., Radu, R., Rozum, I., Schepers, D., Simmons, A., Soci, C., Dee, D., Thépaut, J-N. (2023). ERA5 hourly data on single levels from 1940 to present [Data set]. ECMWF. https://doi.org/10.24381/cds.adbb2d47
- Hersbach, H., Bell, B., Berrisford, P., and others (2020). The ERA5 global reanalysis. *Quarterly Journal of the Royal Meteorological Society*, 146(730), 1999-2049. https://doi.org/10.1002/qj.3803

Licence: API data under CC BY 4.0, with a link "Weather data by Open-Meteo.com" next to any place the data is shown (https://open-meteo.com/en/licence).
https://archive-api.open-meteo.com/v1/archive
Used for: the ERA5 trend shown beside the NASA POWER trend.

## Clinical rules

**WHO (2014). Integrated Management of Childhood Illness: chart booklet (March 2014).**
https://www.who.int/publications/m/item/integrated-management-of-childhood-illness---chart-booklet-(march-2014) (PDF: https://cdn.who.int/media/docs/default-source/mca-documents/9789241506823_chartbook_eng.pdf)
PDF page 5, "Check for general danger signs": not able to drink or breastfeed, vomits everything, convulsions, lethargic or unconscious. "A child with any general danger sign needs URGENT attention".
PDF page 6, cough or difficult breathing: "determine oxygen saturation and refer if < 90%."
Used for: `DANGER_SIGNS` and `SPO2_REFERRAL_BELOW = 90` in `lib/mission/triage.ts`, and the `referral_transport` item. The booklet covers children aged 2 months to 5 years.

**WHO guidelines for malaria (version of 10 September 2026).**
https://www.who.int/publications/i/item/guidelines-for-malaria (PDF: https://iris.who.int/server/api/core/bitstreams/d3c6488b-3ee6-41cb-960f-ddf0202cd74d/content)
Section 5.1, Diagnosing malaria (2015), good practice statement: "All cases of suspected malaria should have a parasitological test (microscopy or RDT)".
Used for: the `malaria_rdt` item and the "do a rapid malaria test" step.

**National Malaria Elimination Centre (2017). Guidelines for the Diagnosis and Treatment of Malaria in Zambia, Fifth Edition.** Lusaka.
https://static1.squarespace.com/static/58d002f017bffcf99fe21889/t/5cb9738a42ffca0001aaedbc/1555657626933/NationalMalariaTreatmentGuidelines2017_Final20170917+%281%29.pdf (file hosted by the centre's site, https://www.nmec.org.zm/)
Chapter 4, Treatment of uncomplicated malaria: "recommended ACTs are Artemether-lumefantrine (AL) and Dihydroartemisin-Piparaquine (DHA-PQ)."
Used for: the `artemether_lumefantrine` item. Correction to the plan: AL is one of two first-line ACTs in Zambia, not the only one.

## Pitch statistics

**Malaria cases and deaths in Zambia.** WHO World malaria report 2025, Annex 4-H, "Population denominator for case incidence and mortality rate, and estimated malaria cases and deaths, 2000-2024", row Zambia, 2024.
https://cdn.who.int/media/docs/default-source/malaria/world-malaria-reports/wmr2025_annex_4h.xlsx (listed at https://www.who.int/publications/m/item/annexes-world-malaria-report-2025)
- Estimated cases, 2024: 5,380,115 (range 4,333,000 to 6,652,000).
- Estimated deaths, 2024: 8,682 (range 7,740 to 10,200).
- Population at risk, 2024: 21,314,955.
These are WHO model estimates, not reported cases.

**Antimalarial and rapid test availability at facilities.** Only old, four-district surveys were found:
- Zurovac, D., Ndhlovu, M., Sipilanyambe, N., Chanda, P., Hamer, D. H., and others (2007). Paediatric malaria case-management with artemether-lumefantrine in Zambia: a repeat cross-sectional study. *Malaria Journal*, 6, 31. https://doi.org/10.1186/1475-2875-6-31 (full text https://pmc.ncbi.nlm.nih.gov/articles/PMC1832199/). 2006 survey of 104 facilities in four districts: "40% of facilities still did not have any artemether-lumefantrine in stock on the survey day"; "facilities were out of stock for approximately 30% of the year".
- Hamer, D. H., Ndhlovu, M., Zurovac, D., and others (2007). Improved diagnostic testing and malaria treatment practices in Zambia. *JAMA*, 297(20), 2227-2231. https://doi.org/10.1001/jama.297.20.2227 (https://pmc.ncbi.nlm.nih.gov/articles/PMC2674546/). 2006: "63% of facilities had RDTs available on the day of the survey."
If used, say "in a 2006 survey of four districts". These do not describe today's supply chain.

**Distance to a facility for rural households.** Mochida, K., Nonaka, D., Wamulume, J., and Kobayashi, J. (2021). Supply-side barriers to the use of public healthcare facilities for childhood illness care in rural Zambia. *International Journal of Environmental Research and Public Health*, 18(10), 5409. https://doi.org/10.3390/ijerph18105409 (https://pmc.ncbi.nlm.nih.gov/articles/PMC8158757/). Data: Zambia DHS 2018 linked to the 2017 Health Facility Census, rural children.
- Abstract: "The median distances to the nearest facility were 4.5 km among 854 febrile children" (4.6 km among 813 children with diarrhoea).
- Discussion: "Nearly half of the present study's participants live over 5 km away".

**Seasonal loss of access.** UNICEF Zambia, "Rebuilding hope after the Lundazi floods", 30 January 2026 (Lundazi is in Eastern Province). https://www.unicef.org/zambia/stories/rebuilding-hope-after-lundazi-floods
- "entire communities were cut off from basic services."
- Volunteers oriented "across 4 health facilities directly impacted by the floods."
This supports flood disruption in one season and district. It gives no figure for roads.

## Conversation and species roles

**World Health Organization (2025).** Malaria, fact sheet, 4 December 2025. https://www.who.int/news-room/fact-sheets/detail/malaria
Used for: malaria spread by some infected female Anopheles; symptoms 10 to 15 days after the bite; test before treating; nets.

**World Health Organization (2025).** Dengue and severe dengue, fact sheet, 21 August 2025. https://www.who.int/news-room/fact-sheets/detail/dengue-and-severe-dengue
Used for: Aedes aegypti biting by day; dengue symptoms and warning signs; paracetamol, fluids, and avoiding ibuprofen and aspirin; covering and cleaning water containers.

**World Health Organization (2025).** Chikungunya (14 April 2025), Zika virus (6 November 2025) and Yellow fever (20 October 2025), fact sheets. https://www.who.int/news-room/fact-sheets/detail/chikungunya, https://www.who.int/news-room/fact-sheets/detail/zika-virus, https://www.who.int/news-room/fact-sheets/detail/yellow-fever
Used for: the diseases Aedes aegypti can carry.

**World Health Organization (2017).** West Nile virus, fact sheet, 3 October 2017. https://www.who.int/news-room/fact-sheets/detail/west-nile-virus
Used for: Culex as the main vector; severe signs (high fever, neck stiffness, disorientation, weakness).

**World Health Organization (2024).** Lymphatic filariasis, fact sheet, 21 November 2024. https://www.who.int/news-room/fact-sheets/detail/lymphatic-filariasis
Used for: filariasis spread by Culex and Anopheles.

**Centers for Disease Control and Prevention (2019).** DPDx: Lymphatic filariasis. https://www.cdc.gov/dpdx/lymphaticfilariasis/index.html
Used for: Mansonia among the vectors of filariasis.

**Ministry of Health, Zambia, National Malaria Elimination Centre (2022).** National Malaria Elimination Strategic Plan 2022 to 2026. https://static1.squarespace.com/static/58d002f017bffcf99fe21889/t/632a4cb0fcd87c13d0165372/1663716530614/ZNMESP+2022+to+2026_SIGNED+120722.pdf
Used for: An. funestus s.s., An. gambiae s.s. and An. arabiensis as Zambia's primary malaria vectors, which sets the "main malaria carrier in Zambia" label.

**National Malaria Elimination Centre, Zambia (2017).** Guidelines for the Diagnosis and Treatment of Malaria in Zambia, 5th edition. (link under Clinical rules)
Used for: a rapid test for every fever before treatment; the severe malaria signs the conversation asks about (dark urine, yellow eyes, hard breathing, unusual bleeding).

**World Health Organization and UNICEF (1997).** IMCI in-service training, module 1: Assess and classify the sick child.
Used for: the four general danger signs in the conversation.

**Photos on the species cards.** CDC / James Gathany (An. arabiensis, An. gambiae; public domain); James Gathany, Frank Collins, CDC (An. funestus; CC0); Jens N. Lallensack (An. coustani; CC BY 4.0); Volkmar Becher (Culex pipiens; CC0); Graham Snodgrass, Army Medicine (Aedes aegypti; CC BY 2.0); Alex Abair (Mansonia titillans; CC BY 4.0). File pages are linked in `lib/pod/species.ts`.

## No source found: do not use

- "35% of primary clinics fully stocked" (plan A9): no primary source found.
- "Three in ten clinics out of malaria drugs" (plan A9): no current national source found. The closest primary figure is the 2006 four-district survey above (40% without AL on the survey day; about 30% of the year out of stock), which is a different measure.
- 100%, 65.8% and 68% availability (old video, plan A9): no source found.
- "4.3 million" roof count (plan A9): no source checked or found.
- A national or provincial figure for the share of rural facilities or households that lose road access in the rainy season: no primary source found.
- A current (after 2020) national share of facilities with stock-outs of artemether-lumefantrine or malaria rapid tests: no primary source found. A USAID report that is often quoted for this could not be opened (pdf.usaid.gov did not resolve).
