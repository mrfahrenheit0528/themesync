# MOS Instrument & Dataset Grounding: Verified Sources

Checked 2026-09-28 in response to the TSA's questions: (1) what backs Table 2's
Likert scale, (2) what the basis is for the 3 MOS parameters, and (3) who
evaluates. Also covers the missing CGL-Dataset V2 citation in Chapter 3 (p.46).

These are **working notes, not manuscript prose.** Nothing has been added to
the manuscript yet.

**How each source was verified:**
- ✔ **Primary text read.** I downloaded the paper/standard itself and
  quote it directly below.
- ◐ **Bibliographic details verified, content only from the abstract or a
  secondary summary.** Check the library copy (and page numbers) before
  quoting it in the manuscript.

---

## 1. Short answer

- **The 3 parameters are defensible as written; they just need citations.**
  Each one names a design principle that the layout-generation literature
  already uses as a quality criterion.
- **Table 2's structure comes from ITU-T P.800.** That is the standard
  that defines "Mean Opinion Score." It should replace the Twilio glossary
  page [18] as the MOS source.
- **"Who evaluates" is the weak point.** The manuscript specifies a
  single designated expert (p.54, p.57). Every source that would back the
  evaluation method uses **several** raters (see §4).

---

## 2. Basis for each MOS parameter

Each parameter has two layers of grounding. The **internal** layer is the
Chapter 3 component the parameter is the human check of. The **external**
layer is the literature naming it as a design-quality criterion.

### 2.1 Visual Hierarchy Preservation

**Internal counterpart:** hierarchy-based node sizing/placement (the
`hierarchy_index` in dynamic instantiation), plus the saliency-driven
dominance of the name/title.

**External sources:**
- ✔ **O'Donovan, Agarwala & Hertzmann (2014), §6 "Emphasis":** "Successful
  designs highlight important elements and lead the viewer's eye to key
  text or graphics. … Designers also often establish a desired hierarchy of
  importance for elements, with more important elements being visually
  emphasized." Their layout model turns this into an energy term, the same
  way ThemeSync's fitness function does.
- ◐ **Williams, *The Non-Designer's Design Book*,** principle of
  *Contrast*: make unequal elements clearly different so the important
  ones dominate. O'Donovan et al. cite this book (their ref. [37], 3rd ed.,
  2008) as a source of their principles.
- ◐ **Lupton & Phillips (2015), *Graphic Design: The New Basics*,** has a
  dedicated *Hierarchy* chapter (confirmed from the table of contents only).

### 2.2 Brand and Typographic Consistency

**Internal counterpart:** the Hybrid Visual DNA, i.e. the K-Means
palette, fonts and baseline sizes carried from the master layout. This
parameter asks whether they arrived "without hallucination."

**External sources:**
- ✔ **Wheeler (2013), *Designing Brand Identity*, 4th ed., p.29, brand
  ideal "Coherence":** "Whenever a customer experiences a brand, it must
  feel familiar and have the desired effect. Consistency does not need to
  be rigid or limiting in order to feel like one company."
  - Direct fit: ThemeSync exists to create *new* brand touchpoints (a
    certificate or ID) from an existing master layout. Whether those
    touchpoints still feel like the same brand is exactly what this
    parameter checks.
- ◐ **Williams, principle of *Repetition*:** repeat visual elements (fonts,
  colors, styles) throughout a piece to create unity. This is the
  typographic/color side of the same idea.

### 2.3 Constraint and Whitespace Harmony

**Internal counterpart:** the Overlap penalty (Formula 12) and the
Whitespace penalty (Formula 14). This parameter is the human check that
what those formulas score as "valid" also *looks* professionally composed.
Chapter 3, p.58, already frames the MOS this way.

**External sources:**
- ✔ **O'Donovan et al. (2014), §6 "White Space":** "White space in graphic
  designs is fundamental for readability and aesthetics."
- ✔ **O'Donovan et al. (2014), §6 "Overlap and Boundaries":** "We define
  several types of overlap, including overlap of elements on text, overlap
  of text on graphics, and overlap of graphics on other graphics. Users may
  also provide fixed binary masks, to prevent overlapping important
  regions such as faces or logos."
