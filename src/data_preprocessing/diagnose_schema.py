import datasets as ds

def run_diagnostic():
    print("Loading raw CGL-Dataset V2...")
    dataset = ds.load_dataset("creative-graphic-design/CGL-Dataset-v2")
    
    # Isolate the first layout for structural inspection
    example = dataset['train'][0]
    
    print("\n[DIAGNOSTIC] Analyzing 'annotations' column...")
    ann = example.get('annotations')
    print(f"Data Type: {type(ann)}")
    if isinstance(ann, dict):
        print(f"Available Keys: {list(ann.keys())}")
        for k, v in ann.items():
            print(f" -> {k}: contains {len(v) if isinstance(v, list) else 'N/A'} elements")
            
    print("\n[DIAGNOSTIC] Analyzing 'text_annotations' column...")
    txt = example.get('text_annotations')
    print(f"Data Type: {type(txt)}")
    if isinstance(txt, dict):
        print(f"Available Keys: {list(txt.keys())}")
        for k, v in txt.items():
            print(f" -> {k}: contains {len(v) if isinstance(v, list) else 'N/A'} elements")

if __name__ == "__main__":
    run_diagnostic()