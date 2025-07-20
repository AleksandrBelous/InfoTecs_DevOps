#!/bin/bash
set -e

echo "[1/4] Cleaning old build and CMake configs..."

rm -rf build

rm -f CMakeUserPresets.json

mkdir -p build
cd build

echo "[2/4] Installing dependencies..."
conan install .. --build=missing

echo "[3/4] Configuring with CMake..."
cmake .. \
  -DCMAKE_TOOLCHAIN_FILE=Release/generators/conan_toolchain.cmake \
  -DCMAKE_BUILD_TYPE=Release

echo "[3/4] Building..."
cmake --build .

echo "Done. Run with ./build/main"
