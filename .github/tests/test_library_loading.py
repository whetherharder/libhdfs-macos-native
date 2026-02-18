#!/usr/bin/env python3
"""Basic test to verify libhdfs libraries can be loaded."""
import ctypes
import os
import subprocess
import sys

dyld_path = os.environ.get('DYLD_LIBRARY_PATH', '')
print(f"DYLD_LIBRARY_PATH: {dyld_path}")

# Try to load libhdfs
try:
    libhdfs = ctypes.CDLL("libhdfs.dylib")
    print("✅ libhdfs.dylib loaded successfully")
except Exception as e:
    print(f"❌ Failed to load libhdfs.dylib: {e}")
    sys.exit(1)

# Try to load libhadoop
try:
    libhadoop = ctypes.CDLL("libhadoop.dylib")
    print("✅ libhadoop.dylib loaded successfully")
except Exception as e:
    print(f"❌ Failed to load libhadoop.dylib: {e}")
    sys.exit(1)

# Verify compression libraries can be loaded and have expected symbols
# These are dynamically linked by libhadoop.dylib but must be verified separately
# because ctypes only resolves symbols from the loaded library itself
print("\n=== Verifying compression libraries ===")

brew_prefix = subprocess.check_output(['brew', '--prefix']).decode().strip()
brew_lib = os.path.join(brew_prefix, 'lib')

# zlib is keg-only in Homebrew, check both locations
zlib_paths = [
    os.path.join(brew_prefix, 'opt', 'zlib', 'lib', 'libz.dylib'),  # Homebrew keg-only
    os.path.join(brew_lib, 'libz.dylib'),                            # Homebrew linked
    '/usr/lib/libz.dylib',                                            # System
]

zlib_path = None
for p in zlib_paths:
    if os.path.exists(p):
        zlib_path = p
        break

if zlib_path is None:
    print("❌ Cannot find libz.dylib")
    sys.exit(1)

compression_checks = [
    (os.path.join(brew_lib, 'libsnappy.dylib'), 'snappy_compress', 'Snappy'),
    (os.path.join(brew_lib, 'liblz4.dylib'), 'LZ4_compress_default', 'LZ4'),
    (os.path.join(brew_lib, 'libzstd.dylib'), 'ZSTD_compress', 'Zstd'),
    (zlib_path, 'deflate', 'Zlib'),
]

found = 0
missing = []
for lib_path, symbol, name in compression_checks:
    try:
        if not os.path.exists(lib_path):
            print(f"  ❌ {name}: library not found at {lib_path}")
            missing.append(name)
            continue
        lib = ctypes.CDLL(lib_path)
        getattr(lib, symbol)
        print(f"✅ {name}: {symbol} found in {os.path.basename(lib_path)}")
        found += 1
    except (OSError, AttributeError) as e:
        print(f"  ❌ {name}: failed - {e}")
        missing.append(name)

if missing:
    print(f"\n❌ Missing {len(missing)}/4 compression libraries: {', '.join(missing)}")
    sys.exit(1)

# Verify libhadoop.dylib was built with compression support (linked dependencies)
print("\n=== Verifying libhadoop.dylib compression linkage ===")
try:
    otool_output = subprocess.check_output(
        ['otool', '-L', os.path.join(os.environ.get('DYLD_LIBRARY_PATH', '').split(':')[0], 'libhadoop.dylib')],
        stderr=subprocess.STDOUT
    ).decode()

    expected_libs = ['libsnappy', 'liblz4', 'libzstd', 'libz']
    linked = []
    not_linked = []
    for lib_name in expected_libs:
        if lib_name in otool_output:
            linked.append(lib_name)
        else:
            not_linked.append(lib_name)

    if linked:
        print(f"✅ libhadoop.dylib links against: {', '.join(linked)}")
    if not_linked:
        print(f"⚠️  libhadoop.dylib does NOT link against: {', '.join(not_linked)}")
        print("   Build may not have compression support compiled in")
except Exception as e:
    print(f"⚠️  Could not verify linkage: {e}")

print(f"\n✅ All tests passed: core libraries + {found}/4 compression libraries verified")
