# Manuscript Revision List: What to Fix and Add

Every place where the manuscript needs to change so it matches what was
actually built, or answers a grounding question. This is a **to-do list,
not draft prose.** Wording drafts get written only when asked for.

**Checked against `manuscript/Manu 0910.1.pdf` on 2026-10-09.** That is the
group's Prism revision, in the past tense; its LaTeX source is in
`manuscript/LaTeX/`.
- Page numbers are Manu 0910.1's printed page numbers, which equal its PDF
  page numbers. Versions of this list before 2026-10-09 used the May PDF's
  (`manuscript/Manu 1905.pdf`, formerly `Final Manuscript.pdf`).
- Old items keep their numbers. Items found on 2026-10-09 are M1–M27.
  M22–M26 come from the development chat's check
  (`notes/dev_findings_for_manuscript.md`, section A), confirmed against
  the code here.
- Make the fixes in Prism. `manuscript/LaTeX/` is an export, and edits there
  would be lost at the next one.
- **Paste-ready text: `manuscript/manu0910_fixes.md`** (2026-10-09). It has
  121 find-and-replace fixes covering M1, M2, M4–M16, M18–M25, M27 and
  parts of 3.9 and 3.22. All of them applied to the export compile without
  errors. Six placeholders need the group's facts. M3, M17 and M26 wait,
  as noted in that file.
- Write every addition in the past tense.

**Legend:**
- 🔴 **Must fix.** Wrong, contradicts the code, breaks the PDF, or a
  citation the TSA would catch.
- 🟡 **Should fix.**
- ⏸ **Blocked.** Waiting on the TA or the statistics consultant.
- ✔ **Applied** in Manu 0910.1.
- ✅ **No manuscript change needed** (fixed in the code).

**Source notes:**
- `mos_parameter_grounding.md`: verified citations and quotes (§6 has the
  reference entries).
- `gnn_fixes_and_methodology_notes.md`: code-side evidence (§ numbers
  below).
- `adviser_consultation_checklist.md`: the open decisions.

---

## Summary (2026-10-09)

