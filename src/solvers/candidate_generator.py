import json
import os
import copy
import sys

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
for _sub in ('models', 'renderers', 'data_preprocessing'):
    _p = os.path.join(_SRC, _sub)
    if _p not in sys.path:
        sys.path.append(_p)

from optimization_engine import HeuristicEvaluator
from cassowary_engine import ConstraintSolverEngine


# Layout archetypes (notes §3.27): how a candidate frames and aligns its
# content. `region` is the content's horizontal extent (fractions of the
# width); `frame` is drawn by decor.frame_layers and the renderer.
ARCHETYPES = {
    "classic": {"label": "classic centred", "frame": "panel",  "align": "center", "region": (0.0, 1.0)},
    "left":    {"label": "left-aligned",    "frame": "panel",  "align": "left",   "region": (0.0, 1.0)},
    "split":   {"label": "art column",      "frame": "split",  "align": "center", "region": (0.36, 1.0)},
    "banner":  {"label": "header banner",   "frame": "banner", "align": "center", "region": (0.0, 1.0)},
    "card":    {"label": "floating card",   "frame": "card",   "align": "center", "region": (0.07, 0.93)},
    "band":    {"label": "full-width band", "frame": "band",   "align": "center", "region": (0.0, 1.0)},
}

# Figure 3's "parallel algorithmic layout variations": each candidate is an
# archetype with its own page margin, vertical rhythm (the stack's minimum
# gap) and motif arrangement (decor.ARRANGEMENTS, by index; 6 = hero). Every
# variation is solved by the Cassowary engine from the same GNN-guided
# nodes, so none can overlap.
VARIATIONS = {
    "academic_certificate": [
        {"name": "Candidate_A", "archetype": "classic", "margin": 72.0,  "vgap": 18.0, "arrangement": 0},
        {"name": "Candidate_B", "archetype": "split",   "margin": 44.0,  "vgap": 16.0, "arrangement": 5},
        {"name": "Candidate_C", "archetype": "banner",  "margin": 76.0,  "vgap": 16.0, "arrangement": 4},
        {"name": "Candidate_D", "archetype": "left",    "margin": 104.0, "vgap": 18.0, "arrangement": 3},
        {"name": "Candidate_E", "archetype": "classic", "margin": 84.0,  "vgap": 24.0, "arrangement": 2},
        {"name": "Candidate_F", "archetype": "split",   "margin": 44.0,  "vgap": 22.0, "arrangement": 1},
    ],
    "identification_card": [
        {"name": "Candidate_A", "archetype": "classic", "margin": 60.0, "vgap": 20.0, "arrangement": 6},
        {"name": "Candidate_B", "archetype": "card",    "margin": 40.0, "vgap": 16.0, "arrangement": 0},
        {"name": "Candidate_C", "archetype": "band",    "margin": 64.0, "vgap": 18.0, "arrangement": 5},
        {"name": "Candidate_D", "archetype": "left",    "margin": 72.0, "vgap": 18.0, "arrangement": 1},
        {"name": "Candidate_E", "archetype": "classic", "margin": 64.0, "vgap": 24.0, "arrangement": 2},
        {"name": "Candidate_F", "archetype": "card",    "margin": 40.0, "vgap": 22.0, "arrangement": 6},
    ],
}


def variations_for(domain: str) -> list:
    return VARIATIONS.get(domain, VARIATIONS["academic_certificate"])


def prefer_archetype(ranked: list, archetype: str, composition: dict = None) -> list:
    """
    The candidate list with the active candidate first: the fittest
    (lowest C_total, Formula 3.11) of the archetype the master's composition
    calls for (structure_mapping.archetype_for), the rest in fitness order.
    Without a preference — no master, or no candidate of that archetype —
    the fitness order stands. Formula 3.11 still scores every candidate; it
    can't tell the archetypes apart (certificate candidates tie exactly, and
    one ID archetype won every poster by a small, steady margin), so the
    master decides which kind of layout its output is (notes §3.31).
    """
    match = next((c for c in ranked if c.get("archetype", {}).get("name") == archetype), None)
    if not archetype or match is None:
        return list(ranked)
    evidence = "; ".join((composition or {}).get("evidence", [])) or "centred text, no panel, band or side artwork"
    match = dict(match, chosen_because=f"follows the master's composition ({evidence})")
    return [match] + [c for c in ranked if c["candidate_id"] != match["candidate_id"]]


def solver_for(variation: dict, canvas_w: float, canvas_h: float, structure_guided: bool = False):
    """The Cassowary engine configured for one variation. When the GNN's
    positions carry the master's composition (`structure_guided`), the
    vertical-balance rule drops to `weak` and single gaps may reach 30% of
    the height, so the master's arrangement — a title low on the page, room
    above it for the hero — survives the solve (notes §3.26)."""
    arch = ARCHETYPES[variation.get("archetype", "classic")]
    return ConstraintSolverEngine(
        canvas_width=canvas_w, canvas_height=canvas_h,
        margin=variation["margin"], default_vgap=variation["vgap"],
        region=arch["region"], align=arch["align"],
        balance="weak" if structure_guided else "strong",
        max_gap_frac=0.30 if structure_guided else 0.10,
    )


