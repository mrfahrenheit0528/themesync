import json
import os

class NodeInstantiator:
    def __init__(self, base_canvas_width=1200, base_canvas_height=900):
        """
        Initializes the instantiator with standard 4:3 baseline dimensions.
        """
        self.canvas_w = base_canvas_width
        self.canvas_h = base_canvas_height
        
    def _calculate_baseline_tensor(self, hierarchy_index, struct_class):
        """
        Assigns worst-case baseline geometric tensors (w, h) based on the 
        Spatial Hierarchy Index to establish the Implicit Geometric Hierarchy.
        """
        if struct_class == "repeating_group":
            return [self.canvas_w * 0.2, self.canvas_h * 0.1]
            
        if struct_class == "image_node" and hierarchy_index == 0:
            # Institution Logo: Restrict to a compact, square-like bounding box
            return [self.canvas_w * 0.15, self.canvas_w * 0.15]
            
        # Calculate text nodes based on shifted hierarchy
        if hierarchy_index == 1:
            # Issuing Organization
            return [self.canvas_w * 0.5, self.canvas_h * 0.08]
        elif hierarchy_index == 2:
            # Certificate Title
            return [self.canvas_w * 0.6, self.canvas_h * 0.15]
        elif hierarchy_index == 4:
            # Student Name
            return [self.canvas_w * 0.5, self.canvas_h * 0.1]
        else:
            # Default fallback tensor for standard text lines (Presentation Line, Date, etc.)
            return [self.canvas_w * 0.3, self.canvas_h * 0.05]

    def instantiate_payload(self, payload_path):
        """
        Ingests the JSON schema and outputs functional mathematical nodes.
        """
        if not os.path.exists(payload_path):
            raise FileNotFoundError(f"Payload schema not found at {payload_path}")
            
        with open(payload_path, 'r') as file:
            payload = json.load(file)
            
        schema = payload.get("variable_schema", {})
        instantiated_nodes = []
        
        for var_name, properties in schema.items():
            struct_class = properties.get("structural_class")
            hierarchy = properties.get("spatial_hierarchy", 99)
            
            # Retrieve the mathematical tensor footprint
            tensor_w, tensor_h = self._calculate_baseline_tensor(hierarchy, struct_class)
            
            # Handle repeating elements (e.g., 3 separate signature blocks)
            count = properties.get("instantiation_count", 1)
            
            for i in range(count):
                node_id = f"{var_name}_{i}" if count > 1 else var_name
                
                # Initialize node at origin [0,0]; Cassowary will calculate actual [x,y] later
                node_data = {
                    "node_id": node_id,
                    "semantic_category": "dynamic_variable",
                    "structural_class": struct_class,
                    "spatial_hierarchy": hierarchy,
                    "bbox": [0.0, 0.0, tensor_w, tensor_h], 
                    "constraint_type": "Soft" # Defaults to Soft for algorithmic layout logic
                }
                instantiated_nodes.append(node_data)
                
        return instantiated_nodes

def execute_instantiation():
    print("Initializing Dynamic Node Instantiation...")
    instantiator = NodeInstantiator()
    
    payload_file = "data/raw/academic_payload.json"
    
    try:
        nodes = instantiator.instantiate_payload(payload_file)
        print(f"\nSuccessfully instantiated {len(nodes)} dynamic variables:")
        
        for node in nodes:
            print(f" -> Node: {node['node_id']} | Hierarchy: {node['spatial_hierarchy']} | Baseline Tensor [w, h]: [{node['bbox'][2]}, {node['bbox'][3]}]")
            
        print("\nImplicit Geometric Hierarchy established. Nodes are prepared for Cassowary CSP constraint solving.")
    except Exception as e:
        print(f"Instantiation Failure: {e}")

if __name__ == "__main__":
    execute_instantiation()