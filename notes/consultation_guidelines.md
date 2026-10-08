# Consultation Guide: Statistical Treatment

**ThemeSync** · statistics consultation · 9 October 2026

<div class="lead" markdown="1">

**Goal:** leave with the consultant's answer to every question in Part 4.
Write each answer in the space under its question, then copy it onto the
answer sheet on the last page.

**Why now:** Chapter 3 has to say how the expert ratings will be analysed
*before* anyone looks at them. If the tests are picked after seeing the
data, it can look as if we chose whichever test gave a significant
result. Scores are coming in, but **none has been analysed yet**.

**If time is short,** ask Q3, Q4, Q6 and Q7 first (the main result), then
Q2 (expert agreement) and Q10 (how the posters were chosen).

</div>

---

## Part 1. Opening update (2 minutes)

**The consultant's three remarks from the 29 September demo are all done:**

1. **"Show the steps; disable the others."** The dashboard now shows
   Step 1 Perceptual Ingestion → Step 2 Active Orchestration → Step 3
   Evaluation Report. Only the current step can be opened, and buttons
   move forward or back.
2. **"Isolate the evaluation."** Step 3 is a separate report on the
   user's own finished layout: its fitness score (Formula 3.11), the
   structural accuracy of each element (F1, as p.56 defines it), whether
   manual edits survived, and the latency of each step.
3. **"Improve the dataset; avoid background noise."** The group
   re-annotated 200 posters, and boxes covering most of a poster were
   dropped from training. The new detector (YOLO v5), measured on 32
   images neither the old nor the new detector trained on:

   | | Old (v4) | New (v5) |
   |---|---|---|
   | Precision | 0.58 | 0.84 |
   | mAP50 | 0.486 | 0.728 |

**Phase 4 status:** rating packets went to four design experts on
7 October. Scores are coming in; none has been analysed.

**Today's request:** confirm how we will analyse the ratings. p.45 of the
manuscript promises "the precise statistical tools," but Chapter 3 doesn't
name them yet.

---

## Part 2. The study in one page

**What the experts rate:**

<div class="flow">16 posters × 2 formats × 2 conditions = <b>64 layouts</b></div>

- **16 posters:** real event posters (pubmats) collected by the group.
  None appears in any of our training data; an image-duplicate check
  confirmed this, and one poster that failed it was replaced.
- **2 formats:** a certificate and an event ID, made from each poster.
- **2 conditions:**
    - **GNN:** the full system.
    - **Baseline:** the same pipeline with the GNN switched off.

Both versions of a poster carry identical text, so only the layout
differs.

**Who rates:** four design experts (Eisen Rose D. Galvante, Kyz Denise
Aquino, Mark Joseph Orias, Mark Kenneth C. Ellorde).

**How they rate:** every layout gets three scores from 1 to 5, using
Table 2's scale (adapted from ITU-T P.800, the standard that defines the
Mean Opinion Score):

| Parameter | What the expert judges |
|---|---|
| Visual Hierarchy Preservation | Do the most important elements dominate, as on the poster? |
| Brand and Typographic Consistency | Are the poster's colours, fonts and style carried over faithfully? |
| Constraint and Whitespace Harmony | Is nothing covered or crowded, with professional empty space? |

<div class="flow">64 layouts × 3 parameters × 4 experts = <b>768 ratings</b></div>

**Blinding:**

- Each page shows the original poster next to one generated layout,
  under a random code.
- Each expert has their own page order.
- Two pages from the same poster are never next to each other.
- Nothing says which version is the GNN and which is the baseline.

**The pairs we will compare:** each poster in each format has a GNN
version and a baseline version. That makes **32 pairs** (16 certificate
pairs and 16 event ID pairs).

---

## Part 3. Words you may hear

| Term | Meaning |
|---|---|
| **Ordinal data** | Ratings in order (1 < 2 < … < 5) where the steps aren't guaranteed to be equal. Our 1–5 ratings are ordinal. |
| **Paired data** | Two measurements of the same thing. Here: the same poster and format, once with the GNN and once without. |
| **p-value** | How surprising our difference would be if the GNN and the baseline were really equally good. Below the significance level means "significant." |
| **Significance level** | The p-value cut-off, fixed in advance; usually 0.05. |
| **Effect size** | How big the difference is, regardless of how many samples we have. A p-value alone doesn't tell you that. |
| **Inter-rater agreement** | How consistently the experts rate the same layouts. |
| **Two-sided test** | Checks for a difference in either direction (GNN better *or* worse). |
| **Multiple comparisons** | Every extra test adds a chance of a false "significant" result. A correction (e.g. Holm) keeps the overall risk at 5%. |

---

## Part 4. The questions

### Q1. How do we describe the ratings?