class MetaheuristicStateExplorer:
    def __init__(self, canvas_width=1200, canvas_height=900, output_dir="data/processed/",
                 saliency_map=None, style_kit=None, domain="academic_certificate",
                 panel_rgb=(255, 255, 255), palette=None, structure_guided=False):
        """
        saliency_map: fallback legibility map when no style kit is given
          (the master's own map, as before).
        style_kit: Stage 0c output (stylistic_markers.build_style_kit). When
          present, each candidate's motifs are placed around its solved
          layout and the Legibility Penalty is scored against that
          candidate's own composed background (text-free master background,
          frame, motifs) — the layer the output is rendered on.
        palette: the renderer's palette (frame colours: panel, band).
        structure_guided: the nodes carry the master's composition (see
          solver_for).
        """
        self.canvas_w = float(canvas_width)
        self.canvas_h = float(canvas_height)
        self.output_dir = output_dir
        self.saliency_map = saliency_map
        self.style_kit = style_kit or {}
        self.domain = domain
        self.panel_rgb = tuple(panel_rgb)
        self.palette = palette or {"accent": "#D4AF37", "band": "#8A6D12"}
        self.structure_guided = structure_guided
        self._vision = None
        os.makedirs(self.output_dir, exist_ok=True)

    def compose(self, nodes, variation):
        """The candidate's composed background layer (see decor.compose_background)."""
        from decor import background_is_dark, compose_background, frame_layers

        arch = ARCHETYPES[variation.get("archetype", "classic")]
        content = [n for n in nodes if n.get("structural_class") != "decor"]
        decor_nodes = [n for n in nodes if n.get("structural_class") == "decor"]
        layers = frame_layers(self.domain, arch["frame"], self.canvas_w, self.canvas_h, content, self.palette,
                              dark=background_is_dark(self.style_kit["background"]))
        wordmark = self.style_kit.get("wordmark")
        art = wordmark or (self.style_kit.get("motifs") or [None])[0]
        return compose_background(self.style_kit["background"], int(self.canvas_w), int(self.canvas_h),
                                  decor_nodes, panel_rgb=self.panel_rgb, layers=layers,
                                  watermark=wordmark, art=art)

    def saliency(self, nodes, variation):
        """SIFT saliency map of the candidate's own composed background."""
        import numpy as np
        from vision_extraction import VisionExtractor

        if self._vision is None:
            self._vision = VisionExtractor()
        return self._vision.calculate_saliency_map(np.asarray(self.compose(nodes, variation)))

    def generate_and_rank_candidates(self, base_nodes, population_size=6):
        """
        Explores layout candidates — archetypes with their own margin,
        vertical rhythm and motif arrangement — solving each variation
        strictly through the Cassowary Constraint Solver to guarantee zero
        overlap, then ranks them by the Heuristic Fitness Function (Formula
        3.11, minimisation).

        base_nodes: the GNN-guided (or, in baseline mode, unplaced) nodes
          before any solve — every candidate starts from the same state.
        """
        results = []
        motifs = self.style_kit.get("motifs") or []
        variations = variations_for(self.domain)

        for var_cfg in variations[:max(1, min(population_size, len(variations)))]:
            arch = ARCHETYPES[var_cfg.get("archetype", "classic")]
            solver_engine = solver_for(var_cfg, self.canvas_w, self.canvas_h, self.structure_guided)
            content = [n for n in copy.deepcopy(base_nodes) if n.get("structural_class") != "decor"]
            content = solver_engine.execute_relational_logic(content)

            decor_nodes = []
            saliency_map = self.saliency_map
            if self.style_kit.get("background"):
                from decor import place_motifs, ARRANGEMENTS
                decor_nodes = place_motifs(self.canvas_w, self.canvas_h,
                                           [n["bbox"] for n in content], motifs, var_cfg["arrangement"])
                saliency_map = self.saliency(content + decor_nodes, var_cfg)
                arrangement = (decor_nodes[0]["arrangement"] if decor_nodes
                               else ARRANGEMENTS[var_cfg["arrangement"] % len(ARRANGEMENTS)][0] if motifs
                               else "no motifs")
            else:
                arrangement = "flat card"
            nodes = content + decor_nodes

            candidate_id = var_cfg["name"]
            filepath = os.path.join(self.output_dir, f"{candidate_id}.json")
            with open(filepath, 'w') as f:
                json.dump(nodes, f, indent=4)

            evaluator = HeuristicEvaluator(canvas_width=self.canvas_w, canvas_height=self.canvas_h,
                                           saliency_map=saliency_map,
                                           grid_bounds=(solver_engine.left_bound, solver_engine.right_bound),
                                           content_region=(arch["region"][0] * self.canvas_w,
                                                           arch["region"][1] * self.canvas_w))
            scores = evaluator.evaluate_layout(nodes)
            results.append({
                "candidate_id": candidate_id,
                "label": (f"{arch['label']} · margin {var_cfg['margin']:.0f}px · "
                          f"gap {var_cfg['vgap']:.0f}px · {arrangement}"),
                "variation": dict(var_cfg),
                "archetype": dict(arch, name=var_cfg.get("archetype", "classic")),
                "filepath": filepath,
                "c_total": scores["Total_Cost"],
                "metrics": scores,
                "nodes": nodes,
                "saliency_map": saliency_map,
            })

        # Rank ascending by Total Cost (minimization objective)
        results.sort(key=lambda x: x["c_total"])
        return results
