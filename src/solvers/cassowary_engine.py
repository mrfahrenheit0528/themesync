import kiwisolver as kiwi
import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models')))
from dynamic_instantiation import NodeInstantiator

_BALANCE = {"strong": kiwi.strength.strong, "medium": kiwi.strength.medium,
            "weak": kiwi.strength.weak}
# A master anchor's position (notes §3.26): above the GNN's inferred
# positions (`medium`), below the design rules (`strong`) — when they can't
# all be met, the inferred nodes give way before the master's composition.
ANCHOR = kiwi.strength.create(0.0, 10.0, 0.0)


class ConstraintSolverEngine:
    def __init__(self, canvas_width=1200, canvas_height=900, margin=50.0, default_vgap=16.0,
                 region=(0.0, 1.0), align="center", balance="strong", max_gap_frac=0.10):
        """
        margin       page margin (px) inside the content region.
        default_vgap the candidate's vertical rhythm: minimum gap between
                     stacked elements (px).
        region       horizontal extent of the content, as fractions of the
                     canvas width — (0, 1) is the whole page; a layout
                     archetype with an art column uses, e.g., (0.36, 1).
        align        "center": stacked elements share the region's centre
                     axis; "left": they share its left edge.
        balance      strength of the vertical-balance rule (equal space
                     above and below the stack): "strong" when nothing else
                     decides where the stack sits (baseline), "weak" when the
                     GNN's structure-mapped positions should (notes §3.26),
                     or None to leave it out.
        max_gap_frac cap on any single gap, as a fraction of canvas height.
        """
        self.canvas_w = float(canvas_width)
        self.canvas_h = float(canvas_height)
        self.margin_x = float(margin)
        self.margin_y = float(margin)
        self.default_vgap = float(default_vgap)
        self.region = (float(region[0]), float(region[1]))
        self.align = align
        self.balance = balance
        self.max_gap_frac = float(max_gap_frac)
        self.left_bound = self.region[0] * self.canvas_w + self.margin_x
        self.right_bound = self.region[1] * self.canvas_w - self.margin_x
        self.solver = kiwi.Solver()
        self.variables = {}

    def _initialize_node_variables(self, node_id, width, height):
        v = {
            'left': kiwi.Variable(f"{node_id}_left"),
            'top': kiwi.Variable(f"{node_id}_top"),
            'right': kiwi.Variable(f"{node_id}_right"),
            'bottom': kiwi.Variable(f"{node_id}_bottom"),
        }
        self.variables[node_id] = v

        # Dimensions are exact for the given tensor
        self.solver.addConstraint(v['right'] == v['left'] + width)
        self.solver.addConstraint(v['bottom'] == v['top'] + height)

        # Margins & boundary containment (within the content region)
        self.solver.addConstraint((v['left'] >= self.left_bound) | kiwi.strength.strong)
        self.solver.addConstraint((v['top'] >= self.margin_y) | kiwi.strength.strong)
        self.solver.addConstraint((v['right'] <= self.right_bound) | kiwi.strength.strong)
        self.solver.addConstraint((v['bottom'] <= self.canvas_h - self.margin_y) | kiwi.strength.strong)

        return v

    def _fit_width(self, node):
        """A Soft node wider than the content region is narrowed to fit it
        (the renderer fits text to whatever box it gets); Hard nodes keep
        the size the designer gave them."""
        width = float(node['bbox'][2])
        if node.get('constraint_type') != "Hard":
            width = min(width, max(8.0, self.right_bound - self.left_bound))
            node['bbox'][2] = round(width, 2)
        return width

    def execute_relational_logic(self, instantiated_nodes):
        self.solver = kiwi.Solver()
        self.variables = {}

        # The candidate's vertical rhythm is the *minimum* gap between stacked
        # elements, held at `strong` like the other design rules, so the
        # GNN's `medium` position preferences can add space between elements
        # but never squeeze them together (v1's degenerate predictions pulled
        # every gap down to a 6 px floor, notes §3.22). max_gap caps any one
        # gap (10% of the canvas height by default), so no prediction can open
        # a hole.
        self.v_gap = kiwi.Variable('vertical_gap')
        self.solver.addConstraint(self.v_gap >= 6.0)
        self.solver.addConstraint((self.v_gap == self.default_vgap) | kiwi.strength.strong)
        self.max_gap = max(3.0 * self.default_vgap, self.max_gap_frac * self.canvas_h)

        # Decor nodes (the master's motifs, placed around the solved layout by
        # decor.place_motifs) sit outside the stack: the solver leaves them
        # exactly where they are.
        sorted_nodes = sorted((n for n in instantiated_nodes if n.get('structural_class') != 'decor'),
                              key=lambda n: n['spatial_hierarchy'])
        singular_nodes = [n for n in sorted_nodes if n.get('structural_class') != 'repeating_group']
        repeating_nodes = [n for n in sorted_nodes if n.get('structural_class') == 'repeating_group']

        locked_coordinates = set()
        region_centre = (self.left_bound + self.right_bound) / 2.0

        # 1. Singular Nodes Initialization and Alignment
        for node in singular_nodes:
            node_id = node['node_id']
            tensor_w = self._fit_width(node)
            tensor_h = float(node['bbox'][3])

            current_var = self._initialize_node_variables(node_id, tensor_w, tensor_h)
            human_x, human_y = float(node['bbox'][0]), float(node['bbox'][1])
            coord_key = f"{human_x}_{human_y}"

            if node.get('constraint_type') == "Hard":
                self.solver.addConstraint(current_var['left'] == human_x)
                self.solver.addConstraint(current_var['top'] == human_y)
                locked_coordinates.add(coord_key)
            else:
                # Shared alignment axis — a standard design rule (every one of
                # the 18 sample IDs is centred; a left-aligned archetype shares
                # the region's left edge instead) — at `strong`, the tier of the
                # other design rules (margins, stacking, balance), so it
                # outranks the GNN's `medium` preferences below.
                if self.align == "left":
                    self.solver.addConstraint((current_var['left'] == self.left_bound) | kiwi.strength.strong)
                else:
                    target_x = max(self.left_bound, region_centre - tensor_w / 2.0)
                    self.solver.addConstraint((current_var['left'] == target_x) | kiwi.strength.strong)
                if node.get('gnn_predicted', False) or node.get('structure_hint', False):
                    # The GNN's predicted vertical position (notes §3.22, §3.26)
                    # is the primary soft preference for y. `medium`: it
                    # decides the rhythm and, when mapped from the master, where
                    # the stack sits, but yields to margins/containment, the
                    # non-overlap stacking order and the gap limits. A node
                    # anchored to its counterpart on the master holds its
                    # place at ANCHOR, so the inferred nodes move first.
                    strength = ANCHOR if node.get('structure_anchor', False) else kiwi.strength.medium
                    self.solver.addConstraint((current_var['top'] == human_y) | strength)

        # 2. Strict Top-to-Bottom Stacking (Non-Overlap)
        for i in range(1, len(singular_nodes)):
            curr_var = self.variables[singular_nodes[i]['node_id']]
            prev_var = self.variables[singular_nodes[i-1]['node_id']]
            self.solver.addConstraint((curr_var['top'] >= prev_var['bottom'] + self.v_gap) | kiwi.strength.strong)
            # Weak preference for exactly the candidate's gap: only a
            # tie-breaker (the GNN's `medium` positions still win), but it
            # keeps the stack compact so the vertical-balance rule (4) moves
            # the whole stack rather than stretching the gaps to fill the page.
            self.solver.addConstraint((curr_var['top'] == prev_var['bottom'] + self.v_gap) | kiwi.strength.weak)
            self.solver.addConstraint((curr_var['top'] <= prev_var['bottom'] + self.max_gap) | kiwi.strength.strong)

        # 3. Repeating Groups (Signature Blocks), distributed across the region
        if repeating_nodes:
            count = len(repeating_nodes)
            widths = [self._fit_width(n) for n in repeating_nodes]
            avail_w = max(0.0, self.right_bound - self.left_bound)
            total_w = sum(widths)
            if total_w > avail_w:  # narrow them so the row fits the region
                scale = avail_w / (total_w + 15.0 * (count + 1))
                widths = [w * scale for w in widths]
                for n, w in zip(repeating_nodes, widths):
                    n['bbox'][2] = round(w, 2)
            gap = max(15.0, (avail_w - sum(widths)) / (count + 1))

            first_rep_var = None
            cursor = self.left_bound + gap
            for i, node in enumerate(repeating_nodes):
                node_id = node['node_id']
                tensor_w = widths[i]
                tensor_h = float(node['bbox'][3])

                current_var = self._initialize_node_variables(node_id, tensor_w, tensor_h)

                if first_rep_var is None:
                    first_rep_var = current_var
                else:
                    self.solver.addConstraint((current_var['top'] == first_rep_var['top']) | kiwi.strength.strong)

                if node.get('constraint_type') == "Hard":
                    human_x, human_y = float(node['bbox'][0]), float(node['bbox'][1])
                    self.solver.addConstraint(current_var['left'] == human_x)
                    self.solver.addConstraint(current_var['top'] == human_y)
                else:
                    # Distribute repeating nodes evenly across the region
                    self.solver.addConstraint((current_var['left'] == cursor) | kiwi.strength.strong)
                    self.solver.addConstraint((current_var['bottom'] <= self.canvas_h - self.margin_y) | kiwi.strength.strong)
                cursor += tensor_w + gap

                # Must be strictly below the last singular element
                if singular_nodes:
                    last_singular_var = self.variables[singular_nodes[-1]['node_id']]
                    self.solver.addConstraint((current_var['top'] >= last_singular_var['bottom'] + self.v_gap) | kiwi.strength.strong)
                    self.solver.addConstraint((current_var['top'] == last_singular_var['bottom'] + self.v_gap) | kiwi.strength.weak)
                    self.solver.addConstraint((current_var['top'] <= last_singular_var['bottom'] + self.max_gap) | kiwi.strength.strong)

        # 4. Vertical balance — equal top and bottom margins for the whole
        # stack (top_gap == bottom_gap, i.e. first.top + last.bottom == H).
        # A standard design rule expressed as a soft constraint (Chapter 3,
        # p.39, Formulas 3.3/3.5). `strong` when nothing else decides where
        # the stack sits (baseline mode: without it the stack collapsed onto
        # the top margin); `weak` when the GNN's structure-mapped positions
        # carry the master's own composition (notes §3.26), so they decide
        # instead. Hard (manual) constraints stay `required` either way.
        if (singular_nodes or repeating_nodes) and self.balance:
            first_var = self.variables[(singular_nodes or repeating_nodes)[0]['node_id']]
            last_var = self.variables[(repeating_nodes or singular_nodes)[-1]['node_id']]
            self.solver.addConstraint(
                (first_var['top'] + last_var['bottom'] == self.canvas_h) | _BALANCE[self.balance]
            )

        self.solver.updateVariables()

        resolved_nodes = []
        for node in instantiated_nodes:
            if node['node_id'] not in self.variables:  # decor: left untouched
                resolved_nodes.append(node)
                continue
            v = self.variables[node['node_id']]
            node['bbox'][0] = round(v['left'].value(), 2)
            node['bbox'][1] = round(v['top'].value(), 2)
            node['bbox'][3] = round(v['bottom'].value() - v['top'].value(), 2)
            resolved_nodes.append(node)

        return resolved_nodes