**In plain words:** before testing anything, we report the scores
themselves: the Mean Opinion Score (MOS).

**We suggest:**

- The **mean and standard deviation** for each parameter, and for the
  three combined (the "overall MOS").
- Shown separately for GNN and baseline, certificates and event IDs.
- Plus how many 1s, 2s, 3s, 4s and 5s each condition received.

ITU-T P.800 defines the MOS as the arithmetic mean.

**Other options:** the median and interquartile range, which are often
preferred for ordinal ratings, either instead of the mean or alongside it.

> **Consultant's answer:** ☐ Agrees  ☐ Changes it to: ___________________________________________

### Q2. How do we show the four experts agree?

**In plain words:** a MOS of 3.5 could mean all four experts gave 3s and
4s, or that two gave 5s and two gave 2s. An agreement measure shows
whether the average means something.

**We suggest:** **Kendall's W** (coefficient of concordance), for each
parameter and overall, with its chi-square significance test. It
compares how the experts *order* the 64 layouts, so it treats the ratings
as ordinal. That matches the test in Q3.

**Other options:**

- **ICC** (intraclass correlation): treats the ratings as numbers. It has
  several forms, so the form must be chosen.
- **Krippendorff's alpha (ordinal):** made for ordered ratings and
  copes well with ties.

**Also ask:** what value counts as acceptable agreement, and which source
should we cite for it?

> **Consultant's answer:** ☐ Agrees  ☐ Changes it to: ___________________________________________
>
> Acceptable value and source: ___________________________________________

### Q3. Which test compares the GNN with the baseline?

**In plain words:** this is the main result. Do experts rate the GNN's
layouts higher than the baseline's?

**We suggest:** the **Wilcoxon signed-rank test** on the 32 pairs. It
looks only at which version of each pair scored higher and by how much,
in ranks. So it doesn't assume the steps between 1 and 5 are equal.

**Other options:** the **paired t-test**. It treats the averaged ratings
as numbers and can detect smaller differences, but it assumes more about
the data. Statisticians disagree on which suits rating scales.

> **Consultant's answer:** ☐ Agrees  ☐ Changes it to: ___________________________________________

### Q4. Do we average the four experts first?

**In plain words:** each layout gets four ratings, one per expert. We can
average them into one score per layout, or keep all four.

**We suggest:** **average the four ratings for each layout**, then compare
the 32 pairs. A MOS is a mean by definition. Keeping all four would treat
one expert's ratings as if they came from different people.

**Other options:** keep all 128 rating pairs and use a **mixed-effects
model**, which accounts for each expert's own habits (e.g. one expert who
rates everything high). It's more thorough but more complex to run and to
explain.

> **Consultant's answer:** ☐ Agrees  ☐ Changes it to: ___________________________________________

### Q5. Certificates and event IDs: together or separately?

**In plain words:** the 32 pairs are 16 certificate pairs and 16 event ID
pairs. Testing them separately gives two answers, but from only 16 pairs
each.

**We suggest:** run the **main test on all 32 pairs together**, and report
each format's MOS separately (Q1) without a separate test.

**Other options:** a separate test for each format (smaller samples, two
more tests for Q6 to correct for).

> **Consultant's answer:** ☐ Agrees  ☐ Changes it to: ___________________________________________

### Q6. We'll run several tests. How do we avoid false positives?

**In plain words:** testing the overall score and each of the three
parameters makes four tests. Each one adds a chance of a "significant"
result that is really luck.

**We suggest:**

- **One main test, named in advance:** the overall MOS.
- The three parameters as **follow-up tests**, with the **Holm
  correction**. It adjusts the p-values so the four tests together keep a
  5% risk, and it's less strict than Bonferroni.

**Other options:** the Bonferroni correction (stricter), or testing only
the overall MOS.

> **Consultant's answer:** ☐ Agrees  ☐ Changes it to: ___________________________________________

### Q7. Two-sided or one-sided?

**In plain words:** a one-sided test asks only "is the GNN better?" A
two-sided test asks "are they different?", and so can also detect a
baseline that is better.

**We suggest:** **two-sided.** The GNN may not win. In our own Phase 3
tests, the fitness score already rates the baseline slightly better on
11 of 16 event IDs (certificates tie on 15 of 16).

**Other options:** one-sided. It can detect a smaller advantage for the
GNN, but it can't detect a baseline that is better.

> **Consultant's answer:** ☐ Agrees  ☐ Changes it to: ___________________________________________

### Q8. What significance level?

**We suggest:** **0.05.** In the manuscript, write it as "a significance
level of 0.05" rather than "α = 0.05", because α already names the
collision weight in Formula 3.11.

> **Consultant's answer:** ☐ Agrees  ☐ Changes it to: ___________________________________________