- ✔ **Zhou et al. (2022), CGL-GAN (the original CGL-Dataset paper), §5:**
  - Their designer user study judged layouts on items including "the
    visual balance of posters, and the overlap of elements."
  - Their metrics include overlap (R_ove), underlay overlap (R_und), a
    readability/visual-balance measure (R_com), and occlusion of key
    subjects (R_sub, R_shm).
  - Useful connection: Chapter 2 already cites R_shm via Xu et al. [2026]
    (ref. [36]). This parameter is the human-rated counterpart of those
    metrics, in the same line of work as the training dataset.
- ◐ **Williams, principle of *Proximity*:** grouping related items and
  separating unrelated ones, which is the compositional role of whitespace.

---

## 3. Basis for Table 2 (the 5-point scale)

- ✔ **ITU-T Recommendation P.800 (1996), Annex B, §B.4.5**, the
  listening-quality scale:

  | Label | Score |
  |---|---|
  | Excellent | 5 |
  | Good | 4 |
  | Fair | 3 |
  | Poor | 2 |
  | Bad | 1 |

  - P.800 defines MOS itself: "The quantity evaluated from the scores
    (mean listening-quality opinion score, or simply mean opinion score) is
    represented by the symbol MOS."
  - **Table 2 is this scale adapted to layout design.** It keeps the
    5-to-1 numbering and the Excellent/Good/Poor anchors, renames
    Fair → *Acceptable* and Bad → *Fail*, and adds design-specific
    descriptions. That is the honest way to describe it: *adapted from
    ITU-T P.800's Absolute Category Rating scale.*
  - Caveat: P.800 says scale wording "should follow the standard arrived
    at through years of experience." So the renamed labels are a
    deliberate domain adaptation, and Chapter 3 should say so.
- ✔ **Likert (1932), *Archives of Psychology* No. 140:** the origin of the
  5-point ordinal response format (Strongly approve … Strongly
  disapprove).
  - Precision point for the statistics-minded consultant: Likert's
    original is an *agreement* scale. Table 2 is a *quality-rating* scale.
  - Calling it a "5-point Likert-type rating scale" is common and
    acceptable. "5-point Absolute Category Rating scale (ITU-T P.800)" is
    more precise.
- **Averaging ordinal scores:** P.800 defines MOS *as* the arithmetic
  mean, so computing a mean is standard practice for this instrument.
  Reporting the SD alongside it (which `mos_collector.py --report` now
  does) answers the usual "Likert data is ordinal" objection.

---

## 4. Basis for the evaluator: a real gap

The manuscript specifies "the designated layout expert" (singular), a
"professional layout artist or graphic designer with documented industry
experience" (p.54, p.57). All the sources point to **several** raters:

- ◐ **Nielsen & Molich (1990), abstract:** individual evaluators "only
  found between 20 and 51% of the usability problems," but "evaluations
  from several evaluators could be aggregated … and such aggregates do
  rather well, even when they consist of only three to five people."
- ✔ **Zhou et al. (2022) CGL-GAN, and Li et al. (2023) RADM:** both papers
  behind the CGL-Dataset used **five professional and twenty novice
  designers** as raters, on 60 randomly selected test images.
- ✔ **ITU-T P.800 §B.4.4:** MOS subjects are "chosen at random from the
  normal telephone using population." Classic MOS uses panels of raters,
  not one person.

**Implication:**
- These sources support **3–5 expert evaluators**.
- Citing Nielsen & Molich to justify a *single* expert would contradict
  the source itself. The TSA or consultant could catch that.

**Recommendation (needs TA sign-off + a Chapter 3 revision):**
- Recruit 3–5 professional designers instead of 1, and cite Nielsen &
  Molich plus the CGL-GAN/RADM protocol for that choice.
- Report inter-rater agreement across them. Kendall's W or ICC are common
  choices; this is the consultant's area.

**Code status:** `mos_collector.py` already supports multiple evaluators
(`--evaluator "Name"` per session; the report counts unique evaluators).
Inter-rater agreement is **not** computed yet.

---

## 5. Dataset citation for Chapter 3 (p.46)

