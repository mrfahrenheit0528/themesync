# Manu 0910.1: fixes for Prism

124 find-and-replace fixes for the items in `notes/manuscript_revision_list.md`
(M1–M25 and parts of 3.9 and 3.22), in document order. Page numbers are
Manu 0910.1's.

**Already applied (2026-10-09)** to `manuscript/Thesis Latex/`:
`chapters/chapter1.tex`, `chapter2.tex`, `chapter3.tex`, `appendix.tex` and
`references.bib`.
- Only #1 (the cover month, in `thesis.tex`) was left out.
- `git diff -- "manuscript/Thesis Latex"` shows every change.
- You can copy those files into Prism whole, or apply the fixes below one
  by one.

**One placeholder is left:** #1, the month on the cover (`thesis.tex`, not
changed; the group fills it in). #79 and #81 were filled in from the
group's facts and `manuscript/15_IMGs_Expert_Review.pdf` (2026-10-09).

**Resolved in Crossref:** the three reference entries that were
placeholders in the first version of this list. Crossref lists their DOIs
as follows:
- **Packaging-design paper:** Xiaocen Guo, Sijia Fu and Di Zhu (#110,
  #115; the Chapter 2 text, #21).
- **LLM constraint-model paper:** Roberto Penco, Damir Pintar, Mihaela
  Vranić and Marko Šoštarić (#114; the Chapter 2 text, #15).
- **Intelligent interior design paper:** Zhe Ji and Yan Yu, pp.
  135127–135137 (#120).

**Checked:**
- Every **Replace this** block occurs exactly once in the uploaded files.
  Those files are identical to the 2026-10-09 export.
- The applied folder compiles with pdfLaTeX and Biber with no errors or
  warnings, Chapter 4 included (95 pages).
- The two paragraphs that ran off the page (#60, #92) print in full.

**Two findings from drafting this list:**
- **The wrong years in Chapter 2 came from wrong bib keys.** Three
  `\citeyear{…}` calls pointed at other papers: NDN printed Garcia's 2023,
  Graph4GUI printed DepthLab's 2020, and Zheng et al. printed LayoutLM's
  2020 (#11, #12, #20).
- **Chapter 2's saliency paragraph said ThemeSync computes Xu et al.'s
  R_shm.** The system measures the saliency under each text box instead
  (Formula 3.15). Fix #26 credits R_shm to Xu et al. and says what
  ThemeSync does.

**Not in this list yet:**
- **M3, the stress-test claim (p.55):** the test has run (Chapter 4 reports
  it). p.55's wording still says the text never left its box, which the
  test disproved for the event ID's header and for six or more signature
  blocks. Fix #92 only stops the run-off.
- **M26, latency (p.62):** the benchmark has run. "Constraint
  recalculation within 0.1 s, state synchronization within 1.0 s" now
  matches Chapter 4.
- **M17, Figures 2 and 3:** screenshots later. Then the arrangement text in
  both descriptions gets updated. #94 fixes only what the Figure 2 panel
  shows.
- **3.9, the Statistical Treatment:** waits on the consultant.
  - The commented-out draft after Table 2 already picks Kendall's W and
    the Wilcoxon test. Keep it commented until the consultant answers.
  - When it's uncommented: it lacks `\end{enumerate}`, "o determine"
    should be "To determine", and "Formula 11" should be "Formula 3.11".
- **3.10–3.12 (SIFT/SURF, the CNN, Appendix A):** wait on the TA.
- **Significance and Objectives:** still in the future and present tense.
  That's often left as is; ask the TA if unsure.

---

## Title page (`thesis.tex`)

### 1. p.1 · M21 · Cover date

**Search for:** `\makeTitlePage{May}{2026}`

**Replace this:**

```latex
\makeTitlePage{May}{2026}
```

**With this:**

```latex
\makeTitlePage{\textbf{[GROUP: month of the final submission]}}{2026}
```


## Chapter 1 (`chapters/chapter1.tex`)

### 2. p.8 · M18 · Scope: IoU measures detection

**Search for:** `specifically measuring algorithmic latency, spatial prediction`

**Replace this:**

```latex
specifically measuring algorithmic latency, spatial prediction accuracy via Intersection over Union (IoU), and constraint satisfaction rates
```

**With this:**

```latex
specifically measuring algorithmic latency, layout detection accuracy via Intersection over Union (IoU), and constraint satisfaction rates
```

### 3. p.8 · M11 · Scope: past tense

**Search for:** `To ensure the framework's outputs align`

**Replace this:**

```latex
To ensure the framework's outputs align with real-world professional standards, the study will integrate a mixed-methods evaluation strategy. The mathematically validated design candidates will subsequently be evaluated by a panel of four human domain experts (professional layout artists and graphic designers with documented industry experience) using a quantifiable metric. This approach will guarantee that the framework satisfies both strict computational constraints and practical industry aesthetic requirements.
```

**With this:**

```latex
To ensure that the framework's outputs aligned with real-world professional standards, the study integrated a mixed-methods evaluation strategy. The mathematically validated design candidates were subsequently evaluated by a panel of four human domain experts (professional layout artists and graphic designers with documented industry experience) using a quantifiable metric. This approach was designed to verify that the framework satisfied both strict computational constraints and practical industry aesthetic requirements.
```

### 4. p.9 · M15 · Cassowary: cite its own paper

**Search for:** `Cassowary is an incremental constraint-solving system`

Needs the new `Badros2001Cassowary` entry (references.bib section).

**Replace this:**

```latex
Cassowary is an incremental constraint-solving system used to handle automated model generation and linear equalities within complex configuration problems \cite{Cassowary2024}.
```

**With this:**

```latex
Cassowary is an incremental constraint-solving algorithm that efficiently solves systems of linear equalities and inequalities, in which each constraint is either a requirement or a weighted preference; it was developed for user interface layout \cite{Badros2001Cassowary}.
```

### 5. p.10 · M12 · Fitness Function: repeated term

**Search for:** `\textbf{Fitness function}. Fitness Function. This is`

**Replace this:**

```latex
\textbf{Fitness function}. Fitness Function. This is a quantitative
```

**With this:**

```latex
\textbf{Fitness Function.} This is a quantitative
```

### 6. pp.10–11 · M8, M12 · Implicit Geometric Hierarchy: missing "In"; the GNN doesn't rank by area

**Search for:** `by treating distinct areas or patches`

Matches the revised p.53–54 and the code (`dynamic_instantiation.py`).

**Replace this:**

```latex
by treating distinct areas or patches as individual graph nodes. \cite{Han2022VisionGNN, Jiang2024Graph4GUI} this study, rather than relying on explicit semantic tags, the GNN infers spatial dominance by evaluating the mathematical area of a node's bounding box to achieve high-precision UI element alignment. Elements instantiated with larger geometric footprints are mathematically prioritized and positioned accordingly within the structural hierarchy.
```

**With this:**

```latex
by treating distinct areas or patches as individual graph nodes \cite{Han2022VisionGNN, Jiang2024Graph4GUI}. In this study, rather than relying on explicit semantic tags, visual priority is encoded in each element's baseline geometric dimensions and reading order: the Spatial Hierarchy Index sets each element's role and its position in the reading order, and each role is assigned a fixed baseline bounding box, so that the title receives the largest box and the recipient's or attendee's name one of the largest.
```

### 7. p.11 · M11 · MOS: "will refer"

**Search for:** `In this study, MOS will refer`

**Replace this:**

```latex
In this study, MOS will refer to the structured
```

**With this:**

```latex
In this study, MOS refers to the structured
```

### 8. p.11 · M12 · Object Serialization: repeated term

**Search for:** `\textbf{Object Serialization.}Object Serialization. Object Serialization is`

**Replace this:**

```latex
\textbf{Object Serialization.}Object Serialization. Object Serialization is
```

**With this:**

```latex
\textbf{Object Serialization.} Object Serialization is
```

### 9. p.12 · M15 · Soft Constraints: the cited paper is ORCSolver (CHI '20)

**Search for:** `optimized to achieve the most desirable`

The "[11]" was typed by hand. After this, the wrong `jiang2021` entry is no longer cited and can be deleted from references.bib.

**Replace this:**

```latex
optimized to achieve the most desirable aesthetic or functional outcome [11]. According to Jiang, Stuerzlinger, and Lutteroth (\citeyear{jiang2021}),
```

**With this:**

```latex
optimized to achieve the most desirable aesthetic or functional outcome \cite{Jiang2020ORCSolver}. According to Jiang, Stuerzlinger, Zwicker, and Lutteroth (\citeyear{Jiang2020ORCSolver}),
```

### 10. p.12 · M11 · Visual DNA: "will refer"

**Search for:** `In this study, Visual DNA will`

**Replace this:**

```latex
In this study, Visual DNA will refer to a hybrid
```

**With this:**

```latex
In this study, Visual DNA refers to a hybrid
```


## Chapter 2 (`chapters/chapter2.tex`)

### 11. p.17 · M15 · NDN: wrong bib key (it printed Garcia's year) and wrong authors

**Search for:** `While Lee, Jin, and Tseng [\citeyear{Garcia2023}]`

Also replace the `Lee2020Neural` entry (references.bib section). NDN then appears in the Notes.

**Replace this:**

```latex
While Lee, Jin, and Tseng [\citeyear{Garcia2023}] introduced
```

**With this:**

```latex
While Lee, Jiang, Essa, Le, Gong, Yang, and Yang [\citeyear{Lee2020Neural}] introduced
```

### 12. p.17 · M15 · Graph4GUI: wrong bib key (it printed DepthLab's 2020) and wrong authors

**Search for:** `Jiang, Stuerzlinger, and Richter [\citeyear{Du2020DepthLab}] introduced`

**Replace this:**

```latex
Jiang, Stuerzlinger, and Richter [\citeyear{Du2020DepthLab}] introduced Graph4GUI
```

**With this:**

```latex
Jiang, Zhou, Garg, and Oulasvirta [\citeyear{Jiang2024Graph4GUI}] introduced Graph4GUI
```

### 13. p.18 · M12 · Wang et al.: missing verb

**Search for:** `Wang, Xu, Cui, and Wei [\citeyear{Wang2023Graphical}]`

**Replace this:**

```latex
Wang, Xu, Cui, and Wei [\citeyear{Wang2023Graphical}] extraction by explicitly modeling
```

**With this:**

```latex
Wang, Xu, Cui, and Wei [\citeyear{Wang2023Graphical}] extended node extraction by explicitly modeling
```

### 14. pp.18–19 · M14, M11, M25 · YOLOv8 study: authors missing; future tense; OCR's role

**Search for:** `A recent study evaluating the comparative`

"Without relying on manual data entry" is dropped: the layout's words come from the user's payload (M25).

**Replace this:**

```latex
A recent study evaluating the comparative performance of YOLOv8 for the layout analysis of document images concluded that the YOLOv8 architecture provides state-of-the-art precision and speed for extracting structural bounding boxes across complex, heterogeneous layouts [\citeyear{dosSantosJunior2025}]. Building upon this validated extraction method, the proposed methodology will pipeline these generated bounding boxes into the Tesseract OCR engine to retrieve the corresponding textual representations. This hybridized extraction methodology will effectively unflatten raster images, providing the precise spatial embeddings and textual nodes required for downstream GNN processing without relying on manual data entry.
```

**With this:**

```latex
A recent study by dos Santos Júnior, Paixão, and Alvarez [\citeyear{dosSantosJunior2025}], evaluating the comparative performance of YOLOv8 for the layout analysis of document images, concluded that the YOLOv8 architecture provides state-of-the-art precision and speed for extracting structural bounding boxes across complex, heterogeneous layouts. Building upon this validated extraction method, this study passed the generated bounding boxes to the Tesseract OCR engine to retrieve the corresponding textual representations. This hybridized extraction methodology unflattened raster images into the spatial embeddings and labelled text nodes required for downstream GNN processing.
```

### 15. p.20 · M15 · LLM constraint-model paper: authors (checked in Crossref)

**Search for:** `through the work of Penko, Penko,`

Crossref lists DOI 10.3390/app15126518 as Penco, Pintar, Vranić, and Šoštarić. The bib entry is corrected below.

**Replace this:**

```latex
through the work of Penko, Penko, Varga, and Šoštarić [\citeyear{Penko2025LLM}]
```

**With this:**

```latex
through the work of Penco, Pintar, Vranić, and Šoštarić [\citeyear{Penko2025LLM}]
```

### 16. p.20 · M14 · Prymushko et al.: last author missing

**Search for:** `Kravtsov, and [\citeyear{Prymushko2025CRDT}]`

**Replace this:**

```latex
Kravtsov, and [\citeyear{Prymushko2025CRDT}]
```

**With this:**

```latex
Kravtsov, and Artemchuk [\citeyear{Prymushko2025CRDT}]
```

### 17. p.21 · M12 · Missing space

**Search for:** `[\citeyear{Liang2020Bidirectional}]established`

**Replace this:**

```latex
[\citeyear{Liang2020Bidirectional}]established
```

**With this:**

```latex
[\citeyear{Liang2020Bidirectional}] established
```

### 18. p.22 · M12 · Stray space

**Search for:** `Kowdle [ \citeyear{Du2020DepthLab}]`

**Replace this:**

```latex
Kowdle [ \citeyear{Du2020DepthLab}]
```

**With this:**

```latex
Kowdle [\citeyear{Du2020DepthLab}]
```

### 19. p.23 · M11, M14 · Event-driven paragraph: future tense; year-only citation without authors

**Search for:** `By synthesizing these high-speed constraints and`

**Replace this:**

```latex
By synthesizing these high-speed constraints and HITL principles, the orchestration layer will operate as a highly synchronized, event-driven ecosystem. To prevent computational bottlenecks and ensure the graphical interface does not suffer from visual occlusion or frame-rate degradation during manual manipulation, the framework will decouple continuous drag states from the mathematical solvers. Every manual human refinement will act as an asynchronous, post-interaction event trigger. Specifically, the system will only harden the spatial parameters and force the underlying constraint solver to calculate optimal coordinate placements upon the user's release of the element (the on-drop or on-resize-complete event hook). This event-driven approach will mathematically guarantee that the algorithm respects the interactive human inputs without overloading the CPU during fluid drag states, successfully maintaining both global layout harmony and strict latency thresholds [\citeyear{Hu2025FacilityLayout, Du2020DepthLab, He2022iPLAN}].
```

**With this:**

```latex
By synthesizing these high-speed constraints and HITL principles, the orchestration layer operated as a highly synchronized, event-driven ecosystem. To prevent computational bottlenecks and ensure the graphical interface did not suffer from visual occlusion or frame-rate degradation during manual manipulation, the framework decoupled continuous drag states from the mathematical solvers. Every manual human refinement acted as an asynchronous, post-interaction event trigger. Specifically, the system hardened the spatial parameters and invoked the underlying constraint solver to calculate optimal coordinate placements only upon the user's release of the element (the on-drop or on-resize-complete event hook). This event-driven approach ensured that the algorithm respected the interactive human inputs without overloading the CPU during fluid drag states, maintaining both global layout harmony and strict latency thresholds \cite{Hu2025FacilityLayout, Du2020DepthLab, He2022iPLAN}.
```

### 20. p.24 · M15 · Zheng et al.: wrong bib key (it printed LayoutLM's 2020)

**Search for:** `Zheng, Yang, and Zeng [\citeyear{Xu2020LayoutLM}]`

**Replace this:**

```latex
Zheng, Yang, and Zeng [\citeyear{Xu2020LayoutLM}]
```

**With this:**

```latex
Zheng, Yang, and Zeng [\citeyear{Zheng2025Interior}]
```

### 21. p.24 · M15 · Packaging-design paper: authors (checked in Crossref)

**Search for:** `Similarly, Guo, Zhao, and Zhang [\citeyear{Guo2025Aesthetic}]`

Crossref lists DOI 10.1038/s41598-025-20046-1 as Xiaocen Guo, Sijia Fu, and Di Zhu. The bib entry is corrected below.

**Replace this:**

```latex
Similarly, Guo, Zhao, and Zhang [\citeyear{Guo2025Aesthetic}]
```

**With this:**

```latex
Similarly, Guo, Fu, and Zhu [\citeyear{Guo2025Aesthetic}]
```

### 22. p.24 · M15 · Aesthetic-scores sentence: cite the intelligent-design paper, not the CSP paper

**Search for:** `balance functionality with visual harmony \cite{Zhang2025Scalable}.`

`zhang2025intelligent` ("Intelligent Interior Design Systems: Optimizing Layouts and Aesthetics Using AI and User Data") matches this sentence, but its author list is wrong (references.bib section).

**Replace this:**

```latex
balance functionality with visual harmony \cite{Zhang2025Scalable}.
```

**With this:**

```latex
balance functionality with visual harmony \cite{zhang2025intelligent}.
```

### 23. p.24 · M11, M14 · O'Donovan et al.: "will be" and a hand-typed year

**Search for:** `O'Donovan, Agarwala, and Hertzmann [2014], who`

**Replace this:**

```latex
O'Donovan, Agarwala, and Hertzmann [2014], who demonstrated that graphic layout quality will be mathematically modeled
```

**With this:**

```latex
O'Donovan, Agarwala, and Hertzmann [\citeyear{ODonovan2014Layouts}], who demonstrated that graphic layout quality could be mathematically modeled
```

### 24. p.24 · M9 · CGL-GAN: authors

**Search for:** `Expanding this formulation into deep generative`

**Replace this:**

```latex
Expanding this formulation into deep generative models, Zhou, Xu, Ge, Wei, and Xu [2022] formalized
```

**With this:**

```latex
Expanding this formulation into deep generative models, Zhou, Xu, Ma, Ge, Jiang, and Xu [\citeyear{zhou2022cglgan}] formalized
```

### 25. p.24 · M12 · Citation after the full stop (now cited in the text)

**Search for:** `to accurately capture perceptual validity. \cite{ODonovan2014Layouts,zhou2022cglgan}`

**Replace this:**

```latex
to accurately capture perceptual validity. \cite{ODonovan2014Layouts,zhou2022cglgan}
```

**With this:**

```latex
to accurately capture perceptual validity.
```

### 26. pp.24–25 · M11, M14, new · Saliency paragraph: future tense; raw BibTeX names; what the system measures

**Search for:** `Beyond structural alignment and whitespace ratios,`

New finding while drafting: in the past tense the old text said ThemeSync computed $R_{shm}$. The code measures the saliency under each text box (Formula 3.15), so the paragraph now credits $R_{shm}$ to Xu et al. and states what ThemeSync does.

**Replace this:**

```latex
Beyond structural alignment and whitespace ratios, modern automated design frameworks must also account for visual interference between generated elements and underlying background content. To prevent the degradation of text legibility caused by visual noise, the proposed layout optimization pipeline will integrate dynamic saliency evaluations. Drawing upon recent advancements in GAN-based domain adaptation for image-aware layout generation from the study of Xu, Chenchen and Zhou, Min and Ge, Tiezheng and Xu, Weiwei [\citeyear{Xuetal2026}], the framework will algorithmically quantify layout occlusion by computing the perceptual difference in the background's saliency map before and after the application of text masks. By establishing a rigid spatial clash metric ($R_{shm}$), the system will mathematically evaluate the aesthetic score of the composition. This process will ensure that the dynamically generated layout actively preserves the primary focal regions of the background while maintaining optimal structural legibility, effectively bypassing the need for static, offline feature extraction.
```

**With this:**

```latex
Beyond structural alignment and whitespace ratios, modern automated design frameworks must also account for visual interference between generated elements and underlying background content. To prevent the degradation of text legibility caused by visual noise, the layout optimization pipeline of this study integrated dynamic saliency evaluations. Advancing GAN-based domain adaptation for image-aware layout generation, Xu, Zhou, Ge, and Xu [\citeyear{Xuetal2026}] quantified layout occlusion through a spatial clash metric ($R_{shm}$) that computes the perceptual difference in the background's saliency map before and after the application of text masks. Following the same principle, this study measured the background saliency beneath each text element and penalized text placed over visually salient regions (the Legibility Penalty, Formula 3.15). Because the saliency map was computed on each candidate's own composed background, the generated layout preserved the primary focal regions of the background while maintaining structural legibility, without relying on static, offline feature extraction.
```

### 27. p.25 · M12, M15 · AAPA is Patnaik et al.'s term

**Search for:** `Ultimately, Shi, Shang, and Qi [\citeyear{Shi2023Survey}]emphasized`

**Replace this:**

```latex
Ultimately, Shi, Shang, and Qi [\citeyear{Shi2023Survey}]emphasized the integration of deep generative models to bridge the gap between high-fidelity coordinate predictions and human-centric aesthetic preferences. This Aesthetic-Aware Preference Alignment (AAPA) provides the necessary heuristic filtering to validate optimal design structures before they are presented to the user.
```

**With this:**

```latex
Ultimately, Shi, Shang, and Qi [\citeyear{Shi2023Survey}] emphasized the integration of deep generative models to bridge the gap between high-fidelity coordinate predictions and human-centric aesthetic preferences, a goal that Patnaik, Jain, Krishnamurthy, and Sarkar [\citeyear{Patnaik2025AesthetiQ}] formalized as Aesthetic-Aware Preference Alignment (AAPA). Such alignment provides the necessary heuristic filtering to validate optimal design structures before they are presented to the user.
```

### 28. p.25 · M12 · "Al" (lowercase L) for AI

**Search for:** `generative Al models`

**Replace this:**

```latex
generative Al models
```

**With this:**

```latex
generative AI models
```

### 29. p.27 · M15 · State machines: the cited papers were a layout GAN and AesthetiQ

**Search for:** `state machines for decentralized synchronization \cite{Liang2020Bidirectional,Xuetal2026,`

**Replace this:**

```latex
state machines for decentralized synchronization \cite{Liang2020Bidirectional,Xuetal2026, Patnaik2025AesthetiQ}
```

**With this:**

```latex
state machines for decentralized synchronization \cite{Liang2020Bidirectional, Prymushko2025CRDT, Gomes2025ConflictSync}
```

### 30. p.27 · M15 · Cassowary: cite its own paper

**Search for:** `the incremental Cassowary constraint-solving algorithm \cite{Jiang2020ORCSolver}`

**Replace this:**

```latex
the incremental Cassowary constraint-solving algorithm \cite{Jiang2020ORCSolver}
```

**With this:**

```latex
the incremental Cassowary constraint-solving algorithm \cite{Badros2001Cassowary}
```

### 31. p.27 · M15 · AAPA: cite Patnaik et al.

**Search for:** `Aesthetic-Aware Preference Alignment (AAPA) \cite{Shi2023Survey}.`

**Replace this:**

```latex
Aesthetic-Aware Preference Alignment (AAPA) \cite{Shi2023Survey}.
```

**With this:**

```latex
Aesthetic-Aware Preference Alignment (AAPA) \cite{Patnaik2025AesthetiQ}.
```

### 32. p.27 · M12 · "largely predominantly"

**Search for:** `has largely predominantly advanced`

**Replace this:**

```latex
has largely predominantly advanced
```

**With this:**

```latex
has largely advanced
```

### 33. p.28 · M15 · Diffusion-based layout models: cite LayoutDiffusion

**Search for:** `\cite{zhang2025intelligent, Patnaik2025AesthetiQ}`

Needs the new `Zhang2023LayoutDiffusion` entry (references.bib section).

**Replace this:**

```latex
\cite{zhang2025intelligent, Patnaik2025AesthetiQ}
```

**With this:**

```latex
\cite{Zhang2023LayoutDiffusion, Patnaik2025AesthetiQ}
```

### 34. p.29 · M8 · Gap: variables are ordered and sized by role, not ranked by area

**Search for:** `are mathematically prioritized based on their`

"Without relying on rigid semantic labels" is dropped: p.53–54 now says the index sets each element's semantic role.

**Replace this:**

```latex
are mathematically prioritized based on their assigned geometric baseline tensors, allowing dynamic content to be logically orchestrated alongside the master theme without relying on rigid semantic labels.
```

**With this:**

```latex
are placed in a defined reading order and assigned role-specific baseline dimensions, allowing dynamic content to be logically orchestrated alongside the master theme.
```


## Chapter 3 (`chapters/chapter3.tex`)

### 35. p.39 · M13 · Formula number

**Search for:** `through Formula 1 correlates`

**Replace this:**

```latex
through Formula 1 correlates
```

**With this:**

```latex
through Formula 3.1 correlates
```

### 36. p.39 · M13 · Formula number

**Search for:** `as shown in Formula 2:`

**Replace this:**

```latex
as shown in Formula 2:
```

**With this:**

```latex
as shown in Formula 3.2:
```

### 37. p.39 · M13 · Formula number

**Search for:** `The application of Formula 2 allows`

**Replace this:**

```latex
The application of Formula 2 allows
```

**With this:**

```latex
The application of Formula 3.2 allows
```

### 38. p.40 · M15 · Cassowary: cite its own paper

**Search for:** `It is optimized to solve systems`

**Replace this:**

```latex
It is optimized to solve systems of linear equalities and inequalities efficiently \cite{Jiang2020ORCSolver}.
```

**With this:**

```latex
It is optimized to solve systems of linear equalities and inequalities efficiently \cite{Badros2001Cassowary}.
```

### 39. p.40 · M13 · Formula number

**Search for:** `expressed through linear equations defined in`

**Replace this:**

```latex
expressed through linear equations defined in Formula 3:
```

**With this:**

```latex
expressed through linear equations defined in Formula 3.3:
```

### 40. p.40 · M22, M13 · "Incrementally": the whole layout is re-solved per event

**Search for:** `The solver uses a dual-simplex method`

**Replace this:**

```latex
The solver uses a dual-simplex method to maintain these relationships established in Formula 3 incrementally, allowing the layout to re-calculate in milliseconds whenever a single variable—such as viewport width—is adjusted \cite{Li2024SMT}.
```

**With this:**

```latex
The solver used a dual-simplex method to satisfy the relationships established in Formula 3.3. In this implementation, the whole layout was re-solved on every terminal user event, and each solve completed within milliseconds, so the layout re-calculated immediately whenever a variable—such as an element's position or the viewport width—was adjusted \cite{Li2024SMT}.
```

### 41. p.40 · M13 · Formula number

**Search for:** `Hard Equality Constraint in Formula 4:`

**Replace this:**

```latex
Hard Equality Constraint in Formula 4:
```

**With this:**

```latex
Hard Equality Constraint in Formula 3.4:
```

### 42. p.41 · M13 · Formula number

**Search for:** `Weighted Objective Function defined in Formula`

**Replace this:**

```latex
Weighted Objective Function defined in Formula 5:
```

**With this:**

```latex
Weighted Objective Function defined in Formula 3.5:
```

### 43. p.41 · M11 · GNN: past tense

**Search for:** `The architecture of a Graph Neural`

**Replace this:**

```latex
The architecture of a Graph Neural Network (GNN) will be designed for processing relational data by maintaining and updating node states through a graph structure \cite{Wu2022GNN}. In the ThemeSync framework, the design canvas will be modeled as a graph structure. Each design element—such as a text block, logo, or image—will function as a node, while spatial and semantic relationships—such as alignment or proximity—will be represented as edges. Through a message-passing mechanism, nodes will exchange information with their neighbors, allowing the system to capture dependencies among elements. This process will enable the model to infer how design components will interact and depend on one another, supporting relational logic inference for layout optimization.
```

**With this:**

```latex
The architecture of a Graph Neural Network (GNN) was designed for processing relational data by maintaining and updating node states through a graph structure \cite{Wu2022GNN}. In the ThemeSync framework, the design canvas was modeled as a graph structure. Each design element—such as a text block, logo, or image—functioned as a node, while spatial and semantic relationships—such as alignment or proximity—were represented as edges. Through a message-passing mechanism, nodes exchanged information with their neighbors, allowing the system to capture dependencies among elements. This process enabled the model to infer how design components interact and depend on one another, supporting relational logic inference for layout optimization.
```

### 44. p.42 · M11, M13 · Initial Feature Encoding: past tense

**Search for:** `Every design element will start with`

**Replace this:**

```latex
Every design element will start with a set of basic information called a feature vector \cite{Zhou2020Review}. This initial description will record the element's spatial and visual properties, serving as the starting point for relational analysis as established in Formula 6:
```

**With this:**

```latex
Every design element started with a set of basic information called a feature vector \cite{Zhou2020Review}. This initial description recorded the element's spatial and visual properties, serving as the starting point for relational analysis as established in Formula 3.6:
```

### 45. p.42 · M8, M13 · Initial Feature Encoding: the GNN doesn't weight elements by area

**Search for:** `Because the baseline training dataset (CGL-Dataset)`

The sentence about $c_i$ and $s_i$ before this passage is left alone: it waits on the TA (item 3.12).

**Replace this:**

```latex
Because the baseline training dataset (CGL-Dataset) categorizes text under a generic supercategory rather than explicit semantic labels, the framework establishes visual priority through Implicit Geometric Hierarchy. During Dynamic Node Instantiation, the system algorithmically assigns Baseline Geometric Tensors (predefined bounding box dimensions, $w_i \times h_i$) to external administrative variables before they are encoded into the graph. The Graph Neural Network infers spatial dominance purely by evaluating these initial geometric parameters. Elements instantiated with a larger spatial footprint are mathematically assigned a higher relational weight by the GNN, ensuring they are positioned precisely at the top of the structural hierarchy without requiring explicit semantic tagging. By organizing these variables into the structure of Formula 6, the system creates a standardized input for the subsequent Graph Neural Network layers.
```

**With this:**

```latex
Because the baseline training dataset (CGL-Dataset) categorizes text under a generic supercategory rather than explicit semantic labels, the framework established visual priority through Implicit Geometric Hierarchy. During Dynamic Node Instantiation, the system algorithmically assigned Baseline Geometric Tensors (predefined bounding box dimensions, $w_i \times h_i$) to external administrative variables before they were encoded into the graph, and the Spatial Hierarchy Index fixed their reading order. Visual priority was therefore carried by each element's role-specific dimensions and its position in the reading order, both of which entered the GNN through Formula 3.6, rather than by explicit semantic tagging. By organizing these variables into the structure of Formula 3.6, the system created a standardized input for the subsequent Graph Neural Network layers.
```

### 46. p.42 · M11, M13 · Message passing: past tense

**Search for:** `The GNN will process these features`

**Replace this:**

```latex
The GNN will process these features through a layer-wise exchange \cite{Bronstein2023Geometric}. At each layer k, every element will compute messages from its neighbors to update its own representation as defined in Formula 7:
```

**With this:**

```latex
The GNN processed these features through a layer-wise exchange \cite{Bronstein2023Geometric}. At each layer $k$, every element computed messages from its neighbors to update its own representation as defined in Formula 3.7:
```

### 47. p.42 · M13 · Formula number

**Search for:** `In this architecture described by Formula`

**Replace this:**

```latex
In this architecture described by Formula 7,
```

**With this:**

```latex
In this architecture described by Formula 3.7,
```

### 48. p.43 · M11, M13 · Edge features: past tense

**Search for:** `The connections $e_{ij}$ utilized within the`

**Replace this:**

```latex
The connections $e_{ij}$ utilized within the message function of Formula 7 will carry edge features describing spatial logic, which are formally structured in Formula 8:
```

**With this:**

```latex
The connections $e_{ij}$ utilized within the message function of Formula 3.7 carried edge features describing spatial logic, which are formally structured in Formula 3.8:
```

### 49. p.43 · M11, M13 · Edge features: "will mean"

**Search for:** `According to Formula 8, these features`

**Replace this:**

```latex
According to Formula 8, these features include distance, Intersection over Union (IoU), and an alignment score where 0 will mean no alignment and 1 will mean perfect alignment.
```

**With this:**

```latex
According to Formula 3.8, these features include the horizontal and vertical offsets, Intersection over Union (IoU), and an alignment score, where 0 means no alignment and 1 means perfect alignment.
```

### 50. p.43 · M6 · GNN held-out results: what improved, and which error

**Search for:** `The final GNN output was registered`

Numbers from `results/gnn_heldout_eval.json` (notes §3.26).

**Replace this:**

```latex
The final GNN output was registered back to the master's anchors, ensuring that the mapped elements retained their original placements while the network optimally placed the unmapped elements between them. On the held-out validation split, this structure-aware initialization reduced overall position error to 0.036 (compared to 0.050 for the structure start alone), and when registered to exact anchors, improved the placement of unmapped elements to a gap error of 0.075 versus 0.081 for standard linear interpolation.
```

**With this:**

```latex
The final GNN output was registered back to the master's anchors, ensuring that the mapped elements retained their original placements while the network placed the unmapped elements between them. On a held-out validation split of 2,900 CGL-Dataset layouts (a seeded 5\% of its training split, since the dataset's test split carries no annotations), the GNN reduced the position error of the structure start from 0.050 to 0.036, expressed as fractions of the canvas. When the master's exact anchors were given, the registered output placed the unmapped elements with a vertical-center error of 0.075, compared with 0.081 for linear interpolation between the anchors.
```

### 51. pp.43–44 · M2, M11, M13 · State Synchronization: the paragraph printed twice; past tense

**Search for:** `The State Synchronization module will record every change`

Select from "The State Synchronization module will record every change" through the end of the *second* paragraph ("…\cite{Kleppmann2022CRDT}."), i.e. both paragraphs, and paste the one paragraph below.

**Replace this:**

```latex
The State Synchronization module will record every change the designer will make during a session. Each interaction — whether a position nudge, a resize, or an element lock — will be saved as an immutable entry in a JSON-based state chain  No prior state will ever be overwritten, which means the designer's complete editing history will be preserved and any earlier version of the canvas will be restorable.
Each designer action will be modeled as a state transition. When an action will be performed at time t, the system will move from the current canvas state St to a new state St+1 based on a deterministic transition function defined in Formula 9 

The State Synchronization module will record every definitive change the designer will make during a session. Each interaction—whether a finalized position nudge, a completed resize, or an element lock—will be saved as an immutable entry in a JSON-based state chain \cite{Sabau2024RealTime}. To ensure optimal computational latency, the state machine will operate strictly as an Event-Driven Post-Interaction Solver. The system will deliberately ignore continuous manipulation data (e.g., on-drag coordinate streams) to prevent overloading the solver pipeline. Instead, a state transition will only initiate upon a terminal user action. When a discrete event will be performed at time $t$, the system will move from the current canvas state $S_t$ to a new state $S_{t+1}$ based on a deterministic transition function defined in Formula 9 \cite{Kleppmann2022CRDT}.
```

**With this:**

```latex
The State Synchronization module recorded every definitive change the designer made during a session. Each interaction—whether a finalized position nudge, a completed resize, or an element lock—was saved as an immutable entry in a JSON-based state chain \cite{Sabau2024RealTime}. No prior state was ever overwritten, so the designer's complete editing history was preserved and any earlier version of the canvas remained restorable. To ensure optimal computational latency, the state machine operated strictly as an Event-Driven Post-Interaction Solver. The system deliberately ignored continuous manipulation data (e.g., on-drag coordinate streams) to prevent overloading the solver pipeline. Instead, a state transition was initiated only upon a terminal user action. When a discrete event was performed at time $t$, the system moved from the current canvas state $S_t$ to a new state $S_{t+1}$ based on a deterministic transition function defined in Formula 3.9 \cite{Kleppmann2022CRDT}.
```

### 52. p.44 · M13 · Formula number

**Search for:** `In the model represented by Formula`

**Replace this:**

```latex
In the model represented by Formula 9,
```

**With this:**

```latex
In the model represented by Formula 3.9,
```

### 53. p.44 · M12 · Stray full stop

**Search for:** `lock toggles, and direct text edits.).`

**Replace this:**

```latex
lock toggles, and direct text edits.).
```

**With this:**

```latex
lock toggles, and direct text edits).
```

### 54. p.44 · M11, M13 · Constraint type: past tense

**Search for:** `After each transition, every affected element`

**Replace this:**

```latex
After each transition, every affected element will be assigned a constraint type \cite{Liu2026Multimedia}. The classification logic for these elements is formally presented in Formula 10:
```

**With this:**

```latex
After each transition, every affected element was assigned a constraint type \cite{Liu2026Multimedia}. The classification logic for these elements is formally presented in Formula 3.10:
```

### 55. p.45 · M10 · Formula 3.10, first line: set membership

**Search for:** `c_i=Hard,\ if\ \ e_i\ will\ belong\`

**Replace this:**

```latex
c_i=Hard,\ if\ \ e_i\ will\ belong\ to\ U_{manual} \\
```

**With this:**

```latex
c_i &= \text{Hard}, \quad \text{if } e_i \in U_{manual} \\
```

### 56. p.45 · M10 · Formula 3.10, second line: set membership

**Search for:** `c_i=Soft,\ if\ \ e_i\ will\ belong\`

**Replace this:**

```latex
c_i=Soft,\ if\ \ e_i\ will\ belong\ to\ A_{algorithmic}
```

**With this:**

```latex
c_i &= \text{Soft}, \quad \text{if } e_i \in A_{algorithmic}
```

### 57. p.45 · M11, M13 · Formula 3.10's explanation: past tense

**Search for:** `As specified in Formula 10, elements`

**Replace this:**

```latex
As specified in Formula 10, elements manually adjusted by the designer ($U_{manual}$) will be labeled as Hard constraints, meaning the system will not change their position or dimensions. Conversely, elements placed or adjusted by the algorithm ($A_{algorithmic}$) will be labeled as Soft constraints, which the system will be permitted to modify during layout optimization.
```

**With this:**

```latex
As specified in Formula 3.10, elements manually adjusted by the designer ($U_{manual}$) were labeled as Hard constraints, meaning the system did not change their position or dimensions. Conversely, elements placed or adjusted by the algorithm ($A_{algorithmic}$) were labeled as Soft constraints, which the system was permitted to modify during layout optimization.
```

### 58. p.45 · M11 · Visual DNA validation: past tense

**Search for:** `To guarantee that the orchestration engine`

**Replace this:**

```latex
To guarantee that the orchestration engine executes with absolute structural and stylistic precision, the framework will implement a dual-validation protocol to mathematically and programmatically ensure the correctness of the Hybrid Visual DNA prior to layout synthesis. Because the Visual DNA is composed of both extracted and injected variables, the validation will be bifurcated into Algorithmic Correctness and Administrative Correctness.
```

**With this:**

```latex
To guarantee that the orchestration engine executed with structural and stylistic precision, the framework implemented a dual-validation protocol to mathematically and programmatically ensure the correctness of the Hybrid Visual DNA prior to layout synthesis. Because the Visual DNA is composed of both extracted and injected variables, the validation was bifurcated into Algorithmic Correctness and Administrative Correctness.
```

### 59. pp.45–46 · M11, 3.22 · Elbow Method: past tense, and the k range the code uses

**Search for:** `The correctness of the autonomously extracted`

The k range and seeding are from `vision_extraction.py` (notes §3.29).

**Replace this:**

```latex
The correctness of the autonomously extracted color features will be mathematically validated by optimizing the Within-Cluster Sum of Squares (WCSS) during the K-Means execution, as established in Formula 3.1. To prevent the extraction of inaccurate or perceptual outlier colors, the algorithm will iteratively compute the WCSS across multiple centroid ($k$) configurations. The system will programmatically identify the optimal $k$-value by detecting the inflection point (Elbow Method) in the WCSS decay curve. This mathematical convergence will serve as the strict validation metric, guaranteeing that the extracted color centroids accurately and optimally represent the true perceptual variance of the master design template.
```

**With this:**

```latex
The correctness of the autonomously extracted color features was mathematically validated by optimizing the Within-Cluster Sum of Squares (WCSS) during the K-Means execution, as established in Formula 3.1. To prevent the extraction of inaccurate or perceptual outlier colors, the algorithm iteratively computed the WCSS across multiple centroid configurations ($k = 2$ to $6$, each the best of five seeded initializations, so that a master always yielded the same palette). The system programmatically identified the optimal $k$-value by detecting the inflection point (Elbow Method) in the WCSS decay curve. This mathematical convergence served as the validation metric, ensuring that the extracted color centroids represented the perceptual variance of the master design template.
```

### 60. p.46 · M1, M11 · Schema validation: the paragraph that runs off the page; past tense

**Search for:** `To prevent the typographic hallucinations inherent`

The cause of the run-off was the bare `_` in `max_characters`.

**Replace this:**

```latex
To prevent the typographic hallucinations inherent in traditional Optical Character Recognition (OCR) systems, the correctness of the user-defined typographic parameters (font family, font weight, and baseline geometric sizing) will be strictly enforced through pre-orchestration JSON Schema Validation. Prior to initializing the Graph Neural Network (GNN) or the Cassowary solver, the framework will parse the ingested Dynamic Content Payload against a rigid, predefined data schema. The validation algorithm verified that all inputs strictly conformed to programmatic constraints formalized via JSON Schema (Draft 2020-12). Specifically, typographic rules dictated that font weights belonged to a valid integer set $\in \{100, 200, \dots, 900\}$, and baseline font sizes were constrained between a minimum of 8 pixels and a maximum of 15\% of the viewport's shorter side. Furthermore, content payload rules required that every requested schema variable was present and formatted strictly as a string that did not exceed its predefined max_characters limit. If a user payload violates these structural boundaries, the system will programmatically reject the initialization, thereby guaranteeing deterministic typographic correctness and preventing downstream layout failure.
```

**With this:**

```latex
To prevent the typographic hallucinations inherent in traditional Optical Character Recognition (OCR) systems, the correctness of the user-defined typographic parameters (font family, font weight, and baseline geometric sizing) was strictly enforced through pre-orchestration JSON Schema Validation. Prior to initializing the Graph Neural Network (GNN) or the Cassowary solver, the framework parsed the ingested Dynamic Content Payload against a rigid, predefined data schema. The validation algorithm verified that all inputs strictly conformed to programmatic constraints formalized via JSON Schema (Draft 2020-12). Specifically, typographic rules dictated that font weights belonged to the integer set $\{100, 200, \dots, 900\}$, and baseline font sizes were constrained between a minimum of 8 pixels and a maximum of 15\% of the viewport's shorter side. Furthermore, content payload rules required that every requested schema variable was present and formatted strictly as a string that did not exceed its predefined \texttt{max\_characters} limit. If a user payload violated these structural boundaries, the system programmatically rejected the initialization, thereby guaranteeing deterministic typographic correctness and preventing downstream layout failure.
```

### 61. p.46 · M13 · Formula 3.11 reference (it printed "Equation 3")

**Search for:** `The overarching fitness function is defined`

**Replace this:**

```latex
The overarching fitness function is defined in \ref{formula:heuristic-fitness-function}:
```

**With this:**

```latex
The overarching fitness function is defined in Formula 3.11:
```

### 62. p.46 · M13 · Formula number

**Search for:** `In Formula 11, the coefficients`

**Replace this:**

```latex
In Formula 11, the coefficients
```

**With this:**

```latex
In Formula 3.11, the coefficients
```

### 63. p.46 · M20, M13 · Collision Penalty: state the normalization

**Search for:** `It ensures elements do not visually`

**Replace this:**

```latex
It ensures elements do not visually occlude one another, defined in Formula 12:
```

**With this:**

```latex
It ensures elements do not visually occlude one another. The total overlap is normalized by the canvas area, and overlaps between two decorative motifs are not counted, as defined in Formula 3.12:
```

### 64. p.47 · M20 · Formula 3.12 as computed

**Search for:** `P_{collision} = \sum_{i=1}^{N} \sum_{j=i+1}^{N} Area(B_i \cap`

**Replace this:**

```latex
P_{collision} = \sum_{i=1}^{N} \sum_{j=i+1}^{N} Area(B_i \cap B_j)
```

**With this:**

```latex
P_{collision} = \frac{1}{Area_{canvas}} \sum_{i=1}^{N} \sum_{j=i+1}^{N} Area(B_i \cap B_j)
```

### 65. p.47 · M20, M18, M13 · Alignment Penalty: what is measured

**Search for:** `It computes the minimum pixel distance`

**Replace this:**

```latex
It computes the minimum pixel distance from a node's baseline coordinate ($x_i$ or $y_i$) to the nearest gridline, defined in Formula 13:
```

**With this:**

```latex
It computes the minimum horizontal distance from a node's left edge, center, or right edge (the set $X_i$) to the nearest vertical gridline, normalized by the canvas width $W_{canvas}$ and averaged over the $N$ nodes; signature blocks and decorative motifs, which are placed off-grid by design, are excluded. It is defined in Formula 3.13:
```

### 66. p.47 · M20 · Formula 3.13 as computed

**Search for:** `P_{alignment} = \sum_{i=1}^{N} \min_{g \in G}`

**Replace this:**

```latex
P_{alignment} = \sum_{i=1}^{N} \min_{g \in G} | coordinate_i - g |
```

**With this:**

```latex
P_{alignment} = \frac{1}{N \, W_{canvas}} \sum_{i=1}^{N} \min_{x \in X_i,\, g \in G} | x - g |
```

### 67. p.47 · M18 · Alignment: "vertical center"

**Search for:** `and an element was evaluated as`

**Replace this:**

```latex
and an element was evaluated as successfully aligned if its left edge, vertical center, or right edge directly intersected any established gridline.
```

**With this:**

```latex
and an element was evaluated as aligned when its left edge, center, or right edge lay on a gridline.
```

### 68. p.47 · M19, M13 · R_target is fixed at 0.65

**Search for:** `measuring its deviation from an optimal`

If the development chat's optional R_target analysis is wanted, it gets reported in Chapter 4; this sentence stays true either way.

**Replace this:**

```latex
measuring its deviation from an optimal target ratio ($R_{target}$) established by the master template's visual DNA. It is defined in Formula 14:
```

**With this:**

```latex
measuring its deviation from a target ratio ($R_{target}$), which was fixed at 0.65 for every master layout. It is defined in Formula 3.14:
```

### 69. p.48 · M20, M13 · Legibility Penalty: mean, not sum

**Search for:** `It calculates the sum of high-frequency`

**Replace this:**

```latex
It calculates the sum of high-frequency visual noise pixels ($p$) underlying the text coordinates, defined in Formula 15:
```

**With this:**

```latex
It calculates the mean saliency $S(p)$ of the pixels $p$ underlying each text box, averaged over the set of text nodes $T$ so that the term stays on the same scale as the other penalties, as defined in Formula 3.15:
```

### 70. p.48 · M20 · Formula 3.15 as computed

**Search for:** `P_{legibility} = \sum_{t \in TextNodes} \sum_{p`

**Replace this:**

```latex
P_{legibility} = \sum_{t \in TextNodes} \sum_{p \in B_t} S(p)
```

**With this:**

```latex
P_{legibility} = \frac{1}{|T|} \sum_{t \in T} \frac{1}{|B_t|} \sum_{p \in B_t} S(p)
```

### 71. p.48 · M18 · The engine ranks every candidate; it doesn't discard

**Search for:** `By calculating these interconnected formulas, the`

**Replace this:**

```latex
By calculating these interconnected formulas, the orchestration engine mathematically discards invalid spatial configurations and exclusively presents layout candidates that approach the optimal $F_{layout}$ minimum.
```

**With this:**

```latex
By calculating these interconnected formulas, the orchestration engine scored every candidate configuration and ranked the candidates by their $F_{layout}$ value; Phase 3 describes how the final output was selected among them.
```

### 72. p.48 · 3.9 · Materials: there is no usability study

**Search for:** `for both the automated algorithmic testing`

The rest of item 3.9 (the Statistical Treatment) waits on the consultant.

**Replace this:**

```latex
for both the automated algorithmic testing and the human-in-the-loop usability validation
```

**With this:**

```latex
for both the automated algorithmic testing and the expert aesthetic validation
```

### 73. p.48 · 3.9 · Materials: what is measured

**Search for:** `constraint satisfaction rates, and user interaction`

**Replace this:**

```latex
constraint satisfaction rates, and user interaction efficacy,
```

**With this:**

```latex
constraint satisfaction rates, and expert-rated aesthetic quality,
```

### 74. p.49 · M12, M9 · CGL-Dataset V2: garbled sentence and authors

**Search for:** `the framework utilized the CGL-Dataset V2,`

RADM's eleven authors are all named (no "et al."). Its bib entry carries `options = {maxbibnames=99}`, so the Notes list them all too.

**Replace this:**

```latex
the framework utilized the CGL-Dataset V2, which extends the foundational layout benchmark introduced by introduced by Li, Chen, Yi, Liu, Shen, and Wang [2023], which extended the foundational benchmark established by Zhou, Xu, Ge, Wei, and Xu [2022], as its primary offline training corpus.
```

**With this:**

```latex
the framework utilized as its primary offline training corpus the CGL-Dataset V2, which Li, Liu, Feng, Zhu, Li, Zhang, Lv, Zhu, Shen, Lin, and Shao [\citeyear{li2023radm}] introduced as an extension of the CGL-Dataset established by Zhou, Xu, Ma, Ge, Jiang, and Xu [\citeyear{zhou2022cglgan}].
```

### 75. p.49 · M12 · Citation after the full stop (now cited in the text)

**Search for:** `for relational layout inference. \cite{li2023radm, zhou2022cglgan}`

**Replace this:**

```latex
for relational layout inference. \cite{li2023radm, zhou2022cglgan}
```

**With this:**

```latex
for relational layout inference.
```

### 76. p.49 · M12 · "Annex Appendix A" (\ref already prints "Appendix")

**Search for:** `was detailed in Annex~\ref{annex:cgl-node-array}.`

**Replace this:**

```latex
was detailed in Annex~\ref{annex:cgl-node-array}.
```

**With this:**

```latex
is detailed in \ref{annex:cgl-node-array}.
```

### 77. p.50 · M12 · Heading typo

**Search for:** `\subsubsection{Emperical Master-Layout Dataset}`

**Replace this:**

```latex
\subsubsection{Emperical Master-Layout Dataset}
```

**With this:**

```latex
\subsubsection{Empirical Master-Layout Dataset}
```

### 78. p.50 · M16 · CGL-Dataset is posters, not documents

**Search for:** `observed when applying generalized document layout`

**Replace this:**

```latex
observed when applying generalized document layout models to authentic promotional graphics
```

**With this:**

```latex
observed when applying layout models trained on generalized e-commerce posters to authentic promotional graphics
```

### 79. p.50 · M16, M9 · Annotation: authors of the taxonomy; who annotated

**Search for:** `annotations strictly adopted the standardized four-class`

The group's facts (2026-10-09): two researchers annotated, and the group leader reviewed their annotations. "Cross-validation" means k-fold testing in machine learning, so it is dropped.

**Replace this:**

```latex
annotations strictly adopted the standardized four-class schema established by Zhou, Xu, Ge, Wei, and Xu [2022]: logo, text, underlay, and embellishment. The bounding box coordinates were delineated under formalized spatial boundary rules. To minimize annotator subjectivity and eliminate boundary drift, annotation tasks were distributed across independent annotators and subjected to systematic cross-validation audits. \cite{zhou2022cglgan}
```

**With this:**

```latex
annotations strictly adopted the standardized four-class schema established by Zhou, Xu, Ma, Ge, Jiang, and Xu [\citeyear{zhou2022cglgan}]: logo, text, underlay, and embellishment. The bounding boxes were drawn under written class definitions and boundary rules. To minimize annotator subjectivity, two of the researchers annotated the images, and the third researcher, as the group leader, reviewed their annotations against the written class definitions.
```

### 80. p.51 · M16 · YOLOv8 is anchor-free

**Search for:** `preventing ambiguous background container boundaries from`

**Replace this:**

```latex
preventing ambiguous background container boundaries from destabilizing anchor regression.
```

**With this:**

```latex
preventing ambiguous background containers from being learned as layout elements.
```

### 81. p.51 · M16 · The 15-image expert review: what and when

**Search for:** `Finally, an independent domain expert validated`

The sample was sent on 2026-09-26 from the earlier 124-image batch, before the 200-image re-annotation that trained the deployed detector, and the notes don't record a stratified draw. Say what was done and what the expert found.

**Replace this:**

```latex
Finally, an independent domain expert validated a representative 15-image stratified sample against formal class definition rubrics to confirm taxonomic accuracy prior to model training.
```

**With this:**

```latex
Finally, an independent graphic design expert reviewed a sample of 15 annotated images from the first 124-image batch against the written class definitions on September 29, 2026. The expert found the boxes correctly placed on all 15 images and correctly categorized on 10; on the other five, parts of logos or icons had been labeled as embellishments or grouped with adjacent text, and the overall assessment was ``acceptable with minor issues noted.'' The dataset was subsequently expanded to 200 images and re-annotated.
```

### 82. p.51 · M16 · "Guaranteed … high confidence" overstates

**Search for:** `This dedicated dataset guaranteed that the`

**Replace this:**

```latex
This dedicated dataset guaranteed that the perceptual parsing stage extracted structural bounding boxes with high confidence from authentic master layouts prior to graph construction and constraint solving.
```

**With this:**

```latex
This dedicated dataset enabled the perceptual parsing stage to extract structural bounding boxes from authentic master layouts with substantially higher confidence prior to graph construction and constraint solving.
```

### 83. p.53 · M2 · Table 1 paragraph printed twice: delete this first copy

**Search for:** `To guarantee deterministic execution and mathematical rigor, these`

Delete the whole paragraph. The second copy, just before Table 1, stays.

**Replace this:**

```latex
To guarantee deterministic execution and mathematical rigor, these preprocessed offline dataset arrays, alongside the runtime administrative typographic constraints defined in the Hybrid Visual DNA, were explicitly mapped to the mathematical variables established within the system architecture. \ref{tab:ingested-data-fields} demonstrated this precise correlation between the data structures and the algorithmic pipeline.
```

**With:** nothing (delete it).

### 84. p.53 · M18 · Event identification cards

**Search for:** `such as Identification Cards and Academic`

**Replace this:**

```latex
such as Identification Cards and Academic Certificates
```

**With this:**

```latex
such as event identification cards and Academic Certificates
```

### 85. p.54 · M12 · Missing full stop; "Annex Appendix B"

**Search for:** `received the largest geometric dimensions regardless`

"On the event ID" added: on the certificate the citation body's box is larger than the name's.

**Replace this:**

```latex
received the largest geometric dimensions regardless of their sequential placement A sample representation of this runtime schema payload, utilizing an academic certificate context, was structured and shown in Annex \ref{annex:dynamic-content-payload}:
```

**With this:**

```latex
received the largest geometric dimensions on the event ID, regardless of their sequential placement. A sample representation of this runtime schema payload, utilizing an academic certificate context, is shown in \ref{annex:dynamic-content-payload}.
```

### 86. p.54 · M23 · Table 1: stray space after the underscore

**Search for:** `\texttt{extracted\_ color\_centroids}`

`\allowbreak` keeps the line-break the space was there for, without printing a space.

**Replace this:**

```latex
\texttt{extracted\_ color\_centroids}
```

**With this:**

```latex
\texttt{extracted\_\allowbreak color\_\allowbreak centroids}
```

### 87. p.54 · M23 · Table 1: stray space after the underscore

**Search for:** `\texttt{administrative\_ typography (font\_family, weight)}`

**Replace this:**

```latex
\texttt{administrative\_ typography (font\_family, weight)}
```

**With this:**

```latex
\texttt{administrative\_\allowbreak typography (font\_\allowbreak family, weight)}
```

### 88. p.54 · M23 · Table 1: typography's symbol (S_i is the K-Means cluster, s_i the SIFT descriptor)

**Search for:** `& $S_i$`

**Replace this:**

```latex
& $S_i$
```

**With this:**

```latex
& $\tau$
```

### 89. p.54 · M23 · Table 1: stray space after the underscore

**Search for:** `\texttt{extracted\_ saliency\_weight}`

**Replace this:**

```latex
\texttt{extracted\_ saliency\_weight}
```

**With this:**

```latex
\texttt{extracted\_\allowbreak saliency\_\allowbreak weight}
```

### 90. p.54 · M23 · Table 1: saliency's symbol, as in Formula 3.15

**Search for:** `& $p_i(\text{legibility})$`

**Replace this:**

```latex
& $p_i(\text{legibility})$
```

**With this:**

```latex
& $S(p)$
```

### 91. p.54 · M23 · Table 1: stray space after the underscore

**Search for:** `\texttt{spatial\_ hierarchy}`

**Replace this:**

```latex
\texttt{spatial\_ hierarchy}
```

**With this:**

```latex
\texttt{spatial\_\allowbreak hierarchy}
```

### 92. p.55 · M1 · Synthetic templates: the paragraph that runs off the page

**Search for:** `correctly enforce the mathematical spatial_hierarchy weights`

This only stops the run-off. The stress-test claim itself (M3) gets reworded once the development chat's test has run.

**Replace this:**

```latex
correctly enforce the mathematical spatial_hierarchy weights
```

**With this:**

```latex
correctly enforce the mathematical spatial hierarchy weights
```

### 93. p.56 · M25 · OCR labels the regions; the words come from the payload

**Search for:** `alongside Tesseract OCR for text extraction,`

**Replace this:**

```latex
alongside Tesseract OCR for text extraction, converting the flattened raster pixels into structured, editable nodes. Concurrently, the Graph Neural Network
```

**With this:**

```latex
alongside Tesseract OCR, which labelled the detected text regions, converting the flattened raster pixels into structured, editable nodes; the words placed in the generated layouts came from the user's validated content payload. In parallel, the Graph Neural Network
```

### 94. pp.56–57 · M24 · Figure 2: what the panel shows

**Search for:** `(including dominant color centroids identified via`

The rest of the Figure 2 and 3 descriptions waits for the screenshots (M17).

**Replace this:**

```latex
(including dominant color centroids identified via K-Means clustering, boolean feature detection via SIFT/SURF, and the structural hierarchy parsed by the GNN)
```

**With this:**

```latex
(including dominant color centroids identified via K-Means clustering, the SIFT/SURF keypoint saliency together with whether a logo was detected, and the elements parsed by the layout detector)
```

### 95. p.57 · M18 · Phase 3 isn't the final phase

**Search for:** `The final procedural phase involved the`

**Replace this:**

```latex
The final procedural phase involved the rigorous testing
```

**With this:**

```latex
The third procedural phase involved the rigorous testing
```

### 96. p.58 · M5 · The default layout type; one name for the fitness score

**Search for:** `the final recommended output was not`

$C_{total}$ is the code's name; the manuscript's Formula 3.11 calls it $F_{layout}$.

**Replace this:**

```latex
the final recommended output was not determined solely by the lowest absolute $C_{total}$ penalty. Instead, the master layout's original visual composition dictated the target layout archetype (e.g., left-aligned text, an artwork column, or a footer band, defaulting to a classic centered structure in the absence of a master).
```

**With this:**

```latex
the final recommended output was not determined solely by the lowest absolute $F_{layout}$ penalty. Instead, the master layout's original visual composition dictated the target layout archetype (e.g., left-aligned text, an artwork column, or a footer band, with a classic centered structure when the master showed none of these cues). Without a master layout, the candidate with the lowest $F_{layout}$ was selected.
```

### 97. p.60 · M13 · Formula 3.11 reference (it printed "Equation 3")

**Search for:** `heuristic fitness calculation (\ref{formula:heuristic-fitness-function})`

**Replace this:**

```latex
heuristic fitness calculation (\ref{formula:heuristic-fitness-function})
```

**With this:**

```latex
heuristic fitness calculation (Formula 3.11)
```

### 98. p.60 · M18 · The experts rated printed pages

**Search for:** `documented industry experience—interacted with the ThemeSync`

**Replace this:**

```latex
documented industry experience—interacted with the ThemeSync outputs.
```

**With this:**

```latex
documented industry experience—evaluated the ThemeSync outputs.
```

### 99. p.60 · M18 · What the multi-evaluator sources found

**Search for:** `The deployment of multiple evaluators aligned`

Quotes in `notes/mos_parameter_grounding.md` §4.

**Replace this:**

```latex
The deployment of multiple evaluators aligned with established usability and layout evaluation protocols \cite{nielsen1990heuristic, li2023radm, zhou2022cglgan}, which demonstrated that aggregating feedback from a minimum of three to five experts is required to reliably identify structural defects.
```

**With this:**

```latex
The deployment of multiple evaluators followed established usability and layout evaluation practice: Nielsen and Molich [\citeyear{nielsen1990heuristic}] found that individual evaluators identified only 20--51\% of usability problems, whereas aggregated evaluations from as few as three to five evaluators performed well, and the studies that introduced the CGL-Dataset rated generated layouts with panels of professional and novice designers \cite{zhou2022cglgan, li2023radm}.
```

### 100. p.61 · M4 · The baseline also turns off the structure mapping

**Search for:** `To rigorously evaluate the framework's spatial`

From `pipeline.py` (`use_gnn=False` turns `use_structure` off too).

**Replace this:**

```latex
To rigorously evaluate the framework's spatial intelligence, a blind no-GNN baseline condition was introduced. Layouts generated by the full ThemeSync orchestration engine were compared against baseline outputs generated with identical content but with the GNN module deactivated.
```

**With this:**

```latex
To rigorously evaluate the framework's spatial intelligence, a blind baseline condition was introduced. Layouts generated by the full ThemeSync orchestration engine were compared against baseline outputs generated with identical content but with both the master-structure mapping and the GNN module deactivated, so that the baseline arranged the elements as a naive reading-order stack. Both conditions shared the layout archetype selected from the master's composition, the extracted palette, the reconstructed background, and the stylistic markers.
```

### 101. p.61 · M9 · CGL-GAN and RADM authors

**Search for:** `Zhou, Xu, Ge, Wei, and Xu [\citeyear{zhou2022cglgan}]`

**Replace this:**

```latex
Zhou, Xu, Ge, Wei, and Xu [\citeyear{zhou2022cglgan}] and Li, Chen, Yi, Liu, Shen, and Wang [\citeyear{li2023radm}]
```

**With this:**

```latex
Zhou, Xu, Ma, Ge, Jiang, and Xu [\citeyear{zhou2022cglgan}] and Li, Liu, Feng, Zhu, Li, Zhang, Lv, Zhu, Shen, Lin, and Shao [\citeyear{li2023radm}]
```

### 102. p.61 · M18 · IoU measures detection

**Search for:** `to measure algorithmic precision, spatial prediction`

**Replace this:**

```latex
to measure algorithmic precision, spatial prediction accuracy, and computational efficiency
```

**With this:**

```latex
to measure algorithmic precision, detection accuracy, and computational efficiency
```

### 103. p.63 · M13 · Formula numbers

**Search for:** `defined in Formula 11. The heuristic`

**Replace this:**

```latex
defined in Formula 11. The heuristic fitness function objectively scored parallel layout candidates by computing the Collision Penalty (Formula 12 to calculate overlapping nodal areas), the Alignment Penalty (Formula 13 to measure pixel variance from established gridlines), the Whitespace Penalty (Formula 14 to evaluate the mathematical ratio of negative space), and the Legibility Penalty (Formula 15 to quantify
```

**With this:**

```latex
defined in Formula 3.11. The heuristic fitness function objectively scored parallel layout candidates by computing the Collision Penalty (Formula 3.12 to calculate overlapping nodal areas), the Alignment Penalty (Formula 3.13 to measure distances from established gridlines), the Whitespace Penalty (Formula 3.14 to evaluate the mathematical ratio of negative space), and the Legibility Penalty (Formula 3.15 to quantify
```

### 104. p.64 · M13 · Formula numbers

**Search for:** `(specifically Formulas 12 and 14)`

**Replace this:**

```latex
(specifically Formulas 12 and 14)
```

**With this:**

```latex
(specifically Formulas 3.12 and 3.14)
```

### 105. p.65 · M9 · Cite P.800 in Chapter 3

**Search for:** `This rubric was adapted from the`

**Replace this:**

```latex
This rubric was adapted from the standard ITU-T P.800 Absolute Category Rating scale.
```

**With this:**

```latex
This rubric was adapted from the standard ITU-T P.800 Absolute Category Rating scale \cite{itut1996p800}.
```

### 106. p.67 · M15 · Palette mapping: cite the palette-mapping paper

**Search for:** `remained mathematically consistent during structural transformations`

**Replace this:**

```latex
remained mathematically consistent during structural transformations \cite{Kosarev2022Synthesis}.
```

**With this:**

```latex
remained mathematically consistent during structural transformations \cite{Huang2025Recoloring}.
```

### 107. p.67 · M15 · OR-constraints: cite ORCSolver

**Search for:** `adaptive OR-constraints \cite{Chen2024Gestalt}`

**Replace this:**

```latex
adaptive OR-constraints \cite{Chen2024Gestalt}
```

**With this:**

```latex
adaptive OR-constraints \cite{Jiang2020ORCSolver}
```

### 108. p.67 · M15 · Constraint models: the HITL survey doesn't cover them

**Search for:** `scalable constraint generation models \cite{Jiang2023LayoutFormer, MosqueiraRey2023HumanLoop}`

**Replace this:**

```latex
scalable constraint generation models \cite{Jiang2023LayoutFormer, MosqueiraRey2023HumanLoop}
```

**With this:**

```latex
constraint-based layout generation models \cite{Jiang2023LayoutFormer, Zhang2025Scalable}
```


## Appendices (`chapters/appendix.tex`)

### 109. p.75 · M7 · Appendix B: the system's real payload

**Find:** `\label{annex:dynamic-content-payload}`, then the listing under it.

Replace everything between `\begin{lstlisting}` and `\end{lstlisting}` under Appendix B with `data/raw/academic_payload.json`.

**Replace this:**

```latex
{
  "domain_context": "academic_certificate",
  "target_aspect_ratio": "4:3",
  "variable_schema": {
    "{{Student_Name}}": { 
        "structural_class": "text_node", 
        "spatial_hierarchy": 1,
        "max_characters": 60 
    },
    "{{Course_Title}}": { 
        "structural_class": "text_node", 
        "spatial_hierarchy": 2,
        "max_characters": 80 
    },
    "{{Signature_Blocks}}": { 
        "structural_class": "repeating_group",
        "spatial_hierarchy": 3,
        "instantiation_count": 3 
    }
  }
}
```

**With this:**

```latex
{
    "domain_context": "academic_certificate",
    "target_aspect_ratio": "4:3",
    "variable_schema": {
        "{{Institution_Logo}}": {
            "structural_class": "image_node",
            "spatial_hierarchy": 0,
            "lock_aspect_ratio": true
        },
        "{{Issuing_Organization}}": {
            "structural_class": "text_node",
            "spatial_hierarchy": 1,
            "max_characters": 60
        },
        "{{Certificate_Title}}": {
            "structural_class": "text_node",
            "spatial_hierarchy": 2,
            "max_characters": 40
        },
        "{{Presentation_Line}}": {
            "structural_class": "text_node",
            "spatial_hierarchy": 3,
            "max_characters": 30
        },
        "{{Student_Name}}": {
            "structural_class": "text_node",
            "spatial_hierarchy": 4,
            "max_characters": 60
        },
        "{{Citation_Body}}": {
            "structural_class": "text_node",
            "spatial_hierarchy": 5,
            "max_characters": 150
        },
        "{{Date_Issued}}": {
            "structural_class": "text_node",
            "spatial_hierarchy": 6,
            "max_characters": 30
        },
        "{{Certificate_ID}}": {
            "structural_class": "text_node",
            "spatial_hierarchy": 7,
            "max_characters": 20
        },
        "{{Signature_Blocks}}": {
            "structural_class": "repeating_group",
            "spatial_hierarchy": 8,
            "instantiation_count": 3
        }
    }
}
```


## References (`references.bib`)

### 110. Notes · M15 · Packaging-design paper: "DOI: DOI:"

**Find the entry:** `{Fitness2025,`

The authors are right (Crossref, DOI 10.1038/s41598-025-20046-1); only the doubled "DOI:" changes.

**Replace this:**

```latex
@article{Fitness2025,
  author     = {Guo, Xiaocen and Fu, Sijia and Zhu, Di},
  title      = {Aesthetic Quality Evaluation of Packaging Design with Graph Neural Networks and Composition Features},
  journal    = {Scientific Reports},
  year       = {2025},
  volume     = {15},
  number     = {1},
  pages      = {36046},
  doi        = {DOI:10.1038/s41598-025-20046-1}
}
```

**With this:**

```latex
@article{Fitness2025,
  author     = {Guo, Xiaocen and Fu, Sijia and Zhu, Di},
  title      = {Aesthetic Quality Evaluation of Packaging Design with Graph Neural Networks and Composition Features},
  journal    = {Scientific Reports},
  year       = {2025},
  volume     = {15},
  number     = {1},
  pages      = {36046},
  doi        = {10.1038/s41598-025-20046-1}
}
```

### 111. Notes · M15 · SIFT: the malformed DOI; cite Lowe's SIFT paper

**Find the entry:** `{Lowe2009,`

The key stays `Lowe2009` so Chapter 1's `\cite` needn't change; the entry is Lowe's 2004 IJCV paper.

**Replace this:**

```latex
@article{Lowe2009,
  author  = {Lowe, David},
  title   = {Scale Invariant Feature Transform},
  journal = {Scholarpedia},
  year    = {2009},
  volume  = {4},
  number  = {5},
  pages   = {2008},
  doi     = {10.10.1145/2008},
}
```

**With this:**

```latex
@article{Lowe2009,
  author  = {Lowe, David G.},
  title   = {Distinctive Image Features from Scale-Invariant Keypoints},
  journal = {International Journal of Computer Vision},
  year    = {2004},
  volume  = {60},
  number  = {2},
  pages   = {91--110},
  doi     = {10.1023/B:VISI.0000029664.99615.94}
}
```

### 112. Notes · M15 · Graph4GUI: authors

**Find the entry:** `{Jiang2024Graph4GUI,`

The old entry's "Retrieved 2, 2026" lacked its month; set the date to when you open the page.

**Replace this:**

```latex
@inproceedings{Jiang2024Graph4GUI,
  author    = {Jiang, Yue and Stuerzlinger, Wolfgang and Richter, Christoph},
  title     = {Graph4GUI: Graph Neural Networks for Representing Graphical User Interfaces},
  booktitle = {Proceedings of the CHI Conference on Human Factors in Computing Systems (CHI '24)},
  year      = {2024},
  addendum  = {Retrieved 2, 2026 from \url{https://arxiv.org/abs/2404.13521}}
}
```

**With this:**

```latex
@inproceedings{Jiang2024Graph4GUI,
  author    = {Jiang, Yue and Zhou, Changkong and Garg, Vikas and Oulasvirta, Antti},
  title     = {Graph4GUI: Graph Neural Networks for Representing Graphical User Interfaces},
  booktitle = {Proceedings of the CHI Conference on Human Factors in Computing Systems (CHI '24)},
  year      = {2024},
  addendum  = {Retrieved October 9, 2026 from \url{https://arxiv.org/abs/2404.13521}}
}
```

### 113. Notes · M15 · Neural Design Network: authors

**Find the entry:** `{Lee2020Neural,`

**Replace this:**

```latex
@inproceedings{Lee2020Neural,
  author    = {Lee, Hsin-Ying and Jin, Hailin and Tseng, Hung-Yu},
  title     = {Neural Design Network: Graphic Layout Generation with Constraints},
  booktitle = {Proceedings of the European Conference on Computer Vision (ECCV '20)},
  year      = {2020},
  url       = {https://arxiv.org/abs/1912.09421}
}
```

**With this:**

```latex
@inproceedings{Lee2020Neural,
  author    = {Lee, Hsin-Ying and Jiang, Lu and Essa, Irfan and Le, Phuong B. and Gong, Haifeng and Yang, Ming-Hsuan and Yang, Weilong},
  title     = {Neural Design Network: Graphic Layout Generation with Constraints},
  booktitle = {Proceedings of the European Conference on Computer Vision (ECCV '20)},
  year      = {2020},
  url       = {https://arxiv.org/abs/1912.09421}
}
```

### 114. Notes · M15 · LLM constraint-model paper: authors (checked in Crossref)

**Find the entry:** `{Penko2025LLM,`

Crossref lists Penco, Pintar, Vranić, and Šoštarić, which matches the `Penco2025LLM` and `Cassowary2024` entries. Only this copy had the wrong names.

**Replace this:**

```latex
@article{Penko2025LLM,
  author  = {Penko, Ratko and Penko, Domagoj and Varga, Marko and \v{S}o\v{s}tari\'{c}, Marko},
  title   = {Large Language Model-Driven Framework for Automated Constraint Model Generation in Configuration Problems},
  journal = {Applied Sciences},
  volume  = {15},
  number  = {12},
  pages   = {6518},
  year    = {2025},
  doi     = {10.3390/app15126518}
}
```

**With this:**

```latex
@article{Penko2025LLM,
  author  = {Penco, Roberto and Pintar, Damir and Vrani\'{c}, Mihaela and \v{S}o\v{s}tari\'{c}, Marko},
  title   = {Large Language Model-Driven Framework for Automated Constraint Model Generation in Configuration Problems},
  journal = {Applied Sciences},
  volume  = {15},
  number  = {12},
  pages   = {6518},
  year    = {2025},
  doi     = {10.3390/app15126518}
}
```

### 115. Notes · M15 · Packaging-design paper, second entry: authors (checked in Crossref)

**Find the entry:** `{Guo2025Aesthetic,`

Same paper as `Fitness2025`. Crossref lists Guo, Fu, and Zhu, not Guo, Zhao, and Zhang.

**Replace this:**

```latex
@article{Guo2025Aesthetic,
  author  = {Guo, Xiao and Zhao, Wei and Zhang, Lei},
  title   = {Aesthetic quality evaluation of packaging design with graph neural networks and composition features},
  journal = {Scientific Reports},
  volume  = {15},
  year    = {2025},
  doi     = {10.1038/s41598-025-20046-1}
}
```

**With this:**

```latex
@article{Guo2025Aesthetic,
  author  = {Guo, Xiaocen and Fu, Sijia and Zhu, Di},
  title   = {Aesthetic quality evaluation of packaging design with graph neural networks and composition features},
  journal = {Scientific Reports},
  volume  = {15},
  number  = {1},
  pages   = {36046},
  year    = {2025},
  doi     = {10.1038/s41598-025-20046-1}
}
```

### 116. Notes · M15 · Wu et al. GNN book: its DOI was a KDD '23 paper's

**Find the entry:** `{Wu2022GNN,`

Check that https://doi.org/10.1007/978-981-16-6054-2 opens the book.

**Replace this:**

```latex
@book{Wu2022GNN,
  author    = {Wu, Lingfei and Cui, Peng and Pei, Jian and Zhao, Liang},
  title     = {Graph Neural Networks: Foundations, Frontiers, and Applications},
  publisher = {Springer Nature},
  year      = {2022},
  doi       = {10.1145/3580305.3599560}
}
```

**With this:**

```latex
@book{Wu2022GNN,
  author    = {Wu, Lingfei and Cui, Peng and Pei, Jian and Zhao, Liang},
  title     = {Graph Neural Networks: Foundations, Frontiers, and Applications},
  publisher = {Springer Nature},
  year      = {2022},
  doi       = {10.1007/978-981-16-6054-2}
}
```

### 117. Notes · M15 · Kleppmann 2022: the title and venue of the linked paper

**Find the entry:** `{Kleppmann2022CRDT,`

**Replace this:**

```latex
@inproceedings{Kleppmann2022CRDT,
  author    = {Kleppmann, Martin},
  title     = {Making Hard Problems Easy with {CRDT}s and State Synchronization},
  booktitle = {Proceedings of the ACM on Human-Computer Interaction},
  year      = {2022},
  addendum  = {Retrieved March 3, 2026 from \url{https://martin.kleppmann.com/papers/bft-crdt-papoc22.pdf}}
}
```

**With this:**

```latex
@inproceedings{Kleppmann2022CRDT,
  author    = {Kleppmann, Martin},
  title     = {Making {CRDT}s {B}yzantine Fault Tolerant},
  booktitle = {Proceedings of the 9th Workshop on Principles and Practice of Consistency for Distributed Data (PaPoC '22)},
  year      = {2022},
  publisher = {Association for Computing Machinery},
  doi       = {10.1145/3517209.3524042}
}
```

### 118. Notes · M9 · O'Donovan et al.: the paper the MOS parameters quote

**Find the entry:** `{ODonovan2014Layouts,`

Its energy terms ("Emphasis", "White Space", "Overlap and Boundaries") are what Chapter 3's MOS parameters cite.

**Replace this:**

```latex
@article{ODonovan2014Layouts,
  author     = {O'Donovan, Peter and Agarwala, Aseem and Hertzmann, Aaron},
  title      = {Learning Design Inspiration from Layouts},
  year       = {2014},
  issue_date = {July 2014},
  publisher  = {Association for Computing Machinery},
  address    = {New York, NY, USA},
  volume     = {33},
  number     = {4},
  issn       = {0730-0301},
  journal    = {ACM Transactions on Graphics},
  articleno  = {84},
  numpages   = {12},
  doi        = {10.1145/2601097.2601153}
}
```

**With this:**

```latex
@article{ODonovan2014Layouts,
  author  = {O'Donovan, Peter and Agarwala, Aseem and Hertzmann, Aaron},
  title   = {Learning Layouts for Single-Page Graphic Designs},
  journal = {IEEE Transactions on Visualization and Computer Graphics},
  year    = {2014},
  volume  = {20},
  number  = {8},
  pages   = {1200--1213},
  doi     = {10.1109/TVCG.2014.48}
}
```

### 119. Notes · M15 · LayoutFormer++: authors

**Find the entry:** `{Jiang2023LayoutFormer,`

**Replace this:**

```latex
@inproceedings{Jiang2023LayoutFormer,
  author    = {Jiang, Yue and Guo, Zejian and Sun, Ming},
  title     = {LayoutFormer++: Conditional Graphic Layout Generation via Constraint Serialization and Decoding Space Restriction},
  booktitle = {Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR 2023)},
  year      = {2023},
  doi       = {10.48550/arXiv.2208.08037}
}
```

**With this:**

```latex
@inproceedings{Jiang2023LayoutFormer,
  author    = {Jiang, Zhaoyun and Guo, Jiaqi and Sun, Shizhao and Deng, Huayu and Wu, Zhongkai and Mijovic, Vuksan and Yang, Zijiang James and Lou, Jian-Guang and Zhang, Dongmei},
  title     = {LayoutFormer++: Conditional Graphic Layout Generation via Constraint Serialization and Decoding Space Restriction},
  booktitle = {Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR 2023)},
  year      = {2023},
  doi       = {10.48550/arXiv.2208.08037}
}
```

### 120. Notes · M15 · Intelligent interior design paper: authors (checked in Crossref)

**Find the entry:** `{zhang2025intelligent,`

Crossref lists Zhe Ji and Yan Yu. The old author list was LayoutDiffusion's (added below). The key stays `zhang2025intelligent`, so no `\cite` changes.

**Replace this:**

```latex
@article{zhang2025intelligent,
  author = {Zhang, Junyi and Guo, Jiaqi and Sun, Shizhao and Lou, Jian-Guang and Zhang, Dongmei},
  title = {Intelligent Interior Design Systems: Optimizing Layouts and Aesthetics Using AI and User Data},
  journal = {IEEE Access},
  volume = {13},
  year = {2025},
  publisher = {IEEE},
  doi = {10.1109/ACCESS.2025.3591135},
  url = {https://doi.org/10.1109/ACCESS.2025.3591135}
}
```

**With this:**

```latex
@article{zhang2025intelligent,
  author = {Ji, Zhe and Yu, Yan},
  title = {Intelligent Interior Design Systems: Optimizing Layouts and Aesthetics Using AI and User Data},
  journal = {IEEE Access},
  volume = {13},
  pages = {135127--135137},
  year = {2025},
  publisher = {IEEE},
  doi = {10.1109/ACCESS.2025.3591135},
  url = {https://doi.org/10.1109/ACCESS.2025.3591135}
}
```

### 121. Notes · M9 · CGL-GAN: authors, pages, DOI

**Find the entry:** `{zhou2022cglgan,`

Verified in `notes/mos_parameter_grounding.md` §6.

**Replace this:**

```latex
@inproceedings{zhou2022cglgan,
  author    = {Zhou, Min and Xu, Chenchen and Ge, Tiezheng and Wei, Zhiqiang and Xu, Weiwei},
  title     = {Composition-Aware Graphic Layout GAN for Visual-Textual Presentation Designs},
  year      = {2022},
  booktitle = {Proceedings of the Thirty-First International Joint Conference on Artificial Intelligence (IJCAI-22)},
  pages     = {4064--4070},
  publisher = {International Joint Conferences on Artificial Intelligence Organization},
  doi       = {10.24963/ijcai.2022/564}
}
```

**With this:**

```latex
@inproceedings{zhou2022cglgan,
  author    = {Zhou, Min and Xu, Chenchen and Ma, Ye and Ge, Tiezheng and Jiang, Yuning and Xu, Weiwei},
  title     = {Composition-Aware Graphic Layout GAN for Visual-Textual Presentation Designs},
  year      = {2022},
  booktitle = {Proceedings of the Thirty-First International Joint Conference on Artificial Intelligence (IJCAI-22)},
  pages     = {4995--5001},
  publisher = {International Joint Conferences on Artificial Intelligence Organization},
  doi       = {10.24963/ijcai.2022/692}
}
```

### 122. Notes · M9 · CGL-Dataset V2 (RADM): authors, title, pages, DOI

**Find the entry:** `{li2023radm,`

Verified in `notes/mos_parameter_grounding.md` §6 (the citation on the CGL-Dataset V2 Hugging Face card).

**Replace this:**

```latex
@inproceedings{li2023radm,
  author    = {Li, Zhaoyun and Chen, Jialu and Yi, Biao and Liu, Zhibin and Shen, Min and Wang, Wei},
  title     = {RADM: A Relation-Aware Diffusion Model for Graphic Layout Generation},
  year      = {2023},
  booktitle = {Proceedings of the 32nd ACM International Conference on Information and Knowledge Management (CIKM '23)},
  pages     = {1308--1317},
  publisher = {Association for Computing Machinery},
  address   = {New York, NY, USA},
  doi       = {10.1145/3583780.3615017}
}
```

**With this:**

```latex
@inproceedings{li2023radm,
  author    = {Li, Fengheng and Liu, An and Feng, Wei and Zhu, Honghe and Li, Yaoyu and Zhang, Zheng and Lv, Jingjing and Zhu, Xin and Shen, Junjie and Lin, Zhangang and Shao, Jingping},
  title     = {Relation-Aware Diffusion Model for Controllable Poster Layout Generation},
  options   = {maxbibnames=99},
  year      = {2023},
  booktitle = {Proceedings of the 32nd ACM International Conference on Information and Knowledge Management (CIKM '23)},
  pages     = {1249--1258},
  publisher = {Association for Computing Machinery},
  address   = {New York, NY, USA},
  doi       = {10.1145/3583780.3615028}
}
```

### 123. Notes · M15 · Add two entries

Paste at the end of `references.bib`. The Cassowary fixes (Chapters 1–3) and the Chapter 2 diffusion-models fix cite them. Both were checked on the web on 2026-10-09.

```latex
@article{Badros2001Cassowary,
  author  = {Badros, Greg J. and Borning, Alan and Stuckey, Peter J.},
  title   = {The {C}assowary Linear Arithmetic Constraint Solving Algorithm},
  journal = {ACM Transactions on Computer-Human Interaction},
  year    = {2001},
  volume  = {8},
  number  = {4},
  pages   = {267--306},
  doi     = {10.1145/504704.504705}
}

@inproceedings{Zhang2023LayoutDiffusion,
  author    = {Zhang, Junyi and Guo, Jiaqi and Sun, Shizhao and Lou, Jian-Guang and Zhang, Dongmei},
  title     = {LayoutDiffusion: Improving Graphic Layout Generation by Discrete Diffusion Probabilistic Models},
  booktitle = {Proceedings of the IEEE/CVF International Conference on Computer Vision (ICCV)},
  year      = {2023},
  pages     = {7226--7236}
}
```

### 124. Notes · M15 · Optional: delete `jiang2021`

After the Chapter 1 Soft Constraints fix, the entry `{jiang2021,` (a wrong copy of ORCSolver) is no longer cited. Deleting it is optional; uncited entries don't print.
