import json
import os

class AestheticSVGRenderer:
    def __init__(self, canvas_width=1200, canvas_height=900, original_filename="master_template"):
        self.canvas_w = canvas_width
        self.canvas_h = canvas_height
        self.original_filename = original_filename
        
        # 1. The Hybrid Visual DNA (Extracted Stylistic Markers & Typography)
        self.palette = {
            "primary": "#003366",   # Extracted Centroid 1
            "accent": "#FFCC00",    # Extracted Centroid 2
            "background": "#FFFFFF" # Extracted Centroid 3
        }
        self.typography = {
            "font_family": "Montserrat, sans-serif",
            "font_weight": "700"
        }
        
        # 2. Dynamic Content Payload Translation
        # Maps the abstract schema tags to realistic strings for expert evaluation
        self.mock_data = {
            "{{Institution_Logo}}": "CSPC LOGO",
            "{{Issuing_Organization}}": "CAMARINES SUR POLYTECHNIC COLLEGES",
            "{{Certificate_Title}}": "CERTIFICATE OF ACHIEVEMENT",
            "{{Presentation_Line}}": "is proudly presented to",
            "{{Student_Name}}": "Guiller Angelo Hermoso",
            "{{Citation_Body}}": "For outstanding academic performance and successful completion of the automated orchestration framework thesis project.",
            "{{Date_Issued}}": "August 27, 2026",
            "{{Certificate_ID}}": "ID: CSPC-2026-001",
            "{{Signature_Blocks_0}}": "Dean, College of Computer Studies",
            "{{Signature_Blocks_1}}": "Thesis Adviser",
            "{{Signature_Blocks_2}}": "College President"
        }

    def _clean_node_id(self, node_id):
        return self.mock_data.get(node_id, node_id.replace("{", "").replace("}", "").replace("_", " "))

    def render_layout(self, json_filepath, output_dir="data/rendered/"):
        os.makedirs(output_dir, exist_ok=True)
        
        if not os.path.exists(json_filepath):
            print(f"Error: Target layout {json_filepath} not found.")
            return
            
        with open(json_filepath, 'r') as f:
            nodes = json.load(f)
            
        svg_elements = []
        
        # 3. Inject Extracted Background Canvas
        svg_elements.append(
            f'<rect width="{self.canvas_w}" height="{self.canvas_h}" fill="{self.palette["background"]}" />'
        )
        
        # 4. Map Tensors to Fully Populated Visual Nodes
        for node in nodes:
            x, y, w, h = node['bbox']
            node_id = node['node_id']
            struct_class = node.get('structural_class', 'text_node')
            
            content = self._clean_node_id(node_id)
            
            if struct_class == "image_node":
                # Render image assets with the extracted accent color
                svg_elements.append(
                    f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{self.palette["accent"]}" rx="8" />'
                )
                svg_elements.append(
                    f'<text x="{x + w/2}" y="{y + h/2}" font-family="{self.typography["font_family"]}" '
                    f'font-weight="bold" font-size="16" fill="{self.palette["primary"]}" '
                    f'text-anchor="middle" dominant-baseline="middle">{content}</text>'
                )
                
            elif struct_class == "text_node":
                # Dynamically calculate font size relative to the GNN's predicted geometric height
                font_size = min(h * 0.6, 36) if "Title" not in node_id else min(h * 0.8, 52)
                font_weight = "bold" if "Title" in node_id or "Name" in node_id else "normal"
                
                svg_elements.append(
                    f'<text x="{x + w/2}" y="{y + h/2}" font-family="{self.typography["font_family"]}" '
                    f'font-weight="{font_weight}" font-size="{font_size}" fill="{self.palette["primary"]}" '
                    f'text-anchor="middle" dominant-baseline="middle">{content}</text>'
                )
                
            elif struct_class == "repeating_group":
                # Render signature blocks with a designated signature line and subtitle
                line_y = y + h * 0.6
                svg_elements.append(
                    f'<line x1="{x}" y1="{line_y}" x2="{x + w}" y2="{line_y}" stroke="{self.palette["primary"]}" stroke-width="2" />'
                )
                svg_elements.append(
                    f'<text x="{x + w/2}" y="{line_y + 20}" font-family="{self.typography["font_family"]}" '
                    f'font-size="14" fill="{self.palette["primary"]}" text-anchor="middle">{content}</text>'
                )
                
        # 5. Compile Deterministic Vector Structure
        svg_content = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.canvas_w} {self.canvas_h}" '
            f'width="{self.canvas_w}" height="{self.canvas_h}">\n'
            + "\n".join(svg_elements)
            + '\n</svg>'
        )
        
        # Output utilizing the original filename convention
        output_path = os.path.join(output_dir, f"{self.original_filename}_populated.svg")
        with open(output_path, 'w') as f:
            f.write(svg_content)
            
        print(f" -> Fully Populated Rendering Complete: {output_path}")

def execute_rendering():
    print("Initializing Fully Populated Aesthetic Rendering Pipeline...")
    
    # Target the optimal, mathematically ranked output
    target_json = "data/processed/Candidate_0_GNN_Baseline.json"
    
    # Initialize renderer preserving the original canvas filename mapping
    renderer = AestheticSVGRenderer(original_filename="CGL_Master_Canvas")
    renderer.render_layout(target_json)

if __name__ == "__main__":
    execute_rendering()