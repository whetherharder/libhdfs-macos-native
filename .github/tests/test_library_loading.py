#!/usr/bin/env python3
"""Basic test to verify libhdfs libraries can be loaded."""
import ctypes
import os
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

# Check for compression symbols
compression_funcs = ['snappy_compress', 'LZ4_compress_default', 'ZSTD_compress', 'deflate']
found = 0
for func in compression_funcs:
    try:
        getattr(libhadoop, func)
        print(f"✅ Found {func} symbol")
        found += 1
    except:
        pass

print(f"\n✅ Basic library test passed ({found}/4 compression libraries detected)")
