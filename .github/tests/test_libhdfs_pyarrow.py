#!/usr/bin/env python3
"""
Test script for verifying libhdfs native libraries work with PyArrow and Ozone/HDFS.

This script tests:
- Connection to Ozone/HDFS via libhdfs
- Writing Parquet files with compression (snappy, lz4, zstd, gzip)
- Reading Parquet files back
- Verifying data integrity

Requirements:
- pyarrow with HDFS support
- Ozone or HDFS cluster running
- libhdfs native libraries in DYLD_LIBRARY_PATH
- Hadoop JARs in CLASSPATH
"""

import os
import sys
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.fs as fs
import pandas as pd
from datetime import datetime

def check_environment():
    """Verify required environment variables are set."""
    required_vars = ['HADOOP_HOME', 'CLASSPATH', 'DYLD_LIBRARY_PATH']
    missing = []

    for var in required_vars:
        if not os.environ.get(var):
            missing.append(var)

    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        print("\nPlease set:")
        print("  export HADOOP_HOME=/path/to/libhdfs-artifacts")
        print("  export CLASSPATH=$(find $HADOOP_HOME/jars -name '*.jar' | tr '\\n' ':')")
        print("  export DYLD_LIBRARY_PATH=$HADOOP_HOME/native:$JAVA_HOME/lib/server")
        return False

    print("✅ Environment variables set correctly")
    return True

def test_hdfs_connection(host='localhost', port=9000, user='hadoop'):
    """Test connection to HDFS/Ozone."""
    try:
        print(f"\n=== Testing HDFS Connection ===")
        print(f"Connecting to hdfs://{host}:{port} as user '{user}'")

        hdfs = fs.HadoopFileSystem(host=host, port=port, user=user)

        # Try to list root directory
        info = hdfs.get_file_info('/')
        print(f"✅ Successfully connected to HDFS")
        print(f"   Root directory type: {info.type}")

        return hdfs
    except Exception as e:
        print(f"❌ Failed to connect to HDFS: {e}")
        print(f"\nNote: This test requires a running HDFS/Ozone cluster")
        print(f"      Adjust host/port if needed")
        return None

def create_test_data():
    """Create test DataFrame with various data types."""
    return pd.DataFrame({
        'id': range(1000),
        'name': [f'user_{i}' for i in range(1000)],
        'value': [i * 1.5 for i in range(1000)],
        'timestamp': [datetime(2024, 1, 1, 12, 0, 0) for _ in range(1000)],
        'is_active': [i % 2 == 0 for i in range(1000)]
    })

