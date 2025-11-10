#!/usr/bin/env python3
"""
app.py - Streamlit Web Interface for Domain Screenshot & Color Analysis
Usage: streamlit run app.py
"""

import streamlit as st
import os
import asyncio
from pathlib import Path
import pandas as pd
from PIL import Image

# Import custom modules
from screenshotter import DomainScreenshotter
from color_analyzer2 import ColorAnalyzer


# ---------------- UI SETUP ---------------- #
st.set_page_config(page_title="Domain Color Analyzer", layout="centered")
st.title("🎨 Domain Screenshot & Color Analyzer")

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: bold;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 2rem;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border-left: 5px solid #28a745;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .error-box {
        padding: 1rem;
        background-color: #f8d7da;
        border-left: 5px solid #dc3545;
        border-radius: 5px;
        margin: 1rem 0;
    }
    </style>
""", unsafe_allow_html=True)


# ---------------- CORE FUNCTIONS ---------------- #
async def capture_screenshot_async(domain, output_folder):
    """Async wrapper for screenshot capture."""
    screenshotter = DomainScreenshotter(output_folder=output_folder, concurrency=1)
    results = await screenshotter.run([domain])
    return results[0] if results else None


def capture_and_analyze(domain, output_folder="screenshots",
                        analysis_folder="color_analysis", num_colors=5, visualize=True):
    """Capture screenshot then analyze colors."""
    progress = st.progress(0, text="🔄 Starting...")

    try:
        # Step 1: Capture Screenshot
        progress.progress(0.25, text=f"📸 Capturing screenshot of {domain}...")
        result = asyncio.run(capture_screenshot_async(domain, output_folder))
        if not result or not result.get("success", False):
            error_msg = result.get("error", "Unknown error") if result else "Failed to capture"
            st.markdown(f"""
                <div class="error-box"><strong>❌ Failed!</strong><br>{error_msg}</div>
            """, unsafe_allow_html=True)
            progress.empty()
            return None

        screenshot_path = result["output_path"]

        # Step 2: Analyze Colors
        progress.progress(0.65, text="🎨 Analyzing colors...")
        analyzer = ColorAnalyzer(output_folder=analysis_folder)
        analysis_result = analyzer.analyze_single(screenshot_path, num_colors=num_colors, visualize=visualize)

        if not analysis_result:
            st.error("Error analyzing colors.")
            progress.empty()
            return None

        # Step 3: Done
        progress.progress(1.0, text="✅ Completed successfully!")
        st.session_state.analysis_result = analysis_result
        st.session_state.screenshot_path = screenshot_path
        progress.empty()
        return analysis_result

    except Exception as e:
        st.markdown(f"""
            <div class="error-box"><strong>⚠️ Error:</strong> {str(e)}</div>
        """, unsafe_allow_html=True)
        progress.empty()
        return None


# ---------------- MAIN APP ---------------- #
def main():
    st.write("Enter a domain to **capture its screenshot** and **analyze its dominant colors.**")
    domain = st.text_input("Domain", placeholder="example.com or https://example.com")
    num_colors = st.slider("Number of Colors", min_value=3, max_value=10, value=5)
    visualize = st.toggle("Generate Color Palette Image", value=True)

    output_folder = "screenshots"
    analysis_folder = "color_analysis"

    if st.button("Capture & Analyze", use_container_width=True) and domain:
        with st.spinner(f"Processing {domain}..."):
            result = capture_and_analyze(domain, output_folder, analysis_folder, num_colors, visualize)

        if result:
            # Display screenshot
            st.subheader("📸 Screenshot Preview")
            if os.path.exists(st.session_state.screenshot_path):
                image = Image.open(st.session_state.screenshot_path)
                st.image(image, use_container_width=True)

            # Display color analysis
            st.markdown("---")
            st.subheader("🎨 Color Analysis Results")

            palette_path = os.path.join(analysis_folder, f"{result['domain']}_palette.png")
            if visualize and os.path.exists(palette_path):
                st.image(palette_path, caption="Color Palette", use_container_width=True)

            # Data Table
            color_data = [
                {
                    "Rank": i + 1,
                    "Hex": c["hex"],
                    "RGB": f"({c['rgb'][0]}, {c['rgb'][1]}, {c['rgb'][2]})",
                    "Percentage": f"{c['percentage']}%"
                }
                for i, c in enumerate(result["colors"])
            ]
            df = pd.DataFrame(color_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Color Swatches
            st.markdown("### 🎨 Color Swatches")
            cols = st.columns(len(result["colors"]))
            for col, color in zip(cols, result["colors"]):
                text_color = "white" if sum(color["rgb"]) < 382 else "black"
                col.markdown(f"""
                    <div style="
                        background-color: {color['hex']};
                        height: 100px;
                        border-radius: 10px;
                        border: 2px solid #ddd;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: {text_color};
                        font-weight: bold;
                        font-size: 14px;">
                        {color['percentage']}%
                    </div>
                    <p style="text-align: center; margin-top: 5px; font-size: 12px;">
                        {color['hex']}
                    </p>
                """, unsafe_allow_html=True)

            # Download buttons
            st.markdown("---")
            st.subheader("⬇️ Download Results")

            col1, col2, col3 = st.columns(3)

            with col1:
                if os.path.exists(st.session_state.screenshot_path):
                    with open(st.session_state.screenshot_path, "rb") as f:
                        st.download_button("Screenshot", f, f"{result['domain']}_screenshot.png", "image/png")

            with col2:
                if visualize and os.path.exists(palette_path):
                    with open(palette_path, "rb") as f:
                        st.download_button("Palette", f, f"{result['domain']}_palette.png", "image/png")

            with col3:
                csv_data = df.to_csv(index=False)
                st.download_button("CSV", csv_data, f"{result['domain']}_colors.csv", "text/csv")

    # Footer
    st.markdown("---")
    st.caption("⚡ Powered by Playwright + OpenCV + MiniBatchKMeans")


if __name__ == "__main__":
    main()
