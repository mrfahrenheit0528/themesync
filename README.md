# ThemeSync

*A Graph-Based Design Orchestration Framework with Real-Time Constraint
Satisfaction and Stateful Refinement*. BSCS thesis, Camarines Sur Polytechnic
Colleges.

ThemeSync takes a **master layout** (an event poster or other branded design)
and produces a matching **certificate** or **event ID** from it. It does this
in four steps:

1. reads the poster's colours, logos, title artwork and structure (YOLOv8,
   K-Means, SIFT);
2. lays out the target format with a GNN and the Cassowary constraint solver;
3. ranks six layout candidates with the heuristic fitness function;
4. lets you refine the result on an editable canvas.

`Final Manuscript.pdf` describes the method. `notes/` holds the working
notes; start with `notes/system_development_progress.md`.

---

## 1. Before you start

Everything runs on the school server, in the **`themesync_env`** conda
environment. It is already set up there.

```bash
cd ~/themesync
conda activate themesync_env
```

Every command below assumes you are in the repo folder with that
environment active.

**The model files** must be in the repo folder:

| file | what it is |
|---|---|
| `themesync_yolo_v5.pt` | the layout detector (Stage 0b) |
| `themesync_gnn_v3.pth` | the GNN (Stage 2) |

The system uses the newest one present automatically. If you cloned the
repo and they're missing, copy them from the server.

<details>
<summary>Setting up on a different machine</summary>

```bash
conda create -n themesync_env python=3.10
conda activate themesync_env
pip install -r requirements.txt
```

- **PyTorch:** `requirements.txt` was written on a different machine from
  the server. If PyTorch doesn't match your GPU, install it from
  [pytorch.org](https://pytorch.org) first; the server uses torch
  2.5.1 + CUDA 12.1.
- **Fonts:** Montserrat ships in `assets/fonts/`, so nothing has to be
  installed system-wide.
- **Tesseract OCR** is optional. Without it, detected text boxes simply
  aren't transcribed.

</details>

---

## 2. Run the dashboard

```bash
streamlit run src/dashboard/app.py --server.address 127.0.0.1 --server.port 8501
```

Then open **http://localhost:8501** in your browser. Stop it with
**Ctrl+C**.

- **In VS Code (Remote-SSH)**, the port is usually forwarded for you. If
  the page doesn't load, open the **Ports** tab in the bottom panel,
  choose **Forward a Port**, and enter `8501`.
- **From a plain terminal on your laptop**, open a tunnel first, then
  browse to http://localhost:8501:
  ```bash
  ssh -L 8501:localhost:8501 <your-username>@<server-address>
  ```
- **Keep `--server.address 127.0.0.1`.** Without it, Streamlit listens on
  the server's public address, and anyone on the network can open the
  dashboard. It has no login.
- **Port already in use?** Someone else is using 8501. Pick another port,
  e.g. `--server.port 8502`, and open that one instead.
- **After pulling code changes, restart the dashboard** (Ctrl+C, run it
  again). Streamlit doesn't reload the helper modules by itself.

### Using it

The sidebar has three pages.

**1. Perceptual Ingestion (Figure 2).**
1. Upload a poster.
2. Click **Extract Visual DNA**. The first time takes a few seconds while
   the models load.
3. Review what it found: palette, detections, background, motifs, title
   artwork and logos.
4. Set the typography, pick the **target format**, and edit the content
   fields.
5. Click **Initialize Orchestration**.

**2. Active Orchestration (Figure 3).**

The canvas is editable:

| do this | to |
|---|---|
| click | select an element (the Constraint Editor on the right follows) |
| drag | move it |
| drag a corner or edge handle | resize it (hold Shift to keep its proportions) |
| double-click text | retype it (Enter saves, Shift+Enter adds a new line, Esc cancels) |
| arrow keys | nudge it 1 px (Shift: 10 px) |
| L | lock it in place, or release it |
| Ctrl+Z / Ctrl+Shift+Z | undo / redo |
| Tab | select the next element |

- **Hard elements:** anything you move or resize becomes *Hard*: the
  solver keeps it exactly where you put it and re-arranges the rest.
- **Snapping:** hold Alt while dragging to turn it off.
- **Recommendation Engine tab:** the six ranked candidates; any of them
  can become the canvas.
- **State Timeline:** every change; any earlier state can be restored.
- **Downloads:** SVG, PNG and PDF, under the canvas.

**3. Phase 4 Evaluation Set.** Builds the expert rating packet (see
section 4).

---

## 3. Run the pipeline without the dashboard

One poster in, one SVG out (`data/rendered/` by default):

```bash
# certificate
python src/pipeline.py --payload data/raw/academic_payload.json \
    --template_image data/raw/phase4_posters/CTC.jpg

# event ID, with your own text
python src/pipeline.py --payload data/raw/id_payload.json \
    --template_image data/raw/phase4_posters/CTC.jpg \
    --content_data data/raw/sample_content_id.json
```

| option | does |
|---|---|
| `--no_gnn` | runs the no-GNN baseline instead |
| `--logo_image a.png b.png` | uses these logos instead of the ones detected on the poster |
| `--no_wordmark` | types the event title instead of cutting the poster's title artwork |
| `--output_dir DIR` | writes the SVG somewhere else |

`python src/pipeline.py --help` lists the rest.

---

## 4. Phase 4: the expert rating packet

The dashboard's **Phase 4 Evaluation Set** page does all of this with
buttons. The same steps from the terminal:

```bash
# 1. list the posters in data/raw/phase4_posters/ and add any missing ones to manifest.csv
python src/evaluation/phase4_packet.py template

# 2. generate every layout (each poster × certificate/ID × GNN/baseline) and the private answer key
python src/evaluation/phase4_packet.py generate --overwrite

# 3. one printable PDF + score sheet per expert (use a different --order_seed for each)
python src/evaluation/phase4_packet.py packet --expert "Evaluator A" --order_seed 1

# 4. after the session, type the circled scores into that expert's CSV, then
python src/evaluation/mos_collector.py --import_scores <that CSV> \
    --key data/phase4/phase4_key.csv --evaluator "Evaluator A"
python src/evaluation/mos_collector.py --report
```

- **Don't print or share `data/phase4/phase4_key.csv`.** It's the answer
  key that makes the rating blind.
- **Posters must be unseen.** `template` warns if one matches an image in
  the training set; replace it.
- **Fixing a poster's output:** two manifest columns (also checkboxes on
  the Phase 4 page) help when the output looks wrong.
  - `title_artwork` = `no` types the event title, when the artwork cut
    from the poster is clipped or the wrong region.
  - `motifs` = `no` leaves the poster's decorations out, when a
    "decoration" is really a stamp, lettering or a logo.
