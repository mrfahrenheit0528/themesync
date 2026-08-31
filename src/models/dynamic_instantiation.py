import json
import os

class NodeInstantiator:
    def __init__(self, canvas_width=1200, canvas_height=900):
        """
        Initializes the instantiator with dynamic canvas dimensions.
        Supports arbitrary target sizes (e.g., A4, CR80).
        """
        self.canvas_w = float(canvas_width)
        self.canvas_h = float(canvas_height)

    def _calculate_baseline_tensor(self, hierarchy_index, struct_class, domain_context):
        """
        Assigns proportional geometric tensors relative to the current canvas dimensions 
        and the structural domain (Certificate vs. ID).
        """
        if domain_context == "identification_card":
            # Vertical ID Stack Logic (CR80 Portrait)
            if struct_class == "image_node":
                if hierarchy_index == 0:  # Institution Logo
                    logo_dim = min(self.canvas_w * 0.22, self.canvas_h * 0.12)
                    return [logo_dim, logo_dim]
                elif hierarchy_index == 1:  # ID Photo (1:1 ratio)
                    photo_dim = min(self.canvas_w * 0.45, self.canvas_h * 0.28)
                    return [photo_dim, photo_dim]
                elif hierarchy_index == 5:  # Barcode Block
                    return [self.canvas_w * 0.75, self.canvas_h * 0.08]
            elif struct_class == "text_node":
                if hierarchy_index == 2:  # Student Name
                    return [self.canvas_w * 0.85, self.canvas_h * 0.055]
                elif hierarchy_index == 3:  # Department / Course
                    return [self.canvas_w * 0.80, self.canvas_h * 0.045]
                else:  # ID Numbers / Labels
                    return [self.canvas_w * 0.65, self.canvas_h * 0.035]

        else:
            # Horizontal Academic Certificate Logic (A4 Landscape / 4:3)
            if struct_class == "repeating_group":
                # Signature blocks (3 blocks across bottom)
                return [self.canvas_w * 0.22, self.canvas_h * 0.075]
            if struct_class == "image_node" and hierarchy_index == 0:
                logo_dim = min(self.canvas_w * 0.09, self.canvas_h * 0.11)
                return [logo_dim, logo_dim]
            
            if hierarchy_index == 1:  # Issuing Organization
                return [self.canvas_w * 0.70, self.canvas_h * 0.04]
            elif hierarchy_index == 2:  # Certificate Title
                return [self.canvas_w * 0.80, self.canvas_h * 0.075]
            elif hierarchy_index == 3:  # Presentation Line
                return [self.canvas_w * 0.55, self.canvas_h * 0.03]
            elif hierarchy_index == 4:  # Student / Recipient Name
                return [self.canvas_w * 0.75, self.canvas_h * 0.065]
            elif hierarchy_index == 5:  # Citation Body
                return [self.canvas_w * 0.80, self.canvas_h * 0.07]
            elif hierarchy_index == 6:  # Date Issued
                return [self.canvas_w * 0.35, self.canvas_h * 0.028]
            elif hierarchy_index == 7:  # Certificate ID
                return [self.canvas_w * 0.35, self.canvas_h * 0.028]
            else:
                return [self.canvas_w * 0.40, self.canvas_h * 0.035]

        # System Failsafe fallback
        return [self.canvas_w * 0.35, self.canvas_h * 0.04]

    def instantiate_payload(self, payload_path):
        if not os.path.exists(payload_path):
            raise FileNotFoundError(f"Payload schema not found at {payload_path}")
            
        with open(payload_path, 'r') as file:
            payload = json.load(file)
            
        domain = payload.get("domain_context", "academic_certificate")
        schema = payload.get("variable_schema", {})
        instantiated_nodes = []
        
        for var_name, properties in schema.items():
            struct_class = properties.get("structural_class")
            hierarchy = properties.get("spatial_hierarchy", 99)
            
            tensor_w, tensor_h = self._calculate_baseline_tensor(hierarchy, struct_class, domain)
            count = properties.get("instantiation_count", 1)
            
            for i in range(count):
                node_id = f"{var_name}_{i}" if count > 1 else var_name
                
                node_data = {
                    "node_id": node_id,
                    "semantic_category": "dynamic_variable",
                    "structural_class": struct_class,
                    "spatial_hierarchy": hierarchy,
                    "bbox": [0.0, 0.0, round(tensor_w, 2), round(tensor_h, 2)], 
                    "constraint_type": "Soft"
                }
                instantiated_nodes.append(node_data)
                
        return instantiated_nodes

def execute_instantiation():
    print("Initializing Dynamic Node Instantiation (Multi-Format)...")
    cert_instantiator = NodeInstantiator(canvas_width=1200, canvas_height=900)
    cert_nodes = cert_instantiator.instantiate_payload("data/raw/academic_payload.json")
    for node in cert_nodes:
        print(f" -> {node['node_id']} | Tensor: [{node['bbox'][2]}, {node['bbox'][3]}]")

if __name__ == "__main__":
    execute_instantiation()