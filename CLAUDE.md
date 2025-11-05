# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository provides an automated build system for Hadoop libhdfs native libraries on macOS, supporting both Intel x86_64 and Apple Silicon ARM64 architectures. The build is **highly optimized** to skip Java compilation entirely by downloading pre-compiled JARs from Maven Central, focusing only on building native C/C++ libraries with full compression support.

**Key characteristic**: This is a **GitHub Actions-based build system**, not a traditional source code repository. The actual Hadoop source code is cloned during the build process.

## Build Strategy

The build workflow uses a highly optimized approach that **skips JAR downloads entirely** from the main build:

1. **Cache Hadoop source** (keyed by version, saved across builds)
2. **Clone Hadoop source only if cache miss** (shallow clone, for native C/C++ code only)
3. **Build only native libraries** (libhdfs, libhadoop) with compression support
4. **Experimental CMake-only build** attempts direct CMake compilation, falling back to Maven if needed
5. **JAR files downloaded only in integration tests** (not included in artifacts)

This approach reduces build time:
- **Feature branches (full build)**: ~9-13 minutes (build + smoke test only)
- **Feature branches (test-only changes)**: ~2-3 minutes (smoke test with cached artifacts)
- **Main branch**: ~15-20 minutes (includes full integration tests)
- **With Hadoop source cache hit**: Additional ~15 seconds saved
- **Smart build detection**: Automatically skips rebuild when only tests/docs/workflows changed

## Common Commands

### Trigger Build Workflow

Builds are automatically triggered on push to `main`, `develop`, or `claude/**` branches, and on pull requests to `main`.

Manual trigger via GitHub UI:
```
Actions → "Build Hadoop libhdfs (Highly Optimized - Native Only)" → Run workflow
```

Or via GitHub CLI:
```bash
gh workflow run build-libhdfs-macos-optimized.yml \
  --field hadoop_version=3.3.6 \
  --field skip_build=false
```

### Test Integration Locally

```bash
# Set up environment
export HADOOP_HOME=~/libhdfs-artifacts
export JAVA_HOME=$(/usr/libexec/java_home -v 11)
export DYLD_LIBRARY_PATH=$HADOOP_HOME/native:$JAVA_HOME/lib/server
export CLASSPATH=$(find $HADOOP_HOME/jars -name "*.jar" | tr '\n' ':')

# Run basic library loading test
python3 .github/tests/test_library_loading.py

# Run full PyArrow integration test (requires Ozone cluster)
python3 .github/tests/test_libhdfs_pyarrow.py
```

### Compile C Test Program

```bash
gcc .github/templates/test_libhdfs.c -o test_libhdfs \
  -I~/libhdfs-artifacts/headers \
  -I$JAVA_HOME/include \
  -I$JAVA_HOME/include/darwin \
  -L~/libhdfs-artifacts/native \
  -lhdfs \
  -Wl,-rpath,~/libhdfs-artifacts/native

./test_libhdfs
```

## Repository Structure

```
.github/
├── workflows/
│   └── build-libhdfs-macos-optimized.yml  # Main build workflow (3 jobs)
├── patches/
│   ├── hadoop-3.3.6-exception-macos.patch      # macOS exception.c patch
│   ├── hadoop-3.3.6-macos-openssl.cmake        # OpenSSL path configuration
│   └── hadoop-3.3.6-openssl3-compat.patch      # OpenSSL 3.x compatibility
├── templates/
│   ├── pom-download-jars.xml.template     # Maven config to download JARs
│   ├── test_libhdfs.c                     # C smoke test
│   ├── BUILD_INFO.txt.template            # Build metadata template
│   ├── ozone-site.xml.template            # Ozone configuration (legacy)
│   └── ozone-docker-compose.yml           # Docker Compose for Ozone (used in integration tests)
└── tests/
    ├── test_libhdfs_pyarrow.py            # PyArrow integration test
    ├── test_library_loading.py            # Basic library loading test
    └── README.md                          # Testing documentation
```

## Workflow Architecture

The main workflow (`.github/workflows/build-libhdfs-macos-optimized.yml`) has five jobs:

### Job 0: `check-changes` **[NEW]**
- Runs on Ubuntu (fast startup)
- Analyzes changed files to determine if build is needed
- **Smart build detection**:
  - If only tests/workflows/docs changed → skips build, uses latest artifacts
  - If source code/patches changed → triggers full build
  - Manual triggers always respect `skip_build` parameter
- **Files that don't require rebuild**:
  - `.github/workflows/*` (workflow files)
  - `.github/tests/*` (test scripts)
  - `.github/templates/ozone-docker-compose.yml`
  - `CLAUDE.md`, `README.md`
- **Output**: `should_build` (true/false)

### Job 1: `setup-maven`
- Runs once on Intel runner (macos-15)
- Downloads Maven dependencies and plugins
- Creates Maven cache for subsequent jobs
- Only runs if `should_build == true`

