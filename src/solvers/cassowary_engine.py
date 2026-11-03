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
# A Soft text box's height around a designer's Hard box (notes §3.58): kept
# unless the stack can't otherwise fit, then down to MIN_TEXT_SCALE of it
# (the renderer fits the words to the box) rather than overlapping.
TEXT_HEIGHT = kiwi.strength.create(0.0, 100.0, 0.0)
MIN_TEXT_SCALE = 0.6
# A Soft picture the designer added (§3.59) shrinks first, keeping its
# proportions, down to MIN_PICTURE_SCALE of its size.
PICTURE_SIZE = kiwi.strength.create(0.0, 50.0, 0.0)
MIN_PICTURE_SCALE = 0.4


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

    def _initialize_node_variables(self, node_id, width, height, elastic=False, picture=False):
        v = {
            'left': kiwi.Variable(f"{node_id}_left"),
            'top': kiwi.Variable(f"{node_id}_top"),
            'right': kiwi.Variable(f"{node_id}_right"),
            'bottom': kiwi.Variable(f"{node_id}_bottom"),
        }
        self.variables[node_id] = v

        # Dimensions are exact for the given tensor (an elastic text box's
        # height may give way, see TEXT_HEIGHT)
        if picture:      # a Soft picture: its width follows its height
            self.solver.addConstraint(v['right'] - v['left'] == (width / height) * (v['bottom'] - v['top']))
            self.solver.addConstraint(v['bottom'] >= v['top'] + MIN_PICTURE_SCALE * height)
            self.solver.addConstraint((v['bottom'] == v['top'] + height) | PICTURE_SIZE)
        else:
            self.solver.addConstraint(v['right'] == v['left'] + width)
            if elastic:
                self.solver.addConstraint(v['bottom'] >= v['top'] + MIN_TEXT_SCALE * height)
                self.solver.addConstraint((v['bottom'] == v['top'] + height) | TEXT_HEIGHT)
            else:
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
            fit = min(width, max(8.0, self.right_bound - self.left_bound))
            if node.get('structural_class') == 'decor' and fit < width:     # a picture keeps its proportions
                node['bbox'][3] = round(float(node['bbox'][3]) * fit / width, 2)
            width = fit
            node['bbox'][2] = round(width, 2)
        return width

    def _stack_order(self, singular_nodes, repeating_nodes, reference, fixed):
        """
        The top-to-bottom order the stack is solved in, and the Hard boxes
        that sit below the signature row (notes §3.58).

        Soft nodes keep their reading order (spatial_hierarchy). A Hard node
        (moved, resized or locked by the designer) and a picture the
        designer added (Hard or Soft) join it where they are on the canvas:
        after the last node that starts above them (in `reference`, the
        canvas before the event). Before, a Hard node kept its reading-
        order slot wherever it was put, so a text added at the end and
        dragged up the page squeezed everything above its slot into the
        space above it. A Hard node that stays in its slot gives the same
        order as before, so small moves solve exactly as they did. Anything
        below the signature row stays out of the stack.
        """
        hard = [n for n in singular_nodes if n.get('constraint_type') == "Hard"]
        if not hard and not fixed:
            return list(singular_nodes), []
        box = lambda n: reference.get(n['node_id'], n['bbox'])
        top = lambda n: float(box(n)[1])
        order = [n for n in singular_nodes if n.get('constraint_type') != "Hard"]
        placed = hard + list(fixed)
        row_top = min((float(box(n)[1]) for n in repeating_nodes), default=None)
        below_row = []
        gap = self.default_vgap
        least = lambda n: float(n['bbox'][3]) * (MIN_TEXT_SCALE if n.get('constraint_type') != "Hard" and
                                                  n.get('structural_class', 'text_node') == 'text_node' else 1.0)
        row_h = max((float(n['bbox'][3]) + gap for n in repeating_nodes), default=0.0)

        def overflow(k, node):
            # how far the stack would run past the margins with `node` after
            # order[k]: the least the nodes above and below it need
            y0, y1 = float(node['bbox'][1]), float(node['bbox'][1]) + float(node['bbox'][3])
            above = self.margin_y + sum(least(n) + gap for n in order[:k + 1])
            below = y1 + sum(gap + least(n) for n in order[k + 1:]) + row_h
            return max(0.0, above - y0) + max(0.0, below - (self.canvas_h - self.margin_y))

        for node in sorted(placed, key=top):
            if row_top is not None and top(node) + float(node['bbox'][3]) / 2.0 > row_top:
                below_row.append(node)
                continue
            # after the last node that starts above it (a tall title the box
            # was dropped onto stays above it), unless the nodes it overlaps
            # fit better on the other side of it
            y0, y1 = float(node['bbox'][1]), float(node['bbox'][1]) + float(node['bbox'][3])
            k = max((i for i, n in enumerate(order) if top(n) <= top(node)), default=-1)   # ties: after
            lo = max((i for i, n in enumerate(order) if top(n) + float(box(n)[3]) <= y0), default=-1)
            hi = max((i for i, n in enumerate(order) if top(n) < y1), default=-1)
            if overflow(k, node) > 0:
                k = min(range(lo, max(lo, hi) + 1), key=lambda j: (overflow(j, node), abs(j - k)))
            order.insert(k + 1, node)
        return order, below_row

    def execute_relational_logic(self, instantiated_nodes, reference=None, fixed=None):
        """
        Solves the stack. reference: {node_id: bbox} of the canvas before a
        designer event; fixed: the pictures the designer added, held where
        they are when Hard, placed in the stack like the format's own
        elements when Soft (their boxes are updated in place). Both only
        order the stack around the designer's boxes (see _stack_order).
        Without Hard nodes or added pictures the solve is the same as
        before them.
        """
        self.solver = kiwi.Solver()
        self.variables = {}
        self._last_rep = None          # the lowest signature row's lead (§3.63)
        reference = reference or {}
        fixed = list(fixed or [])

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

        reading = [n['node_id'] for n in singular_nodes]
        singular_nodes, below_row = self._stack_order(singular_nodes, repeating_nodes, reference, fixed)
        # Text heights give way only when a designer's box changed the stack
        # (a box out of its reading-order slot, or an added picture): a Hard
        # node left in its slot solves exactly as before (notes §3.58)
        has_hard = bool(fixed) or bool(below_row) or [n['node_id'] for n in singular_nodes] != reading
        # Rows a Soft picture sits in beside other elements (notes §3.61)
        rows = self._picture_rows(singular_nodes, reference) if has_hard else []
        row_of, followers = {}, set()
        for row in rows:
            for m in row['members']:
                row_of[m['node_id']] = row
            followers |= {m['node_id'] for m in row['followers']}

        locked_coordinates = set()
        region_centre = (self.left_bound + self.right_bound) / 2.0

        # 1. Singular Nodes Initialization and Alignment
        for node in singular_nodes + below_row:
            node_id = node['node_id']
            tensor_w = self._fit_width(node)
            tensor_h = float(node['bbox'][3])

            elastic = (has_hard and node.get('constraint_type') != "Hard"
                       and node.get('structural_class', 'text_node') == 'text_node')
            picture = node.get('structural_class') == 'decor' and node.get('constraint_type') != "Hard"
            current_var = self._initialize_node_variables(node_id, tensor_w, tensor_h, elastic=elastic,
                                                          picture=picture)
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
                row = row_of.get(node_id)
                if row is not None:
                    # in a row: the row is placed as a whole (_row_constraints);
                    # its lead keeps the axis as a preference when a Hard
                    # member fixes where the row is
                    if node_id not in followers and row['hard']:
                        target_x = (self.left_bound if self.align == "left"
                                    else max(self.left_bound, region_centre - tensor_w / 2.0))
                        self.solver.addConstraint((current_var['left'] == target_x) | kiwi.strength.medium)
                elif self.align == "left":
                    self.solver.addConstraint((current_var['left'] == self.left_bound) | kiwi.strength.strong)
                elif picture:    # centred whatever size it shrinks to
                    self.solver.addConstraint((current_var['left'] + current_var['right'] == 2.0 * region_centre)
                                              | kiwi.strength.strong)
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

        # 2. Strict Top-to-Bottom Stacking (Non-Overlap). Around a designer's
        # boxes (notes §3.59) the Soft nodes form the chain, and each Hard box
        # pushes only the nearest Soft node above and below it that shares
        # its columns: what sits beside a box can share its height (a logo
        # beside the logos the designer placed).
        chain = ([n for n in singular_nodes if n.get('constraint_type') != "Hard" and n['node_id'] not in followers]
                 if has_hard else singular_nodes)
        if has_hard:
            loose = {m['node_id'] for row in rows if row['lead'] is None for m in row['followers']}
            self._stack_around_boxes(singular_nodes, chain, region_centre, loose, reference)
            for row in rows:
                self._row_constraints(row, chain, region_centre, reference)
        for i in range(1, len(singular_nodes)) if not has_hard else ():
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

            # Signature blocks the designer moved form rows, as the logos do
            # (notes §3.63): blocks at about one height are a row; a block
            # moved well above or below the others is a row of its own, and
            # stays one when released. Without a moved block, or rows from
            # earlier moves, the single row is as before.
            sig_rows = self._signature_rows(repeating_nodes, reference)
            self._last_rep = None
            sequence = [] if (len(sig_rows) > 1 or any(n.get('constraint_type') == "Hard" for n in repeating_nodes)) \
                else list(enumerate(repeating_nodes))
            if not sequence:
                self._place_signature_rows(sig_rows, {n['node_id']: w for n, w in zip(repeating_nodes, widths)},
                                           chain, reference)
            first_rep_var = None
            cursor = self.left_bound + gap
            for i, node in sequence:
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

                # Must be strictly below the last singular element (the last
                # Soft one around a designer's boxes; the boxes after it are
                # kept above the row in _stack_around_boxes' terms below)
                if chain:
                    last_singular_var = self.variables[chain[-1]['node_id']]
                    self.solver.addConstraint((current_var['top'] >= last_singular_var['bottom'] + self.v_gap) | kiwi.strength.strong)
                    self.solver.addConstraint((current_var['top'] == last_singular_var['bottom'] + self.v_gap) | kiwi.strength.weak)
                    self.solver.addConstraint((current_var['top'] <= last_singular_var['bottom'] + self.max_gap) | kiwi.strength.strong)

            # A box after the last Soft element, still above the row: the
            # signatures stay below it
            if has_hard and chain:
                last = singular_nodes.index(chain[-1])
                for node in singular_nodes[last + 1:]:
                    hv = self.variables[node['node_id']]
                    for rep in repeating_nodes:
                        rv = self.variables[rep['node_id']]
                        self.solver.addConstraint((rv['top'] >= hv['bottom'] + self.v_gap) | kiwi.strength.strong)

            # A Hard box below the row (a picture at the foot of the page):
            # the signatures stay above it where they share columns
            for node in below_row:
                hv = self.variables[node['node_id']]
                hx0, hx1 = float(node['bbox'][0]), float(node['bbox'][0]) + float(node['bbox'][2])
                for rep in repeating_nodes:
                    rx0 = float(rep['bbox'][0]) if rep.get('constraint_type') == "Hard" else None
                    rv = self.variables[rep['node_id']]
                    if rx0 is None or min(hx1, rx0 + float(rep['bbox'][2])) - max(hx0, rx0) > 1:
                        self.solver.addConstraint((rv['bottom'] + self.v_gap <= hv['top']) | kiwi.strength.strong)

        # 4. Vertical balance — equal top and bottom margins for the whole
        # stack (top_gap == bottom_gap, i.e. first.top + last.bottom == H).
        # A standard design rule expressed as a soft constraint (Chapter 3,
        # p.39, Formulas 3.3/3.5). `strong` when nothing else decides where
        # the stack sits (baseline mode: without it the stack collapsed onto
        # the top margin); `weak` when the GNN's structure-mapped positions
        # carry the master's own composition (notes §3.26), so they decide
        # instead. Hard (manual) constraints stay `required` either way.
        if (chain or repeating_nodes) and self.balance:
            first_var = self.variables[(chain or repeating_nodes)[0]['node_id']]
            last_var = self.variables[getattr(self, '_last_rep', None) or (repeating_nodes or chain)[-1]['node_id']]
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
        for node in fixed:                             # the designer's pictures, updated in place
            if node['node_id'] in self.variables and node.get('constraint_type') != "Hard":
                v = self.variables[node['node_id']]
                node['bbox'] = [round(v['left'].value(), 2), round(v['top'].value(), 2),
                                round(v['right'].value() - v['left'].value(), 2),
                                round(v['bottom'].value() - v['top'].value(), 2)]

        return resolved_nodes

    @staticmethod
    def _picture_rows(order, reference):
        """
        The rows a Soft picture sits in (notes §3.61): a picture the designer
        released, or added from the panel, that was beside other elements
        (sharing at least half its height with them, not its columns) stays
        in a row with them. Returns [{"members" left to right, "hard", "lead",
        "anchor", "followers"}]: the lead is the row's own Soft element of the
        format (it keeps its place in the stack), the anchor fixes the row's
        line (a Hard member, else the lead), the followers are placed in the
        row beside them.
        """
        box = lambda n: [float(v) for v in reference.get(n['node_id'], n['bbox'])]
        pictures = [n for n in order if n.get('structural_class') == 'decor' and n.get('constraint_type') != "Hard"]
        if not pictures:
            return []
        parent = {n['node_id']: n['node_id'] for n in order}

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def beside(a, b):
            ax, ay, aw, ah = box(a)
            bx, by, bw, bh = box(b)
            return (min(ay + ah, by + bh) - max(ay, by) >= 0.5 * min(ah, bh)
                    and min(ax + aw, bx + bw) - max(ax, bx) <= 1)

        for p in pictures:
            for n in order:
                if n is not p and beside(p, n):
                    parent[find(p['node_id'])] = find(n['node_id'])
        groups = {}
        for n in order:
            groups.setdefault(find(n['node_id']), []).append(n)
        rows = []
        for members in groups.values():
            if len(members) < 2 or not any(m in pictures for m in members):
                continue
            hard = [m for m in members if m.get('constraint_type') == "Hard"]
            soft = [m for m in members if m.get('constraint_type') != "Hard"]
            lead = next((m for m in soft if m.get('structural_class') != 'decor'), None)
            if lead is None and not hard:
                lead = soft[0]
            rows.append({"members": sorted(members, key=lambda m: box(m)[0]), "hard": hard, "lead": lead,
                         "anchor": hard[0] if hard else lead,
                         "followers": [m for m in soft if m is not lead]})
        return rows

    def _row_constraints(self, row, chain, region_centre, reference):
        """One row of the stack (notes §3.61): its members side by side, left
        to right as they were, with one even gap between them, on the
        anchor's centre line; centred on the axis (or at the left edge) as a
        whole unless a Hard member fixes where it is. Followers keep clear of
        the elements above and below the lead."""
        members = row['members']
        var = lambda n: self.variables[n['node_id']]
        box = lambda n: [float(v) for v in reference.get(n['node_id'], n['bbox'])]
        gaps = [box(b)[0] - (box(a)[0] + box(a)[2]) for a, b in zip(members, members[1:])]
        gap = kiwi.Variable(f"row_gap_{members[0]['node_id']}")
        self.solver.addConstraint(gap >= 8.0)
        self.solver.addConstraint((gap == max(8.0, sum(gaps) / len(gaps))) | kiwi.strength.weak)
        for a, b in zip(members, members[1:]):
            if a.get('constraint_type') == "Hard" and b.get('constraint_type') == "Hard":
                continue
            self.solver.addConstraint((var(b)['left'] == var(a)['right'] + gap) | kiwi.strength.strong)
        anchor = var(row['anchor'])
        for m in members:
            if m is not row['anchor'] and m.get('constraint_type') != "Hard":
                self.solver.addConstraint((var(m)['top'] + var(m)['bottom'] == anchor['top'] + anchor['bottom'])
                                          | kiwi.strength.strong)
        if not row['hard']:
            first, last = var(members[0]), var(members[-1])
            if self.align == "left":
                self.solver.addConstraint((first['left'] == self.left_bound) | kiwi.strength.strong)
            else:
                self.solver.addConstraint((first['left'] + last['right'] == 2.0 * region_centre)
                                          | kiwi.strength.strong)
        lead = row['lead']
        if lead is not None and lead in chain:
            i = chain.index(lead)
            prev, nxt = (chain[i - 1] if i else None), (chain[i + 1] if i + 1 < len(chain) else None)
            for f in row['followers']:
                if prev is not None:
                    self.solver.addConstraint((var(f)['top'] >= var(prev)['bottom'] + self.v_gap)
                                              | kiwi.strength.strong)
                if nxt is not None:
                    self.solver.addConstraint((var(nxt)['top'] >= var(f)['bottom'] + self.v_gap)
                                              | kiwi.strength.strong)

    @staticmethod
    def _signature_rows(reps, reference):
        """The signature blocks in rows, top to bottom (notes §3.63): blocks
        sharing at least half their height (on the canvas before the event)
        are one row."""
        box = lambda n: [float(v) for v in reference.get(n['node_id'], n['bbox'])]
        rows = []
        for n in sorted(reps, key=lambda n: box(n)[1]):
            _, y, _, h = box(n)
            for row in rows:
                _, ry, _, rh = box(row[0])
                if min(y + h, ry + rh) - max(y, ry) >= 0.5 * min(h, rh):
                    row.append(n)
                    break
            else:
                rows.append([n])
        return [sorted(row, key=lambda n: box(n)[0]) for row in rows]

    def _place_signature_rows(self, rows, width, chain, reference):
        """Places signature rows (notes §3.63). In a row, a Hard block holds
        its place and the Soft ones spread evenly beside it (_spread_row), at
        its height; a row of Soft blocks spreads across the region. The first
        row sits below the content, each next row below the one above."""
        prev, prev_lead = [], None
        for row in rows:
            xs = self._spread_row(row, [width[n['node_id']] for n in row], reference)
            ordered = ([n for n in row if n.get('constraint_type') == "Hard"]
                       + [n for n in row if n.get('constraint_type') != "Hard"])
            lead = None
            for n in ordered:
                v = self._initialize_node_variables(n['node_id'], width[n['node_id']], float(n['bbox'][3]))
                if n.get('constraint_type') == "Hard":
                    self.solver.addConstraint(v['left'] == float(n['bbox'][0]))
                    self.solver.addConstraint(v['top'] == float(n['bbox'][1]))
                else:
                    self.solver.addConstraint((v['left'] == xs[n['node_id']]) | kiwi.strength.strong)
                    if lead is not None:
                        self.solver.addConstraint((v['top'] == lead['top']) | kiwi.strength.strong)
                lead = lead or v
            above = prev or ([self.variables[chain[-1]['node_id']]] if chain else [])
            for n in ordered:
                v = self.variables[n['node_id']]
                for a in above:
                    self.solver.addConstraint((v['top'] >= a['bottom'] + self.v_gap) | kiwi.strength.strong)
            ref = prev_lead or (above[0] if above else None)
            if ref is not None:
                self.solver.addConstraint((lead['top'] == ref['bottom'] + self.v_gap) | kiwi.strength.weak)
                self.solver.addConstraint((lead['top'] <= ref['bottom'] + self.max_gap) | kiwi.strength.strong)
            prev, prev_lead = [self.variables[n['node_id']] for n in ordered], lead
            self._last_rep = ordered[0]['node_id']

    def _spread_row(self, reps, widths, reference):
        """{node_id: left} of the Soft signature blocks when the designer
        moved one or more (notes §3.61): the Hard ones hold their places and
        split the row into stretches, and the Soft ones spread evenly in the
        stretch they were in (equal gaps, edges included)."""
        width = {n['node_id']: w for n, w in zip(reps, widths)}
        hard = sorted((n for n in reps if n.get('constraint_type') == "Hard"), key=lambda n: float(n['bbox'][0]))
        cuts = [(float(n['bbox'][0]), float(n['bbox'][0]) + float(n['bbox'][2])) for n in hard]
        edges = [self.left_bound] + [v for c in cuts for v in c] + [self.right_bound]
        stretches = [[] for _ in range(len(cuts) + 1)]
        for n in reps:
            if n.get('constraint_type') != "Hard":
                x, _, w, _ = (float(v) for v in reference.get(n['node_id'], n['bbox']))
                stretches[sum(1 for c0, c1 in cuts if (c0 + c1) / 2.0 < x + w / 2.0)].append(n)
        out = {}
        for k, members in enumerate(stretches):
            start, end = edges[2 * k], edges[2 * k + 1]
            g = max(15.0, (end - start - sum(width[m['node_id']] for m in members)) / (len(members) + 1))
            cursor = start + g
            for m in members:
                out[m['node_id']] = cursor
                cursor += width[m['node_id']] + g
        return out

    def _stack_around_boxes(self, order, chain, region_centre, loose=(), reference=None):
        """
        The stacking constraints when a designer's box changed the stack
        (notes §3.59). `order` is the whole stack top to bottom; `chain` its
        Soft nodes, which stack one under the next as before. Each Hard box
        keeps clear of the nearest Soft node above and below it that shares
        its columns (where a Soft node will sit across: the region's axis,
        or its left edge); a gap that a box sits in may stretch by the box.
        """
        reference = reference or {}

        def span(n):
            x, _, w, _ = (float(v) for v in n['bbox'])
            if n.get('constraint_type') == "Hard":
                return x, x + w
            if n['node_id'] in loose:     # a picture in a Hard box's row: about where it was
                x, _, w, _ = (float(v) for v in reference.get(n['node_id'], n['bbox']))
                return x, x + w
            x0 = self.left_bound if self.align == "left" else max(self.left_bound, region_centre - w / 2.0)
            return x0, x0 + w

        def shares(a, b):
            (a0, a1), (b0, b1) = span(a), span(b)
            return min(a1, b1) - max(a0, b0) > 1

        pos = {n['node_id']: i for i, n in enumerate(order)}
        for prev, curr in zip(chain, chain[1:]):
            pv, cv = self.variables[prev['node_id']], self.variables[curr['node_id']]
            between = order[pos[prev['node_id']] + 1:pos[curr['node_id']]]
            room = sum(float(b['bbox'][3]) + self.default_vgap for b in between)
            self.solver.addConstraint((cv['top'] >= pv['bottom'] + self.v_gap) | kiwi.strength.strong)
            self.solver.addConstraint((cv['top'] == pv['bottom'] + self.v_gap) | kiwi.strength.weak)
            self.solver.addConstraint((cv['top'] <= pv['bottom'] + self.max_gap + room) | kiwi.strength.strong)
        for box in (n for n in order if n.get('constraint_type') == "Hard" or n['node_id'] in loose):
            i, bv = pos[box['node_id']], self.variables[box['node_id']]
            above = next((n for n in reversed(chain) if pos[n['node_id']] < i and shares(n, box)), None)
            below = next((n for n in chain if pos[n['node_id']] > i and shares(n, box)), None)
            if above is not None:
                self.solver.addConstraint((self.variables[above['node_id']]['bottom'] + self.v_gap <= bv['top'])
                                          | kiwi.strength.strong)
            if below is not None:
                self.solver.addConstraint((self.variables[below['node_id']]['top'] >= bv['bottom'] + self.v_gap)
                                          | kiwi.strength.strong)
