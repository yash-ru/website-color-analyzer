#!/usr/bin/env python3
"""
dominant_colors_smart.py - Smarter dominant color extractor per domain.
Handles light/dark themes, filters neutral tones, picks primary colors.
"""

import os
import pandas as pd
import colorsys
from pathlib import Path

# ---------- COLOR UTILS ----------
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_brightness(rgb):
    """Convert RGB to perceived brightness (0=dark, 1=bright)"""
    r, g, b = [x / 255 for x in rgb]
    return 0.299*r + 0.587*g + 0.114*b

def is_neutral(rgb, s_thresh=0.25, v_low=0.15, v_high=0.95):
    """Detect whites, greys, blacks using HSV thresholds"""
    r, g, b = [x / 255 for x in rgb]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return (s < s_thresh) or (v < v_low) or (v > v_high)

# ---------- DOMINANT COLOR EXTRACTION ----------
def extract_dominant_colors(csv_path, top_n_primary=2):
    """
    Reads color_analysis CSV with columns:
    domain, top1_hex, top1_pct, ..., top5_hex, top5_pct
    Returns dataframe with dominant_color_1, dominant_color_2, theme
    """
    df = pd.read_csv(csv_path)
    results = []

    for _, row in df.iterrows():
        domain = row['domain']

        # Build color list
        colors = []
        for i in range(1, 6):
            hex_col = f'top{i}_hex'
            pct_col = f'top{i}_pct'
            if hex_col in row and pct_col in row:
                hex_val = row[hex_col]
                pct_val = float(row[pct_col])
                rgb = hex_to_rgb(hex_val)
                colors.append({'hex': hex_val, 'rgb': rgb, 'pct': pct_val})

        # Compute average brightness weighted by percentage
        avg_brightness = sum(c['pct'] * rgb_to_brightness(c['rgb']) for c in colors) / max(sum(c['pct'] for c in colors), 0.0001)
        theme = "Dark" if avg_brightness < 0.5 else "Light"

        # Filter out neutral tones
        non_neutral = [c for c in colors if not is_neutral(c['rgb'])]

        # ---------------- Primary color selection ----------------
        dominant_colors = []
        if theme == "Dark":
            # Exclude very dark colors
            bright_colors = [c for c in non_neutral if rgb_to_brightness(c['rgb']) > 0.15]
            if not bright_colors:
                bright_colors = non_neutral or colors  # fallback
            # Sort by pct * brightness
            bright_colors.sort(key=lambda x: x['pct'] * rgb_to_brightness(x['rgb']), reverse=True)
            dominant_colors = bright_colors[:top_n_primary]
        else:
            # Light site: pick most prominent colors
            non_neutral.sort(key=lambda x: -x['pct'])
            dominant_colors = non_neutral[:top_n_primary]

        # Fallback if less than top_n_primary
        while len(dominant_colors) < top_n_primary:
            dominant_colors.append({'hex': None})

        results.append({
            'domain': domain,
            'dominant_color_1': dominant_colors[0]['hex'],
            'dominant_color_2': dominant_colors[1]['hex'],
            'theme': theme
        })

    # Merge with original data
    df_out = pd.merge(df, pd.DataFrame(results), on='domain')
    return df_out

# ---------- CLI ENTRY POINT ----------
if __name__ == "__main__":
    print("🎨 Extracting smarter dominant colors...")
    csv_input = Path("color_analysis/color_analysis.csv")  # Adjust path
    df_result = extract_dominant_colors(csv_input, top_n_primary=2)
    
    out_folder = Path("color_analysis")
    out_folder.mkdir(parents=True, exist_ok=True)
    out_csv = out_folder / "color_analysis_with_dominant.csv"
    df_result.to_csv(out_csv, index=False)
    
    print(f"✅ Saved updated dominant colors CSV: {out_csv}")