### Job 2: `build-libhdfs` (matrix: Intel & ARM64)
- Depends on `check-changes` and `setup-maven`
- Runs in parallel for both architectures
- Only runs if `should_build == true`
- **Key steps**:
  1. Setup Java 11 (build only)
  2. Install Homebrew dependencies: cmake, maven, protobuf@21, openssl@3, snappy, lz4, zstd, zlib
  3. Setup OpenSSL symlinks (keg-only formula)
  4. **Cache Hadoop source** (keyed by version)
  5. Clone Hadoop source only if cache miss (shallow, specific release tag)
  6. Apply macOS patches (see Patches section below)
  7. **Experimental CMake build** attempt (falls back to Maven if fails)
  8. Build native libraries only (Maven with `-Pnative -DskipTests -Dmaven.compiler.skip=true`)
  9. Collect artifacts (native libraries and headers only, **no JARs**)
  10. Package and upload artifacts

**Note:** JAR downloads completely removed from this job to save time.

### Job 3: `smoke-test` (matrix: Intel & ARM64)
- Runs after `check-changes` and `build-libhdfs`
- **Always runs** on all branches (fast feedback loop)
- **Smart artifact download**:
  - If `should_build == true` → downloads from current run
  - If `should_build == false` → downloads from latest successful run
- **Key steps**:
  1. Download libhdfs artifacts (current or latest)
  2. Verify native libraries load correctly using `test_library_loading.py`
  3. No JAR files needed, no Ozone cluster needed
- **Time**: ~1-2 minutes per architecture
- **Purpose**: Catch 80% of build issues quickly

### Job 4: `integration-tests` (matrix: Intel & ARM64)
- Runs after `check-changes` and `build-libhdfs`
- **Only runs when**:
  - Manual trigger with `run_integration_tests = true`, OR
  - Push to `main` branch
- **Smart artifact download**:
  - If `should_build == true` → downloads from current run
  - If `should_build == false` → downloads from latest successful run
- **Key steps**:
  1. Download libhdfs artifacts (current or latest)
  2. **Download Hadoop JARs** for integration tests (only here!)
  3. Run basic library loading test
  4. **Start Ozone with Docker Compose** (`.github/templates/ozone-docker-compose.yml`)
  5. Wait for Ozone health check to pass
  6. Run PyArrow integration tests with compression
  7. Cleanup: docker compose down
- **Time**: ~5-10 minutes per architecture

**Key optimizations**:
- **Smart build detection**: Automatically skips rebuild when only tests/docs changed (~15 min → ~2-3 min)
- **Ozone via Docker Compose v2**: Uses `docker compose` (not `docker-compose`) for compatibility with latest GitHub Actions runners
- Built-in health checks ensure Ozone is ready before tests
- JAR files only downloaded when integration tests actually run
- Integration tests skipped on feature branches by default
- No need to cache Ozone tarball anymore
- Artifact reuse from previous successful runs when build is skipped

## Patches

Three critical patches are applied during build:

1. **hadoop-3.3.6-exception-macos.patch**: Adds macOS support to `exception.c` by using `strerror()` instead of `sys_errlist`/`sys_nerr` (not available on macOS)

2. **hadoop-3.3.6-macos-openssl.cmake**: Configures OpenSSL paths for both Intel (`/usr/local`) and Apple Silicon (`/opt/homebrew`) via environment variables

3. **hadoop-3.3.6-openssl3-compat.patch**: Guards deprecated OpenSSL threading APIs (pre-1.1.0) to work with OpenSSL 3.x

All patches are applied to the cloned Hadoop source before native compilation begins.

## Compression Support

The native libraries are built with support for:
- **Snappy** - fast compression
- **LZ4** - very fast compression
- **Zstd** - high compression ratio
- **Zlib/Gzip** - standard compression

All compression libraries are installed via Homebrew and linked during native compilation.

## Platform Support

- **Intel x86_64**: Builds on `macos-13` runner
- **Apple Silicon arm64**: Builds on `macos-14` runner

Both architectures use the same workflow with matrix strategy for parallel builds.

## Hadoop Version

Current version: **3.3.6** (configurable via workflow input)

The version is used to:
- Download specific Hadoop JARs from Maven Central
- Clone the correct git release tag (`rel/release-3.3.6`)
- Tag artifacts with version

## Testing

### C Library Test (`.github/templates/test_libhdfs.c`)
Basic smoke test that:
- Loads libhdfs.dylib
- Verifies JVM initialization
- Checks compression codec symbols

### PyArrow Integration Test (`.github/tests/test_libhdfs_pyarrow.py`)
Comprehensive test that:
- Verifies PyArrow has HDFS support
- Connects to Ozone/HDFS cluster
- Tests basic file operations (read/write/list/delete)
- Tests all compression algorithms with Parquet files
- Reports compression results and file sizes

### Library Loading Test (`.github/tests/test_library_loading.py`)
Minimal test that verifies library can be loaded without HDFS cluster.

## Workflow Parameters

When triggering manually via `workflow_dispatch`:

