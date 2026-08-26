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
        Assigns geometric tensors relative to the current canvas dimensions 
        and the structural domain (Certificate vs. ID).
        """
        if domain_context == "identification_card":
            # Vertical ID Stack Logic
            if struct_class == "image_node":
                if hierarchy_index == 0:  # Institution Logo
                    return [self.canvas_w * 0.3, self.canvas_w * 0.3]
                elif hierarchy_index == 1:  # ID Photo (1:1 aspect ratio mapping)
                    return [self.canvas_w * 0.5, self.canvas_w * 0.5]
                elif hierarchy_index == 5:  # Barcode Block
                    return [self.canvas_w * 0.8, self.canvas_h * 0.1]
            elif struct_class == "text_node":
                if hierarchy_index == 2:  # Student Name
                    return [self.canvas_w * 0.8, self.canvas_h * 0.08]
                else:  # Subtitles / ID Numbers
                    return [self.canvas_w * 0.6, self.canvas_h * 0.05]

        else:
            # Horizontal Certificate Logic
            if struct_class == "repeating_group":
                return [self.canvas_w * 0.2, self.canvas_h * 0.1]
            if struct_class == "image_node" and hierarchy_index == 0:
                return [self.canvas_w * 0.15, self.canvas_w * 0.15]
            
            if hierarchy_index == 1:
                return [self.canvas_w * 0.5, self.canvas_h * 0.08]
            elif hierarchy_index == 2:
                return [self.canvas_w * 0.6, self.canvas_h * 0.15]
            elif hierarchy_index == 4:
                return [self.canvas_w * 0.5, self.canvas_h * 0.1]
            else:
                return [self.canvas_w * 0.3, self.canvas_h * 0.05]

        # System Failsafe fallback
        return [self.canvas_w * 0.3, self.canvas_h * 0.05]

    def instantiate_payload(self, payload_path):
        if not os.path.exists(payload_path):
            raise FileNotFoundError(f"Payload schema not found at {payload_path}")
            
        with open(payload_path, 'r') as file:
            payload = json.load(file)
            
        # Extract the domain context to drive the tensor calculation
        domain = payload.get("domain_context", "academic_certificate")
        schema = payload.get("variable_schema", {})
        instantiated_nodes = []
        
        for var_name, properties in schema.items():
            struct_class = properties.get("structural_class")
            hierarchy = properties.get("spatial_hierarchy", 99)
            
            # Compute dynamic width and height 
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
    
    # 1. Test Horizontal Certificate (Standard A4 Landscape: 3508 x 2480 pixels)
    print("\n--- Testing Horizontal Certificate (A4 Dimension) ---")
    cert_instantiator = NodeInstantiator(canvas_width=3508, canvas_height=2480)
    cert_nodes = cert_instantiator.instantiate_payload("data/raw/academic_payload.json")
    for node in cert_nodes:
        print(f" -> {node['node_id']} | Tensor: [{node['bbox'][2]}, {node['bbox'][3]}]")
        
    # 2. Test Vertical ID (Standard CR80 Portrait: 638 x 1014 pixels)
    print("\n--- Testing Vertical ID (CR80 Dimension) ---")
    id_instantiator = NodeInstantiator(canvas_width=638, canvas_height=1014)
    id_nodes = id_instantiator.instantiate_payload("data/raw/id_payload.json")
    for node in id_nodes:
        print(f" -> {node['node_id']} | Tensor: [{node['bbox'][2]}, {node['bbox'][3]}]")

if __name__ == "__main__":
    execute_instantiation()