#!/bin/bash
# Build Windows package for nettest
# Run this after making changes to sync and rebuild the zip

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Building Windows Package ==="
echo

# Sync nettest to windows package (excluding dev files)
echo "[1/3] Syncing nettest files..."
rsync -av --delete \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='README.md' \
    --exclude='run-windows.bat' \
    --exclude='run-windows.ps1' \
    nettest/ nettest-windows-package/nettest/

# Clean any output files from the package
echo "[2/3] Cleaning output directory..."
rm -f nettest-windows-package/output/*.html
rm -f nettest-windows-package/output/*.json
rm -f nettest-windows-package/output/*.csv

# Rebuild the zip
echo "[3/3] Creating zip archive..."
rm -f nettest-for-windows.zip
pushd nettest-windows-package > /dev/null
zip -r ../nettest-for-windows.zip . \
    -x "*.pyc" \
    -x "*__pycache__*" \
    -x "output/*.html" \
    -x "output/*.json" \
    -x "output/*.csv"
popd > /dev/null

echo
echo "=== Done! ==="
echo "Package: nettest-for-windows.zip"
ls -lh nettest-for-windows.zip