- `hadoop_version` (default: `3.3.6`): Hadoop version to build
- `skip_build` (default: `false`): Skip build and run only integration tests using latest artifacts
- `run_integration_tests` (default: `false`): Run full integration tests with Ozone cluster. If false, only smoke tests run (much faster)

## Build Artifacts

Each successful build produces:
- Artifact name: `libhdfs-{version}-macos-{arch}`
- Contains:
  - `libhdfs.dylib` / `libhdfs.a` - HDFS C API library
  - `libhadoop.dylib` / `libhadoop.a` - Hadoop native library
  - Headers from native client (`.h` files)
  - Build metadata (BUILD_INFO.txt)

**IMPORTANT:** JAR files are NOT included in artifacts (removed for optimization). Download separately from Maven Central if needed.

Artifacts are retained for 90 days.

## Environment Variables

Key environment variables used in workflows:

- `HADOOP_VERSION`: Version to build (default: 3.3.6)
- `PROTOBUF_VERSION`: Protocol Buffers version (3.21.12)
- `JAVA_BUILD_VERSION`: Java version for build (11)
- `JAVA_RUNTIME_VERSION`: Java version for testing (17)
- `OPENSSL_ROOT_DIR`, `OPENSSL_INCLUDE_DIR`, `OPENSSL_LIBRARIES`: OpenSSL paths
- `ZLIB_ROOT`, `ZLIB_INCLUDE_DIR`, `ZLIB_LIBRARY`: Zlib paths (Homebrew or SDK)
- `CMAKE_PREFIX_PATH`: All dependency prefixes for CMake
- `PKG_CONFIG_PATH`: pkg-config paths for all libraries
- `LDFLAGS`, `CPPFLAGS`: Compiler/linker flags for keg-only libraries

## Maven Optimization

The workflow uses multiple strategies to minimize Maven overhead:

1. **Dependency caching**: `~/.m2/repository` cached across runs (key: OS + Hadoop version)
2. **Hadoop source caching**: `~/hadoop-src` cached across runs (key: Hadoop version) - saves ~15 seconds per build
3. **JAR downloads eliminated from build**: JAR files NO LONGER downloaded during build phase
   - Build job: Pure native compilation, no JAR downloads
   - Integration tests job: Downloads JARs on-demand using `pom-download-jars.xml.template`
   - Native build uses `-Dmaven.compiler.skip=true` or `-Dmaven.test.skip=true`
4. **Experimental CMake-only build**: Attempts direct CMake compilation (faster), falls back to Maven if needed

## CMake Configuration

The Hadoop native build uses CMake with special considerations for macOS:

- **cmake_minimum_required**: Patched to 3.5 (from 3.1) for better macOS support
- **OpenSSL**: Custom configuration via `.github/patches/hadoop-3.3.6-macos-openssl.cmake`
- **Zlib**: Auto-detected by CMake (Homebrew or system SDK)
- **Keg-only libraries**: protobuf@21, openssl@3 require explicit paths via `CMAKE_PREFIX_PATH`

## macOS Architecture Differences

The workflow handles both architectures uniformly, but note:

- **Intel (x86_64)**: Homebrew prefix = `/usr/local`
- **Apple Silicon (arm64)**: Homebrew prefix = `/opt/homebrew`

All paths use `brew --prefix` to detect correct location dynamically.

## Workflow Triggers

```yaml
on:
  push:
    branches: [ main, develop, 'claude/**' ]
  pull_request:
    branches: [ main ]
  workflow_dispatch:
```

Claude-specific branches (`claude/**`) are included to allow experimental builds.

## Important Changes & Troubleshooting

### Docker Compose v2 Migration (2025-11-06)
**Issue**: GitHub Actions macOS runners no longer support `docker-compose` (v1 with hyphen).

**Solution**: All Docker Compose commands migrated to v2 syntax:
- ❌ Old: `docker-compose -f file.yml up`
- ✅ New: `docker compose -f file.yml up`

**Impact**: Integration tests that use Ozone Docker Compose now work correctly on latest runners.

### Smart Build Detection (2025-11-06)
**Feature**: Workflow now automatically detects if full build is needed based on changed files.

**Behavior**:
- Changes to `.github/patches/*`, source code → **Full build** (~15 min)
- Changes to `.github/workflows/*`, `.github/tests/*`, docs → **Skip build, reuse artifacts** (~2-3 min)
- Manual triggers with `skip_build=true` → Always skip build
- Manual triggers without `skip_build` → Always build

**Benefits**:
- Faster feedback when fixing tests or updating documentation
- Saves ~12-13 minutes when only test/workflow changes are made
- Automatically downloads artifacts from latest successful run

## Claude Code Instructions

- все патч только отдельными файлами! никаких инлайнов в билд
- перед пушем проверяй валидность yaml, корректность патчей
- всегда используй mcp где это возможно
- запомни создавать патчи всегда нужно единственным способом:
  1. копируешь исходный файл
  2. вносишь в нем изменения
  3. создаешь патч средствами git
  4. больше никак
- всегда используй агент после пуша