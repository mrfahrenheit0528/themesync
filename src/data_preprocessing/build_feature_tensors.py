import datasets as ds
import cv2
import torch
import multiprocess
from vision_extraction import VisionExtractor

# Force the 'spawn' method for Hugging Face's multiprocessing backend
try:
    multiprocess.set_start_method("spawn")
except RuntimeError:
    pass 

# Prevent OpenCV from locking CPU threads during parallel execution
cv2.setNumThreads(0)

# Global placeholder for lazy initialization
_worker_extractor = None

# 1. ADD 'rank' TO THE FUNCTION SIGNATURE
def build_tensors(example, rank):
    """
    Consolidates spatial JSON deserialization and computer vision extraction.
    Updated to align strictly with the validated CGL-Dataset V2 schema.
    """
    global _worker_extractor
    
    if _worker_extractor is None:
        # 2. ASSIGN THIS WORKER TO A SPECIFIC GPU
        num_gpus = torch.cuda.device_count()
        if num_gpus > 0:
            gpu_id = rank % num_gpus
            
            # This sets the default CUDA device for this specific spawned process
            torch.cuda.set_device(gpu_id)
            
            # NOTE: If your VisionExtractor takes an explicit device argument, pass it here:
            # _worker_extractor = VisionExtractor(n_colors=3, device=f"cuda:{gpu_id}")
            
        _worker_extractor = VisionExtractor(n_colors=3)

    formatted_nodes = []
    
    # Deserialize graphical and text annotations from the unified 'annotations' array
    annotations = example.get('annotations', {})
    
    if isinstance(annotations, dict):
        bboxes = annotations.get('bbox', [])
        categories = annotations.get('category', []) 
        
        for bbox, category in zip(bboxes, categories):
            formatted_nodes.append({
                'semantic_category': category,
                'bbox': bbox
            })
    elif isinstance(annotations, list):
        for ann in annotations:
            if isinstance(ann, dict):
                formatted_nodes.append({
                    'semantic_category': ann.get('category', 'unknown'),
                    'bbox': ann.get('bbox', [0, 0, 0, 0])
                })

    # Execute perceptual extraction using the worker-specific CUDA context
    image = example['image']
    centroids = _worker_extractor.extract_lab_centroids(image)
    saliency_weight = _worker_extractor.calculate_saliency_weight(image)

    return {
        'extracted_nodes': formatted_nodes,
        'extracted_color_centroids': centroids,
        'extracted_saliency_weight': saliency_weight
    }

def main():
    print("Loading raw CGL-Dataset V2 from cache...")
    dataset = ds.load_dataset("creative-graphic-design/CGL-Dataset-v2")
    
    # 3. DYNAMICALLY SCALE WORKERS (e.g., 2 workers per GPU to maximize throughput)
    num_gpus = max(1, torch.cuda.device_count())
    workers_per_gpu = 3 # Adjust this based on your GPU VRAM
    total_workers = num_gpus * workers_per_gpu

    print(f"Executing across {num_gpus} GPUs using {total_workers} workers...")
    
    processed_dataset = dataset.map(
        build_tensors,
        with_rank=True,       # 4. ENABLE RANK PASSING
        num_proc=total_workers, 
        remove_columns=['image_id', 'file_name', 'annotations', 'text_annotations', 'text_features']
    )
    
    output_path = "data/processed/cgl_tensor_dataset"
    print(f"\nSaving compiled tensors to {output_path}...")
    processed_dataset.save_to_disk(output_path)
    
    print("Phase 1 Extraction Complete.")

if __name__ == "__main__":
    main()