### Q9. Is 32 pairs enough, and what do we report besides the p-value?

**In plain words:** with 32 pairs, a test can detect a clear difference
but may miss a small one. A non-significant result therefore wouldn't
prove the GNN and the baseline are equally good.

**We suggest:**

- Report an **effect size** next to every p-value (for Wilcoxon, the
  rank-biserial correlation *r*).
- If the result isn't significant, write "no significant difference was
  detected," never "they are equal."

**Also ask:** is 32 pairs acceptable for this design?

> **Consultant's answer:** ☐ Agrees  ☐ Changes it to: ___________________________________________

### Q10. How do we describe the way the posters were chosen?

**In plain words:** p.45 promises "targeted sampling techniques," and p.54
says the experts rate "a randomized subset." In fact, the group collected
the 16 posters by criteria; they weren't drawn at random from a larger
pool. What *is* random is the sample codes and each expert's page order.

**We suggest:** describe it as **purposive sampling**, with the criteria
stated:

1. real event posters from school organizations;
2. not in any of our training data, checked with an image-duplicate test;
3. their text fits both the certificate and the event ID.

**Also ask:** is "purposive sampling" the right term, and is it
acceptable here?

> **Consultant's answer:** ☐ Agrees  ☐ Changes it to: ___________________________________________

### Q11. The system's own numbers (Phase 3)

**In plain words:** besides the expert ratings, Chapter 4 reports
numbers the system measures itself:

- the fitness score (Formula 3.11);
- speed (latency);
- structural accuracy (F1);
- detection accuracy (IoU).

**We suggest:**

- **Mean and standard deviation** for each.
- For GNN vs. baseline fitness, the same **Wilcoxon signed-rank test**
  on the same 32 pairs.

**Also ask:** is a test needed here, or are the means and SDs enough?

> **Consultant's answer:** ☐ Agrees  ☐ Changes it to: ___________________________________________

---

## Part 5. If the consultant asks…

| Question | Answer |
|---|---|
| Why a baseline? | To show what the GNN itself adds. The baseline is the same pipeline with only the GNN switched off, and the experts can't tell which is which. |
| Why four experts? | Expert-evaluation studies use 3–5 evaluators rather than one (Nielsen & Molich, 1990). |
| Where does the 1–5 scale come from? | ITU-T P.800 (1996), Annex B: the 5-point Excellent-to-Bad scale that defines the Mean Opinion Score. |
| Where do the three parameters come from? | Visual hierarchy, whitespace and overlap: O'Donovan et al. (2014, IEEE TVCG) and the CGL-GAN paper behind our dataset (Zhou et al., IJCAI 2022). Brand consistency: Wheeler, *Designing Brand Identity*. |
| Why 64 layouts? | 16 posters × 2 formats × 2 conditions. Comparable to the user studies in the CGL-Dataset papers, which used 60 test layouts. |
| Were any posters seen in training? | No. Each was checked against every training batch with an image-duplicate test; one that matched was replaced. |
| Have you looked at the scores yet? | No. Nothing has been analysed; that's why we're fixing the tests today. |
| Are the fitness weights calibrated? | Yes. A calibration on the Phase 3 test set (the same 64 runs) confirmed the current weights: no change to one weight made the chosen layouts better on one design rule without making them worse on another. Halving or doubling any weight changes at most 1 of the 64 rated layouts. |

---

## Part 6. After the consultation

1. Copy the answers onto the answer sheet (next page), and take a photo
   of it.
2. Bring the answers back so the revision list (item 3.9) and the
   analysis script can follow them.
3. Then write Chapter 3's statistical-treatment section from the answer
   sheet.

<div class="page-break"></div>

## Answer sheet

Consultation date: ______________________________

Consultant: ______________________________

| # | Decision | Our suggestion | Consultant's answer |
|---|---|---|---|
| Q1 | Describing the ratings | Mean ± SD per parameter and overall; counts of each rating | |
| Q2 | Expert agreement | Kendall's W (per parameter and overall) | |
| | Acceptable agreement, and its source | (ask) | |
| Q3 | Main test | Wilcoxon signed-rank, 32 pairs | |
| Q4 | Counting the experts | Average the four per layout | |
| Q5 | Formats | Main test on both together | |
| Q6 | Several tests | One main test (overall MOS); parameters with the Holm correction | |
| Q7 | Direction | Two-sided | |
| Q8 | Significance level | 0.05 | |
| Q9 | Besides the p-value | Effect size (rank-biserial *r*) | |
| Q10 | Sampling | Purposive, with three criteria | |
| Q11 | Phase 3 numbers | Mean ± SD; Wilcoxon for GNN vs. baseline fitness | |

Other comments from the consultant:

<div class="lines"></div>
