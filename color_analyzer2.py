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
from sklearn.cluster import MiniBatchKMeans


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
        #small = cv2.resize(img_rgb, (150, 150), interpolation=cv2.INTER_AREA)
        #pixels = small.reshape(-1, 3)

        
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pixels = np.float32(img_rgb.reshape(-1, 3))


        kmeans = MiniBatchKMeans(n_clusters=num_colors, batch_size=4096, n_init="auto", random_state=42)
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
            self.save_results(results)
        return results

    # ---------- OUTPUT ---------- #
    def save_results(self, results):
        """Save color data to CSV."""
        detailed = []
        for result in results:
            domain = result["domain"]
            for idx, color_data in enumerate(result["colors"], 1):
                detailed.append(
                    {
                        "domain": domain,
                        "color_rank": idx,
                        "red": color_data["rgb"][0],
                        "green": color_data["rgb"][1],
                        "blue": color_data["rgb"][2],
                        "hex": color_data["hex"],
                        "percentage": color_data["percentage"],
                    }
                )

        df = pd.DataFrame(detailed)
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
