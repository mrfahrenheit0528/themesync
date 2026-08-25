import datasets as ds

def extract_spatial_tensors(example):
    """
    Deserializes Hugging Face columnar annotation arrays to extract bounding box 
    geometries and semantic identities prior to GNN processing.
    """
    formatted_nodes = []
    
    # 1. Process standard graphical annotations
    annotations = example.get('annotations', {})
    
    if isinstance(annotations, dict):
        # Handle columnar format (Dict of Lists)
        bboxes = annotations.get('bbox', [])
        categories = annotations.get('supercategory', [])
        
        # Map the parallel arrays
        for bbox, category in zip(bboxes, categories):
            formatted_nodes.append({
                'semantic_category': category,
                'bbox': bbox
            })
    elif isinstance(annotations, list):
        # Fallback for row-based format (List of Dicts)
        for ann in annotations:
            if isinstance(ann, dict):
                formatted_nodes.append({
                    'semantic_category': ann.get('supercategory', 'unknown'),
                    'bbox': ann.get('bbox', [0, 0, 0, 0])
                })

    # 2. Process text-specific annotations
    text_annotations = example.get('text_annotations', {})
    
    if isinstance(text_annotations, dict):
        text_bboxes = text_annotations.get('bbox', [])
        for bbox in text_bboxes:
            formatted_nodes.append({
                'semantic_category': 'text',
                'bbox': bbox
            })
    elif isinstance(text_annotations, list):
        for txt in text_annotations:
            if isinstance(txt, dict):
                formatted_nodes.append({
                    'semantic_category': 'text',
                    'bbox': txt.get('bbox', [0, 0, 0, 0])
                })
                
    return {'extracted_nodes': formatted_nodes}

def run_preprocessing():
    print("Loading cached CGL-Dataset V2...")
    dataset = ds.load_dataset("creative-graphic-design/CGL-Dataset-v2")
    
    print("Executing columnar deserialization and spatial extraction...")
    # Apply extraction mapping to the dataset
    processed_dataset = dataset.map(extract_spatial_tensors)
    
    # Execute noise reduction: Drop administrative and raw nested columns
    columns_to_remove = ['image_id', 'file_name', 'annotations', 'text_annotations', 'text_features']
    processed_dataset = processed_dataset.remove_columns(columns_to_remove)
    
    print("Preprocessing complete. Output tensor structure:")
    print(processed_dataset)
    
    return processed_dataset

if __name__ == "__main__":
    run_preprocessing()