Chapter 3 names "CGL-Dataset V2, hosted on the Hugging Face repository"
with no citation. Verified:

- ✔ **CGL-Dataset V2** comes from **Li et al. (2023), RADM, CIKM '23**, which
  is the citation on the Hugging Face card
  `creative-graphic-design/CGL-Dataset-v2`.
  - The paper: "It is an extension of CGL-Dataset [Zhou et al. 2022]"
    that adds text-content annotations.
  - Contents: 60,548 training + 1,035 testing samples. "The original
    CGL-Dataset contains 4 types of elements: logos, texts, underlays and
    embellishments."
- ✔ **The original CGL-Dataset and its 4-class taxonomy** come from
  **Zhou et al. (2022), CGL-GAN, IJCAI-22**. The group's 124-image
  annotation batch reuses this taxonomy, so cite both.
- **Correction to what I said in chat on 2026-09-26:** the CGL-GAN paper's
  title ends "…for Visual-Textual Presentation Designs," not "…Content-aware
  Layout Generation."

---

## 6. Reference entries (formatted like the manuscript's reference lists)

```
Fengheng Li, An Liu, Wei Feng, Honghe Zhu, Yaoyu Li, Zheng Zhang, Jingjing Lv,
  Xin Zhu, Junjie Shen, Zhangang Lin, and Jingping Shao. 2023. Relation-aware
  diffusion model for controllable poster layout generation. In Proceedings of
  the 32nd ACM International Conference on Information and Knowledge
  Management (CIKM '23), 1249–1258. DOI: 10.1145/3583780.3615028.

Min Zhou, Chenchen Xu, Ye Ma, Tiezheng Ge, Yuning Jiang, and Weiwei Xu. 2022.
  Composition-aware graphic layout GAN for visual-textual presentation
  designs. In Proceedings of the Thirty-First International Joint Conference
  on Artificial Intelligence (IJCAI-22), 4995–5001.
  DOI: 10.24963/ijcai.2022/692.

Peter O'Donovan, Aseem Agarwala, and Aaron Hertzmann. 2014. Learning layouts
  for single-page graphic designs. IEEE Transactions on Visualization and
  Computer Graphics, 20, 8, 1200–1213. DOI: 10.1109/TVCG.2014.48.

International Telecommunication Union. 1996. Methods for subjective
  determination of transmission quality. ITU-T Recommendation P.800. ITU,
  Geneva.

Rensis Likert. 1932. A technique for the measurement of attitudes. Archives
  of Psychology, 22, 140, 1–55.

Jakob Nielsen and Rolf Molich. 1990. Heuristic evaluation of user
  interfaces. In Proceedings of the SIGCHI Conference on Human Factors in
  Computing Systems (CHI '90), 249–256. DOI: 10.1145/97243.97281.

Alina Wheeler. 2013. Designing Brand Identity: An Essential Guide for the
  Whole Branding Team (4th ed.). John Wiley & Sons, Hoboken, NJ.

Robin Williams. 2008. The Non-Designer's Design Book (3rd ed.). Peachpit
  Press, Berkeley, CA.            [◐ edition as cited by O'Donovan et al.;
                                     match to the copy you actually use]

Ellen Lupton and Jennifer Cole Phillips. 2015. Graphic Design: The New
  Basics (2nd ed., revised and expanded). Princeton Architectural Press,
  New York.                       [◐ catalog-verified only]
```

- Likert's page range varies across citing sources (1–55 vs. 5–55).
  1–55 is the most common.
- For Williams and Lupton, confirm the edition and page numbers against a
  physical/library copy before quoting.

---

## 7. Considered and dropped

- **Lidwell, Holden & Butler, *Universal Principles of Design*.** From the
  summaries I found, its "Hierarchy" entries are about information
  structure and a "hierarchy of needs," not visual focal-point hierarchy.
  That's a weak fit, and O'Donovan et al. covers it better.
- **Nielsen's "consistency and standards" heuristic (1994).** It is about
  UI-behavior consistency, not brand/visual identity. Wheeler fits better.
- **Twilio glossary [18] (Chapter 1).** It is not an academic source.
  Replace it with (or add) ITU-T P.800 as the MOS definition.