def test_compression(hdfs, test_path='/tmp/libhdfs_test', compressions=['snappy', 'gzip', 'lz4', 'zstd']):
    """Test writing and reading with different compression algorithms."""

    if not hdfs:
        print("\n⚠️  Skipping compression tests (no HDFS connection)")
        return None

    print(f"\n=== Testing Compression Algorithms ===")
    df = create_test_data()
    table = pa.Table.from_pandas(df)

    results = {}

    for compression in compressions:
        try:
            file_path = f"{test_path}/test_{compression}.parquet"

            # Write with compression
            print(f"\nTesting {compression.upper()} compression...")
            with hdfs.open_output_stream(file_path) as out:
                pq.write_table(table, out, compression=compression)

            # Get file size
            file_info = hdfs.get_file_info(file_path)
            file_size = file_info.size

            # Read back
            with hdfs.open_input_stream(file_path) as inp:
                table_read = pq.read_table(inp)

            # Verify data
            df_read = table_read.to_pandas()
            if df.equals(df_read):
                print(f"  ✅ {compression}: Write/Read successful")
                print(f"     File size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
                results[compression] = {'success': True, 'size': file_size}
            else:
                print(f"  ❌ {compression}: Data mismatch after read")
                results[compression] = {'success': False, 'error': 'Data mismatch'}

            # Cleanup
            hdfs.delete_file(file_path)

        except Exception as e:
            print(f"  ❌ {compression}: Failed - {e}")
            results[compression] = {'success': False, 'error': str(e)}

    # Print summary
    print(f"\n=== Compression Test Summary ===")
    successful = [k for k, v in results.items() if v.get('success')]
    failed = [k for k, v in results.items() if not v.get('success')]

    if successful:
        print(f"✅ Working compressions: {', '.join(successful)}")
    if failed:
        print(f"❌ Failed compressions: {', '.join(failed)}")

    return results

def test_basic_operations(hdfs, test_path='/tmp/libhdfs_test'):
    """Test basic HDFS operations."""

    if not hdfs:
        print("\n⚠️  Skipping basic operations tests (no HDFS connection)")
        return False

    print(f"\n=== Testing Basic HDFS Operations ===")

    try:
        # Create directory
        print(f"Creating directory: {test_path}")
        hdfs.create_dir(test_path)
        print(f"  ✅ Directory created")

        # Write a simple file
        test_file = f"{test_path}/test.txt"
        test_content = b"Hello from libhdfs native library!\n"

        print(f"Writing file: {test_file}")
        with hdfs.open_output_stream(test_file) as out:
            out.write(test_content)
        print(f"  ✅ File written")

        # Read the file back
        print(f"Reading file: {test_file}")
        with hdfs.open_input_stream(test_file) as inp:
            content = inp.read()

        if content == test_content:
            print(f"  ✅ File read successfully, content matches")
        else:
            print(f"  ❌ Content mismatch!")
            return False

        # List directory
        print(f"Listing directory: {test_path}")
        selector = fs.FileSelector(test_path)
        files = hdfs.get_file_info(selector)
        print(f"  ✅ Found {len(files)} items")

        return True

    except Exception as e:
        print(f"❌ Basic operations failed: {e}")
        return False

    finally:
        # Always attempt cleanup
        try:
            print(f"Cleaning up: {test_path}")
            hdfs.delete_dir(test_path)
            print(f"  ✅ Directory deleted")
        except Exception:
            print(f"  ⚠️  Cleanup failed (may not exist)")

def print_library_info():
    """Print information about loaded libraries."""
    print("\n=== Library Information ===")
    print(f"PyArrow version: {pa.__version__}")
    print(f"PyArrow built with HDFS: {pa.have_libhdfs()}")

    if pa.have_libhdfs():
        print(f"✅ PyArrow has HDFS support")
    else:
        print(f"❌ PyArrow does NOT have HDFS support")
        print(f"   You may need to rebuild pyarrow with --enable-hdfs")

    print(f"\nEnvironment:")
    print(f"  HADOOP_HOME: {os.environ.get('HADOOP_HOME', 'NOT SET')}")
    print(f"  DYLD_LIBRARY_PATH: {os.environ.get('DYLD_LIBRARY_PATH', 'NOT SET')}")
    print(f"  JAVA_HOME: {os.environ.get('JAVA_HOME', 'NOT SET')}")

def main():
    """Main test runner."""
    print("=" * 60)
    print("libhdfs Native Library Test with PyArrow")
    print("=" * 60)

    # Print library info
    print_library_info()

    # Check environment
    if not check_environment():
        sys.exit(1)

    # Check if PyArrow has HDFS support
    if not pa.have_libhdfs():
        print("\n❌ PyArrow was not built with HDFS support")
        print("   Install with: pip install pyarrow --no-binary pyarrow")
        print("   Or build from source with HDFS enabled")
        sys.exit(1)

    # Configuration (modify as needed)
    hdfs_host = os.environ.get('HDFS_HOST', 'localhost')
    hdfs_port = int(os.environ.get('HDFS_PORT', '9000'))
    hdfs_user = os.environ.get('HDFS_USER', 'hadoop')

    # Test connection
    hdfs = test_hdfs_connection(host=hdfs_host, port=hdfs_port, user=hdfs_user)

    # Run tests and track failures
    failures = 0

    basic_result = test_basic_operations(hdfs)
    if basic_result is False:
        failures += 1

    compression_results = test_compression(hdfs)
    if compression_results is not None:
        failed_compressions = [k for k, v in compression_results.items() if not v.get('success')]
        if failed_compressions:
            failures += 1

    print("\n" + "=" * 60)
    if failures > 0:
        print(f"❌ Test suite completed with {failures} failure(s)")
        print("=" * 60)
        sys.exit(1)
    else:
        print("✅ Test suite completed successfully")
        print("=" * 60)

if __name__ == '__main__':
    main()