- **Applied:** 26 of the 35 earlier items, most of them well. Some need a
  follow-up, listed as new items (the table's "Residue" column). The
  largest: 3.16 runs off the page (M1), 3.8's baseline (M4), 3.13's numbers
  (M6), 3.23's default (M5), and 3.26 is half applied (M7, M8).
- **Not applied:** 3.9 (waits on the consultant), 3.10–3.12 (wait on the
  TA), and the optional 3.7c, 3.17, 3.22. 3.24 and 3.25 needed no change.
- **New:** 27 items (M1–M27; M22–M26 from the development chat, all 🟡).
  The 🔴 ones:
  - two paragraphs run off the page (M1);
  - two paragraphs printed twice (M2);
  - a stress test described as done that doesn't exist (M3);
  - the Phase 4 baseline described as "GNN deactivated", when it also
    drops the master's structure (M4);
  - the no-master default (M5) and the GNN's held-out numbers (M6)
    misstated;
  - Appendix B and the "Implicit Geometric Hierarchy" passages
    contradicting the revised p.53–54 (M7, M8);
  - three reference entries the TSA asked about (CGL-GAN, RADM,
    O'Donovan) with the wrong authors and DOIs, and P.800 not cited in
    Chapter 3 (M9);
  - "will belong" inside Formula 3.10 (M10);
  - Chapter 2 saying, in the past tense, that ThemeSync computes Xu et
    al.'s R_shm (M27).

## Applied in `manuscript/Thesis Latex/` (uncommitted, for the user to review)

- **2026-10-09:**
  - every fix in `manuscript/manu0910_fixes.md` except the cover month,
    including the group's annotation facts and the 15-image expert review;
  - "et al." removed from the text and the Notes;
  - Chapter 4 restructured to the TSA's guidelines.
- **2026-10-10, after the development chat's D2, D3 and D7:**
  - **3.9 done:** Chapter 3 has a Statistical Treatment subsection, the
    plan adopted from the consultation guide (Q1–Q11), with method
    citations (Wilcoxon 1945, Kendall & Babington Smith 1939, Holm 1979,
    Kerby 2014, Cohen 1988, Shrout & Fleiss 1979, Krippendorff 2004,
    Schmidt 1997). Purposive sampling is now described, with Etikan, Musa &
    Alkassim 2016 (p.48 and the Phase 4 section).
    - Schmidt's 0.5/0.7 scale for Kendall's W was confirmed only through a
      secondary source. Check the full text if possible.
  - **M3 done:** p.55 now describes the stress test's design, and Chapter 4
    reports its results as found.
  - **M26 done:** p.62 now applies 0.1 s to the constraint recalculation and
    1.0 s to the state synchronization.
  - **M28 (new, done):** Chapter 3 claimed results the expert ratings
    contradict. They now describe the method instead:
    - Research Design: "to guarantee professional aesthetic compliance";
    - Phase 4: "to ensure industry-standard aesthetic compliance";
    - Evaluation Metrics: "ensured that the framework achieved … aesthetic
      validity";
    - Heuristic Fitness Function: "guaranteed that subjective aesthetic
      principles were translated";
    - MOS: "verified that these … bounds successfully translated into …
      aesthetically pleasing designs";
    - Optimization Theory: "successfully bridged the gap";
    - HCI Theory: "the system proved that … could successfully
      synthesize".
  - **Condition labels:** "structure mapping + GNN" and "baseline" in
    Chapters 3 and 4.
  - **Chapter 4:** the Phase 4 results and the Objective 3 discussion are in.
    Two facts are still pending: the server's GPU, and the certificate's
    paper size for the stress test.

---

## New items (2026-10-09)

### M1 🔴 Two paragraphs run off the page (p.46, p.55)

- **p.46** (pre-orchestration schema validation): the line ends "…its
  predefined maxcharacterslimit.If auserpayloadviolatesthesest" and the
  rest of the paragraph is lost.
- **p.55** (synthetic templates): the line ends "…spatialhierarchyweights,
  anddynamicallyresizetextelementswithoutviolatingpredef in" and the rest is
  lost.
- **Cause:** an unescaped `_` in `max_characters` (chapter3.tex l.188) and
  in `spatial_hierarchy` (l.367). LaTeX reads `_` as a subscript, switches
  to math mode, and sets the rest of the paragraph as one unbreakable
  formula.
- **Fix:** write `max\_characters` and `spatial\_hierarchy`, or
  `\texttt{max\_characters}`. Then check that the PDF shows the two lost
  sentences: "If a user payload violates these structural boundaries…" and
  "…without violating predefined bounding box limits or overwriting
  surrounding structural nodes."
- Prism compiled despite the error, so check its log for others.

### M2 🔴 Two paragraphs are printed twice (pp.43–44, pp.53–54)

- **State Synchronization (pp.43–44):** "The State Synchronization module
  will record every change…" appears twice. The first copy is the old one.
  It lacks a full stop before "No prior state" and after "defined in
  Formula 9". Keep the second (it has the terminal-event wording) and move
  over the first's "No prior state will ever be overwritten… restorable" if
  you want it.
- **Table 1 (pp.53–54):** "To guarantee deterministic execution and
  mathematical rigor… Table 1 demonstrated this precise correlation"
  appears twice. Keep the one just before Table 1.

### M3 🔴 The stress test is described as done, and it doesn't exist (p.55)

**Now:** "the synthetic dataset generated dynamic payloads containing
extreme spatial variables… This controlled injection validated the
solver's capacity to… dynamically resize text elements without violating
predefined bounding box limits…"

**Code:** no such test (notes §3.35, finding 1).
- The only long-text test checks that the schema rejects an over-long
  name.
- `Signature_Blocks` is fixed at `instantiation_count: 3`.

In the May PDF's future tense this was a plan. In the past tense it claims
a result.

**Fix, either:**
- run the stress test as an analysis: long strings up to each
  `max_characters`, and 1–6 signature blocks, checked with p.62's F1. It
  doesn't change the rated layouts, and it's also where F1 can drop below
  1.0; or
- reword p.55 to what was done.

### M4 🔴 The Phase 4 baseline also drops the master's structure (p.61; also p.64)

**Now:** "baseline outputs generated with identical content but with the
GNN module deactivated."

**Code:** the Phase 4 baseline is `use_gnn=False`, so `use_structure` is
off too (`pipeline.py` l.592–620; `phase4_packet.py` l.237).
- Its text elements form a naive reading-order stack: no GNN, and no
  mapping of the master's logo row, header, title or details either.
- Both conditions share the rest: the layout type from the master's
  composition (§3.31), the palette, the background, the motifs and the
  title artwork.
- The "mapping only" ablation runs only in the Phase 3 battery.

**Fix:** say that the baseline turns off the structure mapping and the GNN
together. **Chapter 4:** the MOS compares "structure mapping + GNN" with
"neither", so a difference can't be credited to the GNN alone. The GNN's
own gain is the held-out result (item 3.13).

### M5 🔴 The default layout type is misstated (p.58)

**Now:** the master's composition picks the archetype, "defaulting to a
classic centered structure in the absence of a master."

**Code** (`structure_mapping.archetype_for`, `pipeline.py` l.699 and l.715):
- Classic centred is chosen when there is a master and it shows none of
  the cues (left-aligned text, a large artwork to one side, a panel, a
  footer band).
- **Without a master,** no archetype is preferred, and the lowest C_total
  wins.

**Fix:** reword the sentence.

### M6 🔴 The GNN's held-out sentence credits the wrong thing and names the wrong measure (p.43)

**Now:** "On the held-out validation split, this structure-aware
initialization reduced overall position error to 0.036 (compared to 0.050
for the structure start alone), and when registered to exact anchors,
improved the placement of unmapped elements to a gap error of 0.075 versus
0.081 for standard linear interpolation."

**Problems** (notes §3.26, `results/gnn_heldout_eval.json`):
- **0.036 vs. 0.050:** 0.050 *is* the structure start. 0.036 is the GNN
  (v3) applied to it, so the GNN reduced the start's error, not the
  initialization.
- **0.075 vs. 0.081:** this is the unmapped elements' *vertical-centre
  (position) error* with exact anchors, not a gap error. v3's gap error is
  0.041 vs. 0.052.
- **"The held-out validation split" is never defined.** It is 2,900 CGL
  layouts, a seeded 5% of CGL-Dataset's training split (CGL's own test
  split has no annotations).

**Optionally add** what the GNN is trained to predict: designers' real
positions (Smooth-L1), the offsets between consecutive elements, and the
collision and in-bounds terms as regularisers (item 3.13's v2 notes).

### M7 🔴 Appendix B contradicts the revised p.53–54 (p.75)

**Now:** Student_Name = 1, Course_Title = 2, Signature_Blocks = 3.

**p.53–54 now says:** index 0 (logo row) to 8 (signatures) on the
certificate, in reading order.

**Fix:** replace Appendix B with the real `data/raw/academic_payload.json`
(9 variables: Institution_Logo 0, Issuing_Organization 1,
Certificate_Title 2, Presentation_Line 3, Student_Name 4, Citation_Body 5,
Date_Issued 6, Certificate_ID 7, Signature_Blocks 8). This is the second
half of item 3.26.

### M8 🔴 "Implicit Geometric Hierarchy" still says the GNN ranks elements by area (pp.10–11, pp.28–29, p.42)

**Now:**
- **Dictionary (p.10–11):** "the GNN infers spatial dominance by
  evaluating the mathematical area of a node's bounding box… Elements
  instantiated with larger geometric footprints are mathematically
  prioritized and positioned accordingly."
- **Initial Feature Encoding (p.42):** "Elements instantiated with a larger
  spatial footprint are mathematically assigned a higher relational weight
  by the GNN, ensuring they are positioned precisely at the top of the
  structural hierarchy."
- **Gap (pp.28–29):** variables "are mathematically prioritized based on their
  assigned geometric baseline tensors".

**The revised p.53–54 (item 3.26) says otherwise**, and matches the code:
- the index sets each element's role and reading order;
- each role has a fixed baseline size.

**Code:**
- The GNN takes each box's position and size as features, but nothing in
  it weights by area.
- The order comes from the index. The certificate's name is index 4 and
  has the third-largest box.

**Fix:** bring the three passages in line with p.53–54. Size marks
emphasis; the index sets order.

### M9 🔴 Three reference entries the TSA asked about don't match their sources; P.800 isn't cited in Chapter 3

Verified entries are in `mos_parameter_grounding.md` §6.

| bib key | In the manuscript | Verified |
|---|---|---|
| `zhou2022cglgan` (CGL-GAN) | Zhou, Xu, Ge, **Wei**, Xu; pp. 4064–4070; DOI 10.24963/ijcai.2022/**564** | Min Zhou, Chenchen Xu, **Ye Ma**, Tiezheng Ge, **Yuning Jiang**, Weiwei Xu; IJCAI-22, 4995–5001; DOI 10.24963/ijcai.2022/**692** |
| `li2023radm` (CGL-Dataset V2) | **Zhaoyun Li, Jialu Chen, Biao Yi, Zhibin Liu, Min Shen, Wei Wang**; "RADM: a relation-aware diffusion model for graphic layout generation"; 1308–1317; DOI …/3583780.**3615017** | **Fengheng Li, An Liu, Wei Feng, Honghe Zhu, Yaoyu Li, Zheng Zhang, Jingjing Lv, Xin Zhu, Junjie Shen, Zhangang Lin, Jingping Shao**; "Relation-aware diffusion model for controllable poster layout generation"; CIKM '23, 1249–1258; DOI 10.1145/3583780.**3615028** |
| `ODonovan2014Layouts` | "Learning design inspiration from layouts", ACM TOG 33(4), DOI 10.1145/2601097.2601153 | "Learning layouts for single-page graphic designs", IEEE TVCG 20(8), 1200–1213, DOI 10.1109/TVCG.2014.48. Its energy terms ("Emphasis", "White Space", "Overlap and Boundaries") are the ones the MOS parameters cite. |

- **In-text names follow the bib.** Fix them where they appear:
  - "Zhou, Xu, Ge, Wei, and Xu [2022]": pp.24, 49, 50, 61;
  - "Li, Chen, Yi, Liu, Shen, and Wang [2023]": pp.49, 61.

  "Zhou et al. [2022]" and "Li et al. [2023]" are shorter, if the
  citation style allows.
- **P.800 (p.65):** "This rubric was adapted from the standard ITU-T P.800
  Absolute Category Rating scale" has no citation. Each chapter's Notes
  are separate, so add `\cite{itut1996p800}` there (Chapter 1 cites it as
  [9]).

### M10 🔴 The past-tense conversion reached Formula 3.10 (p.45)

**Now:** "c_i = Hard, if e_i **will belong** to U_manual; c_i = Soft, if
e_i **will belong** to A_algorithmic".

**Fix:** use set membership: `e_i \in U_{manual}`, `e_i \in A_{algorithmic}`.
The explanation below it ("will be labeled… will not change… will be
permitted") is still in the future tense too (M11).

### M11 🟡 Future tense left where the past was meant

- **Scope (p.8):** "the study will integrate a mixed-methods evaluation
  strategy… will subsequently be evaluated by a panel of four… This
  approach will guarantee…".
- **Dictionary (p.11–12):** "MOS will refer", "Visual DNA will refer".
- **Chapter 2, where it describes ThemeSync:**
  - p.18–19: "the proposed methodology will pipeline… will effectively
    unflatten";
  - p.23: "the orchestration layer will operate… will decouple… will only
    harden… will mathematically guarantee";
  - p.24–25: "will integrate dynamic saliency evaluations… will
    algorithmically quantify… will mathematically evaluate… will ensure".
- **Chapter 3:**
  - GNN (pp.41–43): "will be designed… will be modeled… will function…
    will process… 0 will mean no alignment and 1 will mean perfect
    alignment";
  - State Synchronization and Formula 3.10 (pp.43–45);
  - Validation of Hybrid Visual DNA (pp.45–46), which mixes tenses inside
    one paragraph ("will be strictly enforced… verified… will
    programmatically reject").
- **Over-converted:** "O'Donovan, Agarwala, and Hertzmann [2014], who
  demonstrated that graphic layout quality will be mathematically modeled"
  (p.24) should be "could be".
- **Group's call:** Significance (pp.6–7, "This study will benefit…") and
  the objectives ("aims") are often left as they are. Ask the TA if
  unsure.

### M12 🟡 Typos and garbled sentences

- **p.49:** "the CGL-Dataset V2, which extends the foundational layout
  benchmark introduced by introduced by Li… [2023], which extended the
  foundational benchmark established by Zhou… [2022]". This says V2
  extends a benchmark *by* Li et al. In fact Li et al. introduced V2,
  which extends Zhou et al.'s CGL-Dataset. The trailing `\cite` after the
  full stop then repeats both.
- **p.50, heading:** "Emperical" should be "Empirical".
- **Dictionary:**
  - "Fitness function. Fitness Function." (p.10) and "Object
    Serialization.Object Serialization." (p.11) repeat the term;
  - "[8, 11] this study" (p.10) is missing "In".
- **p.18:** "Wang, Xu, Cui, and Wei [2023] extraction by explicitly
  modeling…" is missing a verb.
- **Missing full stops:** p.43 (M2) and p.54 ("regardless of their
  sequential placement A sample…").
- **Small slips:**
  - p.25: "generative Al models" (a lowercase L);
  - p.27: "largely predominantly";
  - p.21: "[2020]established" and p.25: "[2023]emphasized" (no space);
  - p.22: "[ 2020]";
  - p.49 and p.54: "Annex Appendix A/B".

### M13 🟡 Formula references are inconsistent (pp.39–63)

- The equations are numbered (3.1)–(3.15).
- The text says "Formula 1", "Formula 2"… (pp.39–48), "Formula 3.1"
  (p.45), "Formula 11" (pp.46, 63), and twice "Equation 3" for (3.11)
  (p.46 and p.60's Evaluation Report paragraph).
- **Fix:** `\label` each equation and refer with `\ref`, as "Formula 3.11".

### M14 🟡 Chapter 2 citations that print without their authors

The author-year style needs the names typed before `\citeyear`. These
lack them:
- p.18: "[2025]", for dos Santos Júnior, Paixão, and Alvarez;
- p.23: "[2025, 2020, 2022]";
- p.20: "Kravtsov, and [2025]", missing Artemchuk;
- p.24–25: "Xu, Chenchen and Zhou, Min and Ge, Tiezheng and Xu, Weiwei
  [2026]", the raw BibTeX author field. Write "Xu, Zhou, Ge, and Xu
  [2026]".

### M15 🟡 Other reference problems (check each on its DOI or arXiv page)

**The cause of Chapter 2's wrong years:** three `\citeyear{…}` calls point
at the wrong bib key. "Lee, Jin, and Tseng [\citeyear{Garcia2023}]" prints
Garcia's 2023, Graph4GUI's `\citeyear{Du2020DepthLab}` prints 2020, and
Zheng et al.'s `\citeyear{Xu2020LayoutLM}` prints 2020. Because the NDN entry
was never cited, NDN is also missing from the Notes.

**Checked on the web, 2026-10-09:**
- **Confirmed:** Graph4GUI's, LayoutFormer++'s and NDN's authors;
  Kleppmann's title; Badros et al. (Cassowary, DOI
  10.1145/504704.504705); LayoutDiffusion (ICCV 2023, 7226–7236).
- **Couldn't find:** the packaging-design paper (DOI
  10.1038/s41598-025-20046-1) and the LLM constraint-model paper (DOI
  10.3390/app15126518). If those DOIs don't open, the sources have to be
  replaced, not just corrected.

**Wrong authors or titles:**
- **Graph4GUI (`Jiang2024Graph4GUI`):** the authors are Yue Jiang,
  Changkong Zhou, Vikas Garg and Antti Oulasvirta (CHI '24, arXiv
  2404.13521), not Jiang, Stuerzlinger and Richter. p.17 also says "[2020]"
  right after "By 2024". The entry's "Retrieved 2, 2026" lacks a month.
- **LayoutFormer++ (`Jiang2023LayoutFormer`):** Zhaoyun Jiang, Jiaqi Guo,
  Shizhao Sun, et al. (CVPR 2023), not Yue Jiang, Zejian Guo and Ming Sun.
- **Kleppmann 2022 (`Kleppmann2022CRDT`):** the URL is "Making CRDTs
  Byzantine Fault Tolerant", PaPoC '22, DOI 10.1145/3517209.3524042. The
  entry's title and venue don't match it.
- **`zhang2025intelligent` [Ch2 39]:** the authors are LayoutDiffusion's
  (Zhang, Guo, Sun, Lou, Zhang; ICCV 2023), but the title and venue are an
  IEEE Access interior-design paper. p.28 cites it for "diffusion-based
  layout models", so LayoutDiffusion is probably the one meant.
- **Neural Design Network:** "Lee, Jin, and Tseng [2023]" (p.17) is typed
  by hand, so it's missing from the Notes. NDN is ECCV 2020; check the
  author list against the paper.

**One paper, two entries:**
- **ORCSolver:** Ch1 [10] (2021, no Zwicker, DOI
  10.1145/3411764.3445551) vs. Ch2 [16] / Ch3 [5] (CHI '20, with Zwicker,
  DOI 10.1145/3313831.3376610). The second is right; drop the first.
- **Same DOI, different authors:**
  - 10.1038/s41598-025-20046-1 (packaging design): Ch1 [7] "Xiaocen Guo,
    Sijia Fu, Di Zhu" vs. Ch2 [10] "Xiao Guo, Wei Zhao, Lei Zhang";
  - 10.3390/app15126518 (LLM constraint models): Ch1 [15] and Ch3 [18]
    "Roberto Penco, Damir Pintar, Mihaela Vranić" vs. Ch2 [27] "Ratko
    Penko, Domagoj Penko, Marko Varga".

  At most one of each is right. Keep one bib key per paper.

**Cited for something they don't say:**
- **Cassowary is never cited to its own paper:**
  - the Ch1 definition (p.9) cites the LLM constraint-model paper (its bib
    key is `Cassowary2024`);
  - p.27 cites ORCSolver for "the incremental Cassowary constraint-solving
    algorithm";
  - p.40 cites ORCSolver and SMT-Layout.

  Add Badros, Borning & Stuckey (2001), "The Cassowary linear arithmetic
  constraint solving algorithm", ACM TOCHI 8(4), 267–306.
- **AAPA:** credited to Shi et al.'s survey (p.25; p.27's [33]). The term
  comes from Patnaik et al. 2025, AesthetiQ (Ch2 [26]), as p.29 already
  has it.
- **Mismatched numbers in Chapter 2:**
  - p.27: "state machines for decentralized synchronization [22, 37, 26]".
    37 is Xu et al.'s layout GAN and 26 is AesthetiQ
    (`\cite{Liang2020Bidirectional,Xuetal2026, Patnaik2025AesthetiQ}`).
  - p.24: "[40]" (Zhang et al., CSP scalability) for "AI-driven aesthetic
    scores to guide evolutionary strategies".
  - p.24: Zheng et al. "[2020]"; the entry is 2025.
- **Mismatched numbers in Chapter 3's Theoretical Framework (p.67):**
  - palette mapping → [7], Kosarev (UI layout synthesis);
  - "adaptive OR-constraints" → [2], Chen (gestalt persistent homology),
    where ORCSolver is [5];
  - "scalable constraint generation models" → [4, 14], LayoutFormer++ and
    a human-in-the-loop survey.
- **Ch1 Soft Constraints (p.12):** cites [11] (Graph4GUI) but names
  "Jiang, Stuerzlinger, and Lutteroth (2021)", i.e. ORCSolver.

**Formatting:**
- **Lowe 2009 (`Lowe2009`):** the DOI "10.10.1145/2008" is malformed.
  Lowe 2004, "Distinctive image features from scale-invariant keypoints",
  IJCV 60(2), 91–110, is the usual SIFT citation.
- **Wu et al. 2022 GNN book (`Wu2022GNN`):** its DOI
  10.1145/3580305.3599560 belongs to a KDD '23 paper, not the Springer
  book.
- **Ch1 [7]:** "DOI: DOI:".

### M16 🟡 The new dataset subsection: four wording fixes (pp.50–51)

Item 3.2 is in, and it reads well. Four fixes:
- **"preventing ambiguous background container boundaries from
  destabilizing anchor regression":** YOLOv8 is anchor-free. Say "from
  being learned as elements" (§3.30's reason).
- **"This dedicated dataset guaranteed that the perceptual parsing stage
  extracted structural bounding boxes with high confidence":** too strong.
  v5's mAP50 is 0.728, and underlay and embellishment recall is about 0.5.
  Say "improved".
- **"distributed across independent annotators and subjected to
  systematic cross-validation audits":** "cross-validation" means k-fold
  in ML. Say who annotated and how the boxes were cross-checked, and keep
  it to what was done.
- **"an independent domain expert validated a representative 15-image
  stratified sample… prior to model training":** confirm three things.
  - The review came back, and what it found. The checklist (D2) still
    says "update this line once the review comes back".
  - The sample came from the 124-image batch (sent 2026-09-26), before
    the 200-image re-annotation that trained v5.
  - It was stratified. Nothing in the notes records that.

Also, "generalized document layout models" (p.50): CGL-Dataset is
e-commerce posters, not documents.

### M17 🟡 Figures 2 and 3 and their descriptions show the May mockups (pp.56–57, pp.59–60)

- **The figures:** `ts1–ts3.png` are still the Christmas-poster mockups
  (item 3.17).
- **The text:**
  - p.56–57: "the central viewport… the right-hand panel";
  - p.59–60: two tabs on the right, the State Timeline "below" the
    Constraint Editor.
- **The dashboard has changed at the user's request:**
  - Step 1, mockups A1–A3 (notes §3.36–3.37): the master layout on the
    left, the Visual DNA cards on the right, and Target Initialization as
    an overlay;
  - Step 2 (§3.38): the canvas in the centre, the Recommendation Engine
    as thumbnails beneath it, the selected element on the right, and the
    Timeline as a dialog.
- **Decide:**
  - keep the mockups as the design and say so; or
  - once the dashboard settles, replace them with screenshots (CSPC
    poster) and update two or three sentences in each description.

  The working rule (the manuscript is the basis; change it where the
  system got better) favours the second.

### M18 🟡 Smaller accuracy slips

- **p.57:** "The final procedural phase" for Phase 3. Phase 4 follows.
- **p.8 and p.61:** IoU is said to measure "spatial prediction accuracy".
  p.62 confines it to detection (YOLO on the validation split).
- **p.60:**
  - The experts "interacted with the ThemeSync outputs". They rated printed
    pages, as p.61 says.
  - "[16, 10, 24], which demonstrated that aggregating feedback from a
    minimum of three to five experts is required…" overstates the sources.
    Nielsen & Molich found that single evaluators catch 20–51% of
    problems, and that aggregates of three to five "do rather well". The
    CGL papers used five professional and twenty novice designers on 60
    images; they didn't test a minimum.
- **p.47 (Formula 3.13):**
  - "left edge, vertical center, or right edge": the code uses the
    element's horizontal centre (x + w/2) against vertical gridlines, so
    "centre" alone is clearer.
  - The formula's text says "(x_i or y_i)", but only x is scored (see
    M20).
- **p.48:** "exclusively presents layout candidates that approach the
  optimal F_layout minimum". The Recommendation Engine shows every
  candidate, and the output follows the master's layout type (p.58).
- **p.53:** "Identification Cards and Academic Certificates": make it
  "event identification cards", like p.55 and p.61 (item 3.7b).
- **p.58:** "$C_{total}$" is the code's name for the fitness score; Formula
  3.11 calls it $F_{layout}$. Use one name.

### M19 🟡 R_target is fixed, not taken from the master (p.47, Formula 3.14)

**Now:** the target whitespace ratio is "established by the master
template's visual DNA".

**Code:** 0.65 for every master (`optimization_engine.py` l.16). See notes
§3.35, finding 2.

**Fix:** the deployed value can't change, because the experts rated its
output. Either reword p.47, or test a master-derived R_target as an
analysis (how many of the 64 outputs would change), as §3.33 did for the
weights.

### M20 🟡 Normalisations the formulas don't show (pp.47–48, Formulas 3.12, 3.13, 3.15)

Notes §3.35, finding 3:
- **3.12:** the overlap is divided by the canvas area.
- **3.13:** distances are taken in x only, divided by the canvas width,
  and averaged over the nodes. Signature rows and motifs are skipped.
- **3.15:** the saliency is averaged inside each text box, and then over
  the text nodes, not summed. The docstring of
  `calculate_legibility_penalty` gives the reason.

**Fix:** a sentence, or the normalising terms in the formulas.

### M21 🟡 Front matter

- The cover still says "May 2026" (`\makeTitlePage{May}{2026}`).
- `\approvaldate{January 1, 2000}` and the abstract are template
  placeholders. They're commented out of this build.

### M22 🟡 "Incrementally" overstates how Cassowary is used (p.40)

**Now:** "The solver uses a dual-simplex method to maintain these
relationships established in Formula 3 incrementally, allowing the layout
to re-calculate in milliseconds whenever a single variable… is adjusted."

**Code:** every solve builds a new solver (`cassowary_engine.py` l.47,
`kiwi.Solver()`; `pipeline.solver_for`) and solves the whole layout. One
re-solve takes about 0.4 ms (notes §3.32).

**Fix:** e.g. "re-solved the whole layout on every terminal event, in
under a millisecond". Cassowary is still the algorithm (kiwisolver
implements it). Its citation is M15.

### M23 🟡 Table 1 reuses symbols that already mean something else (p.54)

- **Typography:** `administrative_typography (font_family, weight)` is
  mapped to **S_i**. But s_i is the SIFT descriptor in Formula 3.6, and S_i
  is a K-Means cluster in Formula 3.1.
- **Saliency:** `extracted_saliency_weight` → **p_i(legibility)**, while
  Formula 3.15 writes the saliency as S(p) and the penalty as
  P_legibility.
- **Also in Table 1's source:** `\texttt{extracted\_ color\_centroids}`,
  `extracted\_ saliency…` and `spatial\_ hierarchy` print a stray space
  after the underscore.

**Fix:** distinct symbols, e.g. T for typography, and the formulas' own
symbols for saliency.

### M24 🟡 Figure 2's description names two things the panel doesn't show (pp.56–57)

This adds to M17, which covers the arrangement.

- **"the structural hierarchy parsed by the GNN":** the node graph on
  Step 1 (the ⓘ dialog) is Stage 0b's parse, by YOLOv8 + Tesseract. The
  GNN runs only at Initialize.
- **"boolean feature detection via SIFT/SURF":** the SIFT card shows the
  saliency weight, "Logo: Yes/No" and the image size. Only the logo flag
  is boolean, and it comes from YOLO's logo class.

**Fix:** "the elements parsed by the layout detector"; "SIFT keypoint
saliency and whether a logo was detected".

### M25 🟡 OCR isn't what fills the nodes with words (p.56)

**Now:** Tesseract OCR for text extraction, "converting the flattened
raster pixels into structured, editable nodes".

**Code:** the OCR text labels the parsed nodes in the node graph
(`layout_extractor.py` l.132; `views/ingestion.py` l.105). The layout's
words come from the user's validated content payload. That is also what
p.46's argument against OCR "typographic hallucinations" supports.

**Fix (optional):** "OCR labelled the parsed text nodes; their content
came from the validated payload."

### M26 🟡 Which latency meets which limit (p.62)

Item 3.29 is applied: the 0.1 s and 1.0 s thresholds are cited. The
measurements so far fall on either side of the first one:
- **one Cassowary re-solve:** about 0.4 ms, within 0.1 s;
- **one whole canvas edit** (re-solve, re-score, re-render, save the
  state chain): about 160 ms, over 0.1 s but within 1.0 s (notes §3.32).

**Fix:** once the development chat's benchmark is in ("Code before
Chapter 4"), say that the solver meets 0.1 s and a full edit meets 1.0 s,
or that both meet 0.1 s if the development chat gets the edit under it.
Don't add numbers before then.

### M27 🔴 Chapter 2 says ThemeSync computes R_shm (pp.24–25)

**Now:** "the framework will algorithmically quantify layout occlusion by
computing the perceptual difference in the background's saliency map
before and after the application of text masks. By establishing a rigid
spatial clash metric ($R_{shm}$), the system will mathematically evaluate
the aesthetic score…". Converted to the past tense, this claims a result.

**Code:** no R_shm. The Legibility Penalty (Formula 3.15) measures the mean
saliency under each text box, on each candidate's own composed background
(`optimization_engine.calculate_legibility_penalty`).

**Fix:** credit R_shm to Xu et al. and say what ThemeSync measures (fix #24
in `manuscript/manu0910_fixes.md`). Found while drafting the fixes.

---

## Earlier items: status in Manu 0910.1

### Applied ✔

| Item | Where | Residue |
|---|---|---|
| 1.1 MOS cites ITU-T P.800 | p.11, Ch1 [9] | — |
| 1.2 MOS names Chapter 3's three parameters | p.11 | — |
| 1.3 Experts plural | p.8, p.11 | — |
| 2.1 O'Donovan and CGL-GAN in the RRL | p.24 | entries wrong (M9) |
| 3.1 CGL-Dataset V2 cited, with its figures | p.49 | garbled sentence (M12); entries wrong (M9) |
| 3.2 The 200-image master-layout dataset | pp.50–51 | M16 |
| 3.3 What the detector is trained on | pp.55–56 | — |
| 3.4 IoU on the 40-image validation split (text) | p.62 | **the script still doesn't exist** (see "Code before Chapter 4") |
| 3.5 MOS parameters cited | p.64 | O'Donovan entry (M9) |
| 3.6 Table 2 from P.800, Likert cited, "Likert-type" | pp.64–65 | P.800 not cited in Ch3 (M9) |
| 3.7 Four experts, Nielsen & Molich, CGL protocol | pp.60–61 | wording (M18); inter-rater agreement waits on 3.9 |
| 3.7b Event identification cards | pp.55, 61 | p.53 (M18) |
| 3.8 Phase 4 design: 16 × 2 × 2 = 64, blind baseline, packets | pp.60–61 | baseline (M4) |
| 3.13 What the GNN is trained on (v3) | p.43 | M6 |
| 3.14 Background layer, motifs, title artwork | pp.39–40, p.58 | — |
| 3.15 The four parameters the candidates vary | p.58 | — |
| 3.16 Schema rules | p.46 | runs off the page (M1) |
| 3.18 Phase 3 on synthetic templates and real posters | p.57 | — |
| 3.19 Role mapping, interpolation, registration | p.53 | — |
| 3.20 Formulas 3.13–3.14's reference area | p.47 | M18, M20 |
| 3.21 Text edits; undo/redo append | p.44 | — |
| 3.23 The master's composition picks the layout type | p.58, p.60 | no-master default (M5) |
| 3.26 Spatial Hierarchy Index as reading order (text) | pp.53–54 | Appendix B (M7); other passages (M8) |
| 3.27 "Four phases", "five theories" | p.55, p.66 | — |
| 3.28 Step 3, the Evaluation Report | p.60 | "Equation 3" (M13) |
| 3.29 0.1 s / 1 s thresholds, Nielsen 1993 | p.62 | — |

### No manuscript change needed ✅

- **3.24 F1 per element:** fixed in the code (notes §3.32). Chapter 4
  should say that F1 counts collisions and out-of-canvas elements per
  element.
- **3.25 Weight calibration:** done (notes §3.33). p.46 and p.58 stand.
  Chapter 4 reports it, and says it ran after the Phase 4 layouts were
  generated.

### Not applied

#### 3.9 ⏸ Statistical Treatment (pp.48, 61–65): waits on the consultant's answers

**Now:**
- p.48 still promises "the targeted sampling techniques" and "the precise
  statistical tools… to quantitatively measure… user interaction
  efficacy".
- p.48 also mentions a "human-in-the-loop usability validation", which
  the study doesn't have. Phase 4 rates aesthetics.

No Statistical Treatment section exists.

**Add once the consultant answers** (the 2026-10-09 consultation's answer
sheet):
- MOS: the mean and SD per parameter and overall (P.800 defines MOS as the
  mean);
- inter-rater agreement across the four experts;
- the GNN-vs-baseline MOS comparison, paired by poster and format (and
  with or without ANTI_HAZING_LAW, notes §3.35);
- the Phase 3 fitness comparison;
- the mean IoU (item 3.4).

Don't pick the tests before the answers arrive. Reword p.48's "user
interaction efficacy" and "usability validation" at the same time.

#### 3.10 ⏸ SIFT **and** SURF vs. SIFT only (p.11–12, p.39–40, p.55, and wherever "SIFT/SURF" appears)

- **Code:** only SIFT is invoked. SURF is patent-encumbered and absent from
  standard OpenCV builds.
- **Blocked on the TA** (checklist C): reword to "SIFT", or add SURF to the
  code.
- Manu 0910.1 still says SIFT/SURF throughout.

#### 3.11 ⏸ CNN aesthetic evaluator (p.38, "Theorems, Algorithms…")

- **Now:** "Convolutional Neural Networks (CNN) deployed for quantitative
  aesthetic evaluation."
- **Code:** `aesthetic_cnn.py` is trained by distillation from the fitness
  function (no human labels yet), and isn't wired into ranking.
- **Blocked on the TA** (checklist B): describe the distillation, or make
  retraining on the MOS future work.

#### 3.12 ⏸ Appendix A's per-node features vs. the GNN training pipeline (p.74)

- **Now:** each node has its own `node_id`, colour centroids, saliency
  weight and `text_features`.
- **Code:** training broadcasts one global colour and one global saliency
  value into every node. There is no `node_id`, and `text_features` is
  dropped (§3.10, finding 3).
- **Blocked on the TA** (checklist B): fix the code, or revise Appendix A
  and report it as a limitation.

#### Optional, not applied

- **3.7c:** name the vertical-balance rule among the soft constraints
  (p.41).
- **3.17:** screenshots for Figures 2 and 3 (now part of M17).
- **3.22:** seeded K-Means initialisation, best of five per k (p.39).

---

## Code before Chapter 4

The development chat is building these, in this order, and will report
the numbers (`notes/dev_findings_for_manuscript.md`, section B). Their
manuscript passages stay as written until then. None of them changes the
rated layouts.
- **Mean IoU (item 3.4):** p.62 now commits to it, and no script exists.
  It would run v5 on the 40 validation images, pair each predicted box
  with the ground-truth box of the same class, and average
  overlap ÷ union per class and overall.
- **Stress test (M3):** p.55 keeps the claim. The manuscript is the basis,
  so the development chat builds the test, and p.55 is then worded to
  match what it ran.
- **Latency benchmark (M26):** solver and full-edit timings over many
  edits, against 0.1 s and 1.0 s.
- **The GNN–solver "Mean IoU"** (notes §3.35, finding 4):
  - `evaluate.py` and `experiment_runner.py` report an IoU between the
    GNN's output and the final layout, which p.62 rules out.
  - Rename it (e.g. "GNN–solver overlap") or drop it from the notebook.
- **F1 over the rated set** (notes §3.35, finding 5):
  - Add `layout_report.structural_accuracy` to `experiment_runner.py`, so
    F1 1.0 on all 64 rated layouts is in the results files.
- **The K-Means elbow chart** (p.60's Evaluation Report): Step 3 shows a
  WCSS table per k today. The development chat adds the chart, so p.60
  stands.

---

## Chapter 4: Results

**Drafted 2026-10-09: `manuscript/chapter4_draft.tex`** (user's request). It
is organized by the three specific objectives, and every number comes from
a file in `results/`, named in a comment beside it. It compiles in the
template with no errors (about 17 pages).
- **Still `\pending{}`:** the Phase 4 MOS tables and text, inter-rater
  agreement, and the GNN-vs-baseline test (the experts' scores and the
  consultant's answers); the server's GPU; the certificate's paper size;
  and whether ANTI_HAZING_LAW is also analysed separately.
- **The IoU, stress test, latency and rated-layout check** come from the
  development chat's Windows runs (notes §3.41–3.44). CLAUDE.md treats the
  server as the source of results of record, so the group should decide
  whether to re-run them there.
- **No figures yet.** Sample outputs could be added after the scores are
  in, and the Step 3 report and its elbow chart once the dashboard
  settles.

The findings below were the inputs. Where the draft and this list differ,
the draft's numbers, re-read from `results/`, are the current ones.

Not revisions, but the findings Chapter 4 will need, so nothing gets lost:

- **YOLO domain gap and closing it:**
  - v1, CGL only: mAP50 0.539 in-domain, but near-zero confidence on real
    posters.
  - v2 (65 images): mAP50 0.325.
  - v3 (124 images): mAP50 0.370; logo 0.620, text 0.595.
  - **v4 (deployed):** YOLOv8s from COCO at 1024 px, the over-half boxes
    removed. On the same cleaned validation labels as v3:
    - mAP50 0.454 vs. 0.363;
    - logo 0.818 (recall 0.76 vs. 0.55);
    - text 0.682.
  - Embellishment didn't move (recall 0.18). That's a label-definition
    problem; the group is re-annotating with a new `illustration` class
    (notes §3.25), and v5 comes after.
  - The automatic logo row is right on **15 of 15** unseen posters (7 of 15
    before).
  - **v5 (deployed 2026-10-06, notes §3.30):** the group's 200-image
    re-annotation, same recipe. On 32 validation images neither model
    trained on, mAP50 0.728 vs. v4's 0.486; embellishment 0.609 vs. 0.263;
    underlay 0.643 vs. 0.138. The dataset is now **200** images
    (160 train / 40 validation); item 3.2 is updated.
  - **Mean IoU** on the 40 validation images: not computed yet (item 3.4).
- **Fitness weight calibration (item 3.25, notes §3.33):** the deployed
  weights are confirmed; halving or doubling any weight changes at most 1
  of the 64 rated layouts. No candidate ever overlapped, so α's value never
  decided; the choices come down to whitespace against legibility.
- **Data-quality catch:** a mixed-format export would have silently
  dropped about 23% of images (§3.12).
- **GNN v1 → v2 (notes §3.22):** the first GNN predicted from inputs it
  never saw in training; on 2,900 held-out CGL layouts it was worse than no
  model (order kept 47%, i.e. chance). v2 cuts position error 43% and gap
  error 79% against v1. The table is in `results/gnn_heldout_eval.json`.
- **GNN v3, the master's structure as input (notes §3.26):**
  - **Held-out:** v3 cuts the structure start's position error 28% (0.036
    vs. 0.050) and its overlap 89%; v2 makes it worse (0.096).
  - **With exact anchors:**
    - raw v3 moves them by 2.6% of the height;
    - registered to them, it keeps them and places the unmapped elements
      8% better than interpolation (0.075 vs. 0.081);
    - v2 registered is worse than interpolation.
  - That's the case for registration, and for training on structure
    starts.
- **Phase 3 battery, three Stage 2 conditions (notes §3.26, §3.30,
  `results/experiment_log.json`, run 20261006_195534: YOLO v5, the 16 new
  Phase 4 posters, layout type from the master, item 3.23):**
  - **Structure transfer works.** The output is closer to the master than
    the baseline:
    - event IDs: on 15 of 16 (structure error 0.045 vs. 0.117);
    - certificates: on 14 of 16 (0.056 vs. 0.089); the other two have no
      roles to map.
  - **Formula 3.11 doesn't reward it.**
    - Certificates mostly tie (equal on 10 of 16).
    - On IDs the baseline scores slightly better (0.1583 vs. 0.1633),
      through legibility: text goes where the poster had artwork.
    - Worth stating as a limitation of the fitness function. Phase 4's MOS
      (hierarchy, brand consistency) is where this is judged.
  - **GNN vs. mapping only:** the same anchors. The GNN moves the unmapped
    elements on 14 of 32 runs, by ≤ 7.5% of the height. The formats' tall
    stacks leave the solver's design rules little slack, so report the
    GNN's gain from the held-out test, not from the fitness.
  - The 2026-09-29 run (YOLO v4, the earlier 15 posters) showed the same
    pattern. The older 2-condition numbers (1.2029 vs. 1.1876) are
    obsolete.
- **Manual refinements are retained:** simulated moves, resizes and locks
  are kept exactly through re-solves, with no overlap (F1 1.0, `evaluate.py`,
  `test_hard_constraints_preserved`).
- **Stage 0b's automatic logo pick on unseen posters:** right on 7 of 15,
  incomplete on 6, wrong object on 1, nothing on 1 with v3 (notes §3.21).
  With v4 and the row-clustering rule it is right on 15 of 15 (§3.25). The
  dashboard's pickers remain the human-in-the-loop fix.
- **AAPA diversity:** candidates now differ in layout archetype, margin,
  rhythm and motif arrangement (§3.15 above, notes §3.27), superseding the
  earlier collapse finding (§1.4).
- **The ranking picks the same layout type for nearly every poster**
  (run 20261006_144208):
  - certificates: "classic centred" on 14 of 16, because the top
    candidates tie exactly on C_total and the first in the list wins;
  - event IDs: "left-aligned" on 16 of 16, by a small, steady margin.
  - So every poster's output had the same layout per format, and the
    candidates' variety was visible only in the Recommendation Engine.
  - **Fixed before Phase 4 (2026-10-06, notes §3.31):** the master's
    composition now picks the layout type (item 3.23). The Phase 4 set
    has 4 layout types per format across the 16 posters. Chapter 4
    should report the cost: the chosen type isn't always the lowest
    C_total.
- **Reproducibility catch:** Stage 0's K-Means was unseeded, so identical
  runs could render different palettes and pick different winners (notes
  §3.29). It is fixed, and everything reported comes from after the fix.
- **HITL on the canvas:** moves, resizes, locks, text edits and undo/redo
  are made directly on the Figure 3 canvas. Each is one terminal event,
  verified in a real browser (notes §3.28).
- **Phase 4 MOS results:** none yet.

---

## Order of work

1. **Now, in Prism:** apply `manuscript/manu0910_fixes.md` after filling its
   six placeholders. M3 and M26 wait for the development chat's numbers,
   and M17 for screenshots.
   - M9 and M15 answer the TSA's citation concerns directly.
   - M16 needs facts from the group: who annotated, how the boxes were
     cross-checked, and what the 15-image review found.
   - M17 waits until the dashboard settles, if screenshots are wanted.
2. **Code (the development chat), as analyses that leave the rated layouts
   unchanged:** mean IoU (3.4), the stress test (M3), the latency
   benchmark (M26), F1 over the rated set, the elbow chart. See "Code
   before Chapter 4".
3. **After the consultant answers:** 3.9.
4. **After the TA answers:** 3.10, 3.11, 3.12.
