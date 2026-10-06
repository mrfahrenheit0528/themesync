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
        Converts images to CIE L*a*b* space and conditionally executes K-Means clustering.
        Includes a variance check to prevent algorithm failure on grayscale assets.
        """
        img = np.array(image_array)
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
            
        img_resized = cv2.resize(img, (150, 150), interpolation=cv2.INTER_AREA)
        lab_image = cv2.cvtColor(img_resized, cv2.COLOR_RGB2LAB)
        
        # Calculate statistical variance across the a* and b* chromatic channels
        a_variance = np.var(lab_image[:, :, 1])
        b_variance = np.var(lab_image[:, :, 2])
        epsilon = 1e-4 
        
        if a_variance < epsilon and b_variance < epsilon:
            # Fallback: Perform 1D clustering strictly on the L* (Luminance) channel via CPU
            l_channel = lab_image[:, :, 0].reshape(-1, 1)
            
            from sklearn.cluster import KMeans
            kmeans = KMeans(n_clusters=self.n_colors, random_state=42, n_init=10)
            kmeans.fit(l_channel)
            
            # Reconstruct the 3D centroids by padding a* and b* with 128.0 (neutral gray)
            safe_centroids = np.zeros((self.n_colors, 3))
            safe_centroids[:, 0] = kmeans.cluster_centers_.flatten()
            safe_centroids[:, 1] = 128.0 
            safe_centroids[:, 2] = 128.0
            
            return safe_centroids.tolist()
            
        else:
            # Chromatic variance is optimal; execute standard 3D clustering on the GPU.
            # k is not fixed — it is selected via the Elbow Method (Formula 3.1's
            # WCSS, evaluated across a small range of k) so the extracted palette
            # reflects the template's actual perceptual complexity rather than an
            # assumed constant cluster count.
            pixels = lab_image.reshape((-1, 3))
            pixels_tensor = torch.tensor(pixels, dtype=torch.float32, device=self.device)
            centroids = self._select_optimal_k_centroids(pixels_tensor)
            return centroids

    def _kmeans_cuda(self, pixels_tensor, k, max_iter=100, seed=0):
        """
        Internal mathematical solver for minimizing WCSS (Formula 3.1) on CUDA
        hardware for a given k. Returns the fitted centroids and their WCSS.

        The initial centroids are drawn with a seeded generator: unseeded, the
        same poster could get a different palette (even a different elbow k)
        on every run, which made the rendered colours, the Legibility
        Penalty and the winning candidate change between identical runs.
        """
        gen = torch.Generator(device=pixels_tensor.device)
        gen.manual_seed(seed)
        idx = torch.randperm(pixels_tensor.shape[0], device=pixels_tensor.device, generator=gen)[:k]
        centroids = pixels_tensor[idx]

        for _ in range(max_iter):
            # Calculate Euclidean distances using PyTorch cdist
            labels = torch.argmin(torch.cdist(pixels_tensor, centroids), dim=1)

            # Cluster means as one matrix product (a one-hot assignment
            # matrix times the pixels): no per-cluster loop, and no atomic
            # scatter-adds, whose summation order would vary between runs.
            onehot = torch.nn.functional.one_hot(labels, k).to(pixels_tensor.dtype)
            counts = onehot.sum(dim=0).unsqueeze(1)
            new_centroids = torch.where(counts > 0, (onehot.T @ pixels_tensor) / counts.clamp(min=1.0),
                                        centroids)

            # Check for mathematical convergence
            converged = torch.allclose(centroids, new_centroids, atol=1e-4)
            centroids = new_centroids
            if converged:
                break

        labels = torch.argmin(torch.cdist(pixels_tensor, centroids), dim=1)
        wcss = float(((pixels_tensor - centroids[labels]) ** 2).sum().item())

        # Return coordinates to CPU for JSON serialization
        return centroids.cpu().tolist(), wcss

    def _select_optimal_k_centroids(self, pixels_tensor, k_min=2, k_max=6, n_init=5):
        """
        Fits K-Means across k in [k_min, k_max], then selects k via the Elbow
        Method: the k whose WCSS point has the greatest perpendicular distance
        from the chord connecting the first and last points of the WCSS-vs-k
        decay curve (the standard "knee" heuristic). Each k keeps the best
        (lowest-WCSS) of `n_init` seeded initialisations, like the grayscale
        path's scikit-learn KMeans(n_init=10, random_state=42).
        """
        runs = {k: min((self._kmeans_cuda(pixels_tensor, k, seed=1000 * k + s) for s in range(n_init)),
                       key=lambda run: run[1])
                for k in range(k_min, k_max + 1)}
        ks = list(runs.keys())
        wcss_vals = [runs[k][1] for k in ks]

        best_k = self._find_elbow(ks, wcss_vals)
        return runs[best_k][0]

    @staticmethod
    def _find_elbow(ks, wcss_vals):
        x1, y1 = ks[0], wcss_vals[0]
        x2, y2 = ks[-1], wcss_vals[-1]
        line_len = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        if line_len == 0:
            return ks[0]

        best_k, best_dist = ks[0], -1.0
        for x, y in zip(ks, wcss_vals):
            dist = abs((y2 - y1) * x - (x2 - x1) * y + x2 * y1 - y2 * x1) / line_len
            if dist > best_dist:
                best_dist = dist
                best_k = x
        return best_k

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

    def calculate_saliency_map(self, image_array, grid_size=(20, 20)):
        """
        Bins SIFT keypoints into a coarse grid_size heatmap over the image,
        giving a per-region visual-noise density map (see manuscript Figure 1,
        panels c/d) rather than a single global scalar. Used by
        HeuristicEvaluator.calculate_legibility_penalty (Formula 3.15) to
        cross-reference text node bboxes against actual background noise.
        """
        img = np.array(image_array)
        gray_image = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        h, w = gray_image.shape[:2]

        keypoints = self.sift.detect(gray_image, None)

        rows, cols = grid_size
        heatmap = np.zeros((rows, cols), dtype=np.float32)
        for kp in keypoints:
            x, y = kp.pt
            col = min(int((x / w) * cols), cols - 1) if w > 0 else 0
            row = min(int((y / h) * rows), rows - 1) if h > 0 else 0
            heatmap[row, col] += 1.0

        max_count = heatmap.max()
        if max_count > 0:
            heatmap = heatmap / max_count

        return {"heatmap": heatmap.tolist(), "image_wh": (w, h)}