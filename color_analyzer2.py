#!/usr/bin/env python3
"""
color_analyzer.py - Optimized Screenshot Color Analysis Module
Usage: python color_analyzer.py
"""

import os
import cv2
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from sklearn.cluster import KMeans
import time

start = time.time()

class ColorAnalyzer:
    def __init__(self, screenshots_folder="screenshots", output_folder="color_analysis"):
        self.screenshots_folder = screenshots_folder
        self.output_folder = output_folder
        os.makedirs(output_folder, exist_ok=True)

    # ---------- CORE COLOR EXTRACTION ---------- #
    def get_dominant_colors(self, image_path, num_colors=5):
        """Extract dominant colors from image using MiniBatchKMeans."""
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Image not found or invalid: {image_path}")

        # Downsample for huge speedup
        #img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        #small = cv2.resize(img_rgb, (450, 450), interpolation=cv2.INTER_AREA)
        #pixels = small.reshape(-1, 3)

        
        #img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        #pixels = np.float32(img_rgb.reshape(-1, 3))

                # Convert to RGB first
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
# ---------- Adaptive resize with aspect-ratio-based pixel budget ---------- #
        h, w = img_rgb.shape[:2]
        aspect_ratio = h / w

        # Base pixel budget (for roughly 1280x800-like screenshots)
        base_pixels = 1_000_000  

        # Scale budget for taller screenshots
        if aspect_ratio < 1.2:
            max_pixels = base_pixels
        elif aspect_ratio < 2.0:
            max_pixels = int(base_pixels * 1.2)
        elif aspect_ratio < 3.0:
            max_pixels = int(base_pixels * 1.5)
        else:
            max_pixels = int(base_pixels * 2.0)

        # Compute resize scale
        current_pixels = h * w
        scale = (max_pixels / current_pixels) ** 0.5 if current_pixels > max_pixels else 1.0
        new_w = int(w * scale)
        new_h = int(h * scale)

        # Resize image preserving aspect ratio
        small = cv2.resize(img_rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)
        pixels = small.reshape(-1, 3)



        kmeans = KMeans(n_clusters=num_colors, n_init="auto", random_state=42)
        labels = kmeans.fit_predict(pixels)
        centers = np.uint8(kmeans.cluster_centers_)

        unique_labels, counts = np.unique(labels, return_counts=True)
        return [(centers[i].tolist(), counts[idx]) for idx, i in enumerate(unique_labels)]

    # ---------- UTILITIES ---------- #
    @staticmethod
    def rgb_to_hex(rgb):
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

    def create_palette_visualization(self, domain, color_percentages, output_path):
        """Generate horizontal color palette bar (optional)."""
        fig, ax = plt.subplots(figsize=(10, 2))
        for i, (color, pct) in enumerate(color_percentages):
            ax.barh(
                0,
                pct,
                left=sum(p[1] for p in color_percentages[:i]),
                color=np.array(color) / 255,
                edgecolor="white",
                linewidth=0.5,
            )

        ax.set_xlim(0, 100)
        ax.set_yticks([])
        ax.set_xlabel("Percentage (%)", fontsize=10)
        ax.set_title(f"{domain} - Color Palette", fontsize=12, fontweight="bold")
        for side in ["top", "right", "left"]:
            ax.spines[side].set_visible(False)

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()

    # ---------- ANALYSIS ---------- #
    def analyze_single(self, screenshot_path, num_colors=5, visualize=False):
        """Analyze one screenshot."""
        domain = Path(screenshot_path).stem
        try:
            dominant_colors = self.get_dominant_colors(screenshot_path, num_colors)
            total = sum(count for _, count in dominant_colors)
            color_percentages = [
                (color, round((count / total) * 100, 2)) for color, count in dominant_colors
            ]

            if visualize:
                palette_path = os.path.join(self.output_folder, f"{domain}_palette.png")
                self.create_palette_visualization(domain, color_percentages, palette_path)

            result = {
                "domain": domain,
                "colors": [
                    {"rgb": color, "hex": self.rgb_to_hex(color), "percentage": pct}
                    for color, pct in color_percentages
                ],
            }

            print(f"✅ {domain}")
            return result
        except Exception as e:
            print(f"⚠️ {domain} - {e}")
            return None

    def analyze_all(self, num_colors=5, visualize=False, workers=6):
        """Analyze all screenshots in folder with multiprocessing."""
        screenshots = [
            f
            for f in os.listdir(self.screenshots_folder)
            if f.lower().endswith(".png") and f != "results.png"
        ]

        if not screenshots:
            print("\n❌ No screenshots found for color analysis.")
            return []

        print(f"\n🎨 Analyzing {len(screenshots)} screenshots with {workers} workers...\n")

        results = []
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self.analyze_single, os.path.join(self.screenshots_folder, f), num_colors, visualize): f
                for f in screenshots
            }
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)

        if results:
            self.save_results(results, num_colors=num_colors)
        return results

    # ---------- OUTPUT ---------- #
    def save_results(self, results, num_colors=5):
        """Save flattened one-row-per-domain color data to CSV."""
        rows = []
        for result in results:
            domain = result["domain"]
            row = {"domain": domain}
            
            for i, color_data in enumerate(result["colors"], start=1):
                hex_col = color_data["hex"]
                pct = color_data["percentage"]
                row[f"top{i}_hex"] = hex_col
                row[f"top{i}_pct"] = pct

            # Fill missing colors if fewer than num_colors
            for i in range(len(result["colors"]) + 1, num_colors + 1):
                row[f"top{i}_hex"] = None
                row[f"top{i}_pct"] = None

            rows.append(row)

        df = pd.DataFrame(rows)
        csv_path = os.path.join(self.output_folder, "color_analysis.csv")
        df.to_csv(csv_path, index=False)

        print(f"\n💾 Results saved: {csv_path}")
        print(f"🎨 Palettes in: {self.output_folder}/")
        self.print_summary(results)


    @staticmethod
    def print_summary(results):
        print(f"\n{'=' * 50}")
        print("📊 COLOR ANALYSIS SUMMARY")
        print(f"{'=' * 50}")
        print(f"✅ Screenshots analyzed: {len(results)}")
        print(f"{'=' * 50}\n")


# ---------- CONVENIENCE WRAPPERS ---------- #
def analyze_colors(screenshots_folder="screenshots", output_folder="color_analysis", num_colors=5, visualize=False, workers=6):
    analyzer = ColorAnalyzer(screenshots_folder, output_folder)
    return analyzer.analyze_all(num_colors=num_colors, visualize=visualize, workers=workers)


def analyze_single_screenshot(screenshot_path, output_folder="color_analysis", num_colors=5, visualize=True):
    analyzer = ColorAnalyzer(output_folder=output_folder)
    return analyzer.analyze_single(screenshot_path, num_colors=num_colors, visualize=visualize)


# ---------- CLI USAGE ---------- #
if __name__ == "__main__":
    print("=" * 60)
    print("🎨 FAST SCREENSHOT COLOR ANALYZER")
    print("=" * 60)

    analyze_colors(
        screenshots_folder="screenshots",
        output_folder="color_analysis",
        num_colors=5,
        visualize=True,  # set True to enable palette PNGs
        workers=6,         # adjust based on CPU cores
    )

end = time.time()
print(f"\n⏱️ Total execution time: {end - start:.2f} seconds")
