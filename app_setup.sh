#!/bin/bash
# app_setup.sh - Streamlit Cloud setup script

echo "Installing Playwright and Chromium dependencies..."
pip install playwright
playwright install chromium --with-deps