- **Poster count:** `generate` uses 16 posters by default, all of the
  current set. With more in the folder it picks 16 (seeded); change
  `--n_posters` to use a different number.
- **Regenerating:** if the system changes after a set was generated, add
  `--overwrite`. Older packets are moved aside, not deleted.

---

## 5. Reproduce the results

| command | what it produces |
|---|---|
| `python src/evaluation/experiment_runner.py` | Phase 3 battery: every Phase 4 poster × 2 formats × 3 conditions (GNN, mapping only, baseline) → `results/experiment_log.json`. About 30–40 min. |
| `python src/evaluation/gnn_heldout_eval.py` | GNN v1/v2/v3 on 2,900 held-out CGL layouts → `results/gnn_heldout_eval.json`. About 5 min. |
| `python src/evaluation/evaluate.py` | synthetic certificate + simulated designer edits → `results/evaluation_results.json` |
| `jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=themesync_env notebooks/results_analysis.ipynb` | refreshes every chart and table in the results notebook |

**Tests:**

```bash
python tests/test_certificate_pipeline.py
python tests/test_id_pipeline.py
```

---

## 6. After annotating more master layouts (retrain the detector)

Export the Roboflow project in **YOLOv8** format. Move the current
`data/raw/master_layout_batch/{train,valid,data.yaml}` into a new
`_raw_vN_backup/` folder, and unzip the export in their place. Then:

```bash
# convert polygon rows to boxes and drop boxes covering over half a poster (writes a copy)
python src/data_preprocessing/prepare_master_layout_dataset.py --out data/processed/yolo_master_v6

# check the labels
python src/models/finetune_yolo_master_layout.py --check_only --data data/processed/yolo_master_v6/data.yaml

# train (about 10 min on a free GPU) to a *candidate* name
python src/models/finetune_yolo_master_layout.py --data data/processed/yolo_master_v6/data.yaml \
    --base_checkpoint yolov8s.pt --imgsz 1024 --epochs 120 --patience 25 --freeze 0 --seed 0 --amp \
    --output_checkpoint themesync_yolo_v6_candidate.pt --run_name themesync_master_layout_v6

# compare with the deployed model on validation images neither trained on
python src/evaluation/yolo_compare.py --data data/processed/yolo_master_v6/data.yaml \
    --models v5=themesync_yolo_v5.pt,v6=themesync_yolo_v6_candidate.pt --out results/yolo_v6_comparison.json
```

**Before running `yolo_compare.py`:** add the new batch to
`TRAINING_IMAGES` in `src/evaluation/poster_overlap.py`. The comparison
uses that list to leave out images a model trained on.

**If the candidate wins,** copy it to `themesync_yolo_v6.pt`. The system
switches to it automatically. The annotation rules are in
`notes/annotation_guidelines.md`.

---

## Where things are

| path | contents |
|---|---|
| `src/pipeline.py` | the whole pipeline; `OrchestrationSession` is what the dashboard uses |
| `src/dashboard/` | the Streamlit app (`app.py`, `views/`, the canvas editor `canvas_editor.*`) |
| `src/data_preprocessing/` | Stage 0: palette, YOLO + OCR, stylistic markers, dataset preparation |
| `src/models/` | GNN, structure mapping, state chain, schema validation, training scripts |
| `src/solvers/` | Cassowary engine, candidate generator, fitness function |
| `src/renderers/` | SVG renderer, decoration, PNG/PDF rasterizing |
| `src/evaluation/` | Phase 3 and Phase 4 tools |
| `data/raw/` | payload schemas, sample content, posters, annotation batch (not in git) |
| `data/rendered/` | generated outputs |
| `results/` | measured results; `notebooks/results_analysis.ipynb` charts them |
| `notes/` | working notes, revision list, progress |
