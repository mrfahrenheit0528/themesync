import datasets as ds

def download_dataset():
    print("Initializing CGL-Dataset V2 ingestion...")
    # Load the dataset from Hugging Face
    dataset = ds.load_dataset("creative-graphic-design/CGL-Dataset-v2")
    
    print(f"Dataset successfully loaded. Configuration: {dataset}")
    return dataset

if __name__ == "__main__":
    download_dataset()