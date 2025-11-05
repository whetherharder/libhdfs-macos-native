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
Actions → "Build and Test libhdfs (Modular)" → Run workflow
```

Or via GitHub CLI:
```bash
# Full build (default)
gh workflow run orchestrator.yml \
  --field hadoop_version=3.3.6

# Force build even if only tests changed
gh workflow run orchestrator.yml \
  --field force_build=true

# Skip build, run tests only (use cached artifacts)
gh workflow run orchestrator.yml \
  --field skip_build=true \
  --field run_integration_tests=true

# Full build with integration tests
gh workflow run orchestrator.yml \
  --field hadoop_version=3.3.6 \
  --field run_integration_tests=true
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
│   ├── orchestrator.yml                   # Main workflow - orchestrates all jobs
│   ├── check-changes.yml                  # Reusable: Check if build needed + artifact validation
│   ├── setup-maven.yml                    # Reusable: Setup Maven dependencies cache
│   ├── build-libhdfs.yml                  # Reusable: Build native libraries (matrix: Intel + ARM64)
│   ├── smoke-test.yml                     # Reusable: Fast native library verification (matrix)
│   ├── integration-test.yml               # Reusable: PyArrow tests with Ozone (matrix + service containers)
│   └── build-libhdfs-macos-optimized.yml.old  # Legacy monolithic workflow (backup)
├── patches/
│   ├── hadoop-3.3.6-exception-macos.patch      # macOS exception.c patch
│   ├── hadoop-3.3.6-macos-openssl.cmake        # OpenSSL path configuration
│   └── hadoop-3.3.6-openssl3-compat.patch      # OpenSSL 3.x compatibility
├── templates/
│   ├── pom-download-jars.xml.template     # Maven config to download JARs
│   ├── test_libhdfs.c                     # C smoke test
│   ├── BUILD_INFO.txt.template            # Build metadata template
│   ├── ozone-site.xml.template            # Ozone configuration (legacy)
│   └── ozone-docker-compose.yml           # Docker Compose for Ozone (local dev reference)
└── tests/
    ├── test_libhdfs_pyarrow.py            # PyArrow integration test
    ├── test_library_loading.py            # Basic library loading test
    └── README.md                          # Testing documentation
```

## Workflow Architecture

The workflow system is **modular**, using reusable workflows for each stage. The main orchestrator (`.github/workflows/orchestrator.yml`) coordinates all jobs.

### Modular Structure

**Main Orchestrator** (`orchestrator.yml`):
- Entry point for all triggers (push, PR, manual)
- Calls reusable workflows in dependency order
- Passes inputs/outputs between jobs

**Reusable Workflows** (called via `workflow_call`):

### 1. `check-changes.yml` - Smart Build Decision
**File**: `.github/workflows/check-changes.yml`

- Runs on Ubuntu (fast startup)
- **Enhanced logic with artifact validation**:
  - **Priority 0**: `force_build=true` → always build
  - **Priority 1**: `skip_build=true` → skip build
  - **Priority 2**: Manual trigger → always build
  - **Priority 3**: Auto trigger → analyze changed files
  - **Priority 4**: If skip recommended → **check artifact existence in latest run**
    - If artifacts found for both architectures → skip build
    - If artifacts missing/expired → force build

- **Files that don't require rebuild**:
  - `.github/tests/*` (test scripts)
  - `.github/templates/ozone-docker-compose.yml` (test config)
  - `CLAUDE.md`, `README.md` (documentation)

- **Files that ALWAYS trigger rebuild**:
  - `.github/workflows/*` (workflow changes)
  - `.github/patches/*` (patch changes)
  - Source code files

- **Output**: `should_build` (true/false)

### 2. `setup-maven.yml` - Maven Dependencies Cache
**File**: `.github/workflows/setup-maven.yml`

- Runs once on Intel runner (macos-15)
- Downloads Maven dependencies and plugins
- Creates Maven cache for subsequent jobs
- Only runs if `should_build == true`

### 3. `build-libhdfs.yml` - Native Library Compilation
**File**: `.github/workflows/build-libhdfs.yml`

- **Matrix strategy**: Intel x86_64 + ARM64 (parallel)
- Depends on `check-changes` and `setup-maven`
- Only runs if `should_build == true`
- **Key steps**:
  1. Setup Java 11 (build only)
  2. Install Homebrew dependencies: cmake, maven, protobuf@21, openssl@3, snappy, lz4, zstd, zlib
  3. Setup OpenSSL symlinks (keg-only formula)
  4. Cache Hadoop source (keyed by version)
  5. Clone Hadoop source only if cache miss (shallow)
  6. Apply macOS patches (see Patches section)
  7. Build native libraries only (Maven with `-Pnative -DskipTests -Dmaven.compiler.skip=true`)
  8. Collect artifacts (native libraries + headers, **no JARs**)
  9. Upload artifacts

**Note:** JAR downloads completely removed from build to save time.

### 4. `smoke-test.yml` - Fast Native Library Verification
**File**: `.github/workflows/smoke-test.yml`

- **Matrix strategy**: Intel x86_64 + ARM64 (parallel)
- **Always runs** (fast feedback loop)
- **Smart artifact download**:
  - If `should_build == true` → downloads from current run
  - If `should_build == false` → downloads from latest successful run
- **Key steps**:
  1. Download libhdfs artifacts
  2. Verify native libraries load correctly (`test_library_loading.py`)
  3. No JAR files or Ozone cluster needed
- **Time**: ~1-2 minutes per architecture
- **Purpose**: Catch 80% of build issues quickly

### 5. `integration-test.yml` - PyArrow Tests with Ozone
**File**: `.github/workflows/integration-test.yml`

- **Matrix strategy**: Intel x86_64 + ARM64 (parallel)
- **Docker Compose**: Ozone cluster via Docker Compose v2
  - Each matrix job gets own Ozone instance (runner isolation)
  - Health check polling (60s timeout)
  - Automatic cleanup with `docker compose down`
- **Only runs when**:
  - Manual trigger with `run_integration_tests=true`, OR
  - Push to `main` branch
- **Enhanced artifact download**:
  - Retry logic (3 attempts, 300s timeout each)
  - Artifact validation (check libhdfs.dylib exists)
  - Clear error messages for expired/missing artifacts
- **Key steps**:
  1. Download libhdfs artifacts (with retry)
  2. Download Hadoop JARs for integration tests
  3. Run basic library loading test
  4. Start Ozone with Docker Compose
  5. Wait for Ozone health check (polling)
  6. Run PyArrow integration tests with compression
  7. Cleanup: docker compose down
- **Time**: ~5-10 minutes per architecture

### Key Improvements in Modular Architecture

1. **Modular code**: Each workflow file focused on single responsibility
2. **Artifact validation**: Checks existence before skipping build
3. **Docker Compose v2**: Ozone cluster management with health checks
4. **Enhanced error handling**: Retry logic and clear failure messages
5. **Better maintainability**: Changes isolated to specific workflow files

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
- `force_build` (default: `false`): **NEW** - Force full build even if only tests/docs changed. Overrides smart build detection.
- `skip_build` (default: `false`): Skip build and run only tests using latest artifacts. Useful for testing changes.
- `run_integration_tests` (default: `false`): Run full integration tests with Ozone cluster. If false, only smoke tests run (much faster).

### Build Decision Priority

The `check-changes` workflow uses the following priority order:

1. **Priority 0**: `force_build=true` → Always build (overrides everything)
2. **Priority 1**: `skip_build=true` → Skip build (use cached artifacts)
3. **Priority 2**: Manual trigger (workflow_dispatch) → Always build
4. **Priority 3**: Auto trigger (push/PR) → Analyze changed files
5. **Priority 4**: If only test/docs changed → Check artifact existence:
   - Artifacts found → Skip build
   - Artifacts missing/expired → Force build

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
- Changes to source code, `.github/patches/*`, `.github/workflows/*` → **Full build** (~15 min)
- Changes to `.github/tests/*`, docs only → **Skip build, reuse artifacts** (~2-3 min)
- Manual triggers with `skip_build=true` → Always skip build
- Manual triggers without `skip_build` → Always build

**Benefits**:
- Faster feedback when fixing tests or updating documentation
- Saves ~12-13 minutes when only test script changes are made
- Automatically downloads artifacts from latest successful run
- Workflow changes always trigger full rebuild to ensure integrity

**Pattern Fix (2025-11-06)**:
- Initial implementation incorrectly included workflow files in "test-only" pattern
- This caused workflow changes to skip build, creating chicken-and-egg problem
- Fixed: workflow changes now properly trigger full rebuild

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
- всегда используй агент чтобы мониторить билд
- перед пушем делай ревью. для этого используй агент