import cv2
import numpy as np
import torch

class VisionExtractor:
    def __init__(self, n_colors=3):
        """
        Initializes the GPU-accelerated K-Means and CPU-bound SIFT feature extraction modules.
        """
        self.n_colors = n_colors
        self.sift = cv2.SIFT_create()
        # Automatically target the first available RTX A5000
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    def extract_lab_centroids(self, image_array):
        """
        Converts images to CIE L*a*b* space and executes K-Means clustering 
        directly on the GPU utilizing PyTorch tensor operations.
        """
        img = np.array(image_array)
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
            
        img_resized = cv2.resize(img, (150, 150), interpolation=cv2.INTER_AREA)
        lab_image = cv2.cvtColor(img_resized, cv2.COLOR_RGB2LAB)
        
        # Flatten and convert to a PyTorch tensor on the GPU
        pixels = lab_image.reshape((-1, 3))
        pixels_tensor = torch.tensor(pixels, dtype=torch.float32, device=self.device)
        
        # GPU-Accelerated K-Means execution
        centroids = self._kmeans_cuda(pixels_tensor)
        return centroids

    def _kmeans_cuda(self, pixels_tensor, max_iter=100):
        """
        Internal mathematical solver for minimizing WCSS on CUDA hardware.
        """
        # Randomly initialize centroids
        idx = torch.randperm(pixels_tensor.shape[0], device=self.device)[:self.n_colors]
        centroids = pixels_tensor[idx]
        
        for _ in range(max_iter):
            # Calculate Euclidean distances using PyTorch cdist
            distances = torch.cdist(pixels_tensor, centroids)
            labels = torch.argmin(distances, dim=1)
            
            new_centroids = torch.zeros_like(centroids)
            for k in range(self.n_colors):
                mask = labels == k
                if mask.any():
                    new_centroids[k] = pixels_tensor[mask].mean(dim=0)
                else:
                    new_centroids[k] = centroids[k]
                    
            # Check for mathematical convergence
            if torch.allclose(centroids, new_centroids, atol=1e-4):
                break
            centroids = new_centroids
            
        # Return coordinates to CPU for JSON serialization
        return centroids.cpu().tolist()

    def calculate_saliency_weight(self, image_array):
        """
        Utilizes SIFT on the CPU to detect high-frequency keypoints.
        """
        img = np.array(image_array)
        if len(img.shape) == 3:
            gray_image = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray_image = img
            
        keypoints = self.sift.detect(gray_image, None)
        
        total_pixels = gray_image.shape[0] * gray_image.shape[1]
        density = len(keypoints) / total_pixels if total_pixels > 0 else 0
        normalized_weight = min(density / 0.05, 1.0)
        
        return normalized_weight