import json
import os

class AestheticSVGRenderer:
    def __init__(self, canvas_width=1200, canvas_height=900, original_filename="master_template"):
        self.canvas_w = canvas_width
        self.canvas_h = canvas_height
        self.original_filename = original_filename
        
        # Hardcoded Visual DNA for prototype rendering
        self.palette = {
            "primary": "#003366",
            "accent": "#FFCC00",
            "background": "#FFFFFF"
        }
        self.typography = {
            "font_family": "Montserrat, sans-serif",
            "font_weight": "700"
        }

    def render_layout(self, json_filepath, output_dir="data/rendered/"):
        os.makedirs(output_dir, exist_ok=True)
        
        if not os.path.exists(json_filepath):
            print(f"Error: Target layout {json_filepath} not found.")
            return
            
        with open(json_filepath, 'r') as f:
            nodes = json.load(f)
            
        svg_elements = []
        # 1. Inject Background Canvas
        svg_elements.append(
            f'<rect width="{self.canvas_w}" height="{self.canvas_h}" fill="{self.palette["background"]}" />'
        )
        
        # 2. Map Tensors to Visual Nodes
        for node in nodes:
            x, y, w, h = node['bbox']
            node_id = node['node_id']
            struct_class = node.get('structural_class', 'text_node')
            
            if struct_class == "image_node":
                # Render image placeholders with accent colors
                svg_elements.append(
                    f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
                    f'fill="{self.palette["accent"]}" stroke="{self.palette["primary"]}" stroke-width="2" opacity="0.8" />'
                )
                svg_elements.append(
                    f'<text x="{x + w/2}" y="{y + h/2}" font-family="{self.typography["font_family"]}" '
                    f'font-size="14" fill="{self.palette["primary"]}" text-anchor="middle" dominant-baseline="middle">'
                    f'[{node_id}]</text>'
                )
            elif struct_class == "text_node":
                # Render typography with primary brand colors
                svg_elements.append(
                    f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
                    f'fill="none" stroke="{self.palette["primary"]}" stroke-width="1" stroke-dasharray="4" />'
                )
                svg_elements.append(
                    f'<text x="{x + w/2}" y="{y + h/2}" font-family="{self.typography["font_family"]}" '
                    f'font-weight="{self.typography["font_weight"]}" font-size="24" fill="{self.palette["primary"]}" '
                    f'text-anchor="middle" dominant-baseline="middle">{node_id}</text>'
                )
                
        # 3. Compile Deterministic Vector Structure
        svg_content = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.canvas_w} {self.canvas_h}" '
            f'width="{self.canvas_w}" height="{self.canvas_h}">\n'
            + "\n".join(svg_elements)
            + '\n</svg>'
        )
        
        # Output utilizing the original filename convention
        output_path = os.path.join(output_dir, f"{self.original_filename}_rendered.svg")
        with open(output_path, 'w') as f:
            f.write(svg_content)
            
        print(f" -> Aesthetic Rendering Complete: {output_path}")

def execute_rendering():
    print("Initializing Aesthetic Rendering Pipeline...")
    
    # Target the optimal mathematically ranked output
    target_json = "data/processed/Candidate_0_GNN_Baseline.json"
    
    # Initialize renderer preserving the original canvas filename mapping
    renderer = AestheticSVGRenderer(original_filename="CGL_Master_Canvas")
    renderer.render_layout(target_json)

if __name__ == "__main__":
    execute_rendering()