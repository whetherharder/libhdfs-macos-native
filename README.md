# libhdfs-macos

Automated build system for Hadoop libhdfs native libraries on macOS (Intel x86_64 and Apple Silicon ARM64).

## Overview

This repository provides GitHub Actions workflows to build Hadoop libhdfs native libraries optimized for macOS platforms. The libraries are built with full compression support (Snappy, LZ4, Zstd, Zlib) and are compatible with PyArrow and Apache Ozone.

## Features

- **Dual Architecture Support**: Builds for both Intel x86_64 (macos-13) and Apple Silicon ARM64 (macos-14)
- **Compression Support**: Includes Snappy, LZ4, Zstd, and Zlib compression libraries
- **Optimized Build**:
  - Downloads pre-compiled Hadoop JARs from Maven Central
  - Only compiles native C/C++ code
  - Maven dependency caching for faster builds
- **Automatic Testing**: Integration tests with PyArrow and mini Ozone cluster
- **Artifacts**: Native libraries packaged and available for download

## Build Artifacts

Each successful build produces artifacts containing:

- `libhdfs.dylib` / `libhdfs.a` - HDFS C API library (dynamic/static)
- `libhadoop.dylib` / `libhadoop.a` - Hadoop native library (dynamic/static)
- Headers and build information

## Hadoop Version

Current version: **3.3.6**

## Usage

### Automated Builds

Builds are automatically triggered on:
- Push to `main`, `develop`, or `claude/**` branches
- Pull requests to `main`

### Manual Builds

You can trigger builds manually:

1. Go to **Actions** → **Build Hadoop libhdfs (Highly Optimized - Native Only)**
2. Click **"Run workflow"**
3. Select branch and Hadoop version
4. Optionally enable `skip_build` to run only integration tests on existing artifacts

### Download Artifacts

After a successful build:

1. Go to the workflow run page
2. Scroll to **Artifacts** section
3. Download artifacts for your architecture:
   - `libhdfs-3.3.6-macos-intel-x86_64`
   - `libhdfs-3.3.6-macos-apple-silicon-arm64`

## Integration Testing

Integration tests verify:
- Library loading and initialization
- Compression library symbols (Snappy, LZ4, Zstd, Zlib)
- PyArrow compatibility (optional, requires mini Ozone cluster)

Tests run automatically after successful builds on both architectures.

## Local Testing

See `.github/tests/README.md` for instructions on:
- Setting up test environment
- Running C smoke tests
- Testing with PyArrow
- Configuring for Ozone integration

## Build Performance

- **First run** (no cache): ~15-17 minutes
- **Subsequent runs** (with cache): ~9-11 minutes
- **Tests only** (skip_build): ~5-7 minutes

## Repository Structure

```
.github/
├── workflows/           # GitHub Actions workflows
│   └── build-libhdfs-macos-optimized.yml
├── patches/            # CMake and source patches for macOS compatibility
├── templates/          # Configuration templates
└── tests/             # Test scripts and documentation
```

## Requirements

- macOS 13 (Intel) or macOS 14 (Apple Silicon)
- Xcode Command Line Tools
- Homebrew packages: cmake, maven, protobuf@21, openssl@3, snappy, lz4, zstd, zlib
- Java 11 (for build) and Java 17 (for runtime testing)

## License

This project inherits the Apache License 2.0 from Apache Hadoop.

See `LICENSE.txt` for full license text.

## Credits

Built on top of Apache Hadoop native libraries with patches for macOS compatibility and optimization.
