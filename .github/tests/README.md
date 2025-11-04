# Testing libhdfs Native Libraries with PyArrow

This directory contains test scripts to verify that the compiled libhdfs native libraries work correctly with PyArrow and Ozone/HDFS.

## Prerequisites

### 1. Download libhdfs Artifacts

Download the compiled native libraries for your architecture from GitHub Actions:

```bash
# For Intel Mac (x86_64)
# Download artifact: libhdfs-3.3.6-macos-intel-x86_64

# For Apple Silicon Mac (arm64)
# Download artifact: libhdfs-3.3.6-macos-apple-silicon-arm64
```

Extract the artifact:
```bash
mkdir -p ~/libhdfs-artifacts
cd ~/libhdfs-artifacts
# Extract downloaded artifact here
# Should contain: libhdfs.dylib, libhdfs.a, libhadoop.dylib, libhadoop.a
```

### 2. Download Hadoop JARs

You need the Hadoop runtime JARs. Download from the build artifacts or Maven Central:

```bash
cd ~/libhdfs-artifacts
mkdir jars
cd jars

# Download Hadoop JARs (example for 3.3.6)
HADOOP_VERSION=3.3.6
wget https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-common/${HADOOP_VERSION}/hadoop-common-${HADOOP_VERSION}.jar
wget https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-hdfs/${HADOOP_VERSION}/hadoop-hdfs-${HADOOP_VERSION}.jar
wget https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-hdfs-client/${HADOOP_VERSION}/hadoop-hdfs-client-${HADOOP_VERSION}.jar

# Download dependencies (you can also copy from build artifacts)
# commons-logging, slf4j, etc.
```

### 3. Install Python Dependencies

```bash
# Install PyArrow with HDFS support
# Option 1: Pre-built wheel (may not have HDFS support)
pip install pyarrow pandas

# Option 2: Build from source with HDFS (recommended)
pip install --no-binary pyarrow pyarrow pandas
```

### 4. Setup Ozone or HDFS Cluster

You need a running Ozone or HDFS cluster for testing.

**Option A: Local HDFS with Docker**
```bash
docker run -d --name hadoop \
  -p 9000:9000 -p 9870:9870 \
  bde2020/hadoop-namenode:2.0.0-hadoop3.2.1-java8
```

**Option B: Use existing Ozone cluster**
```bash
# Configure HDFS_HOST and HDFS_PORT environment variables
export HDFS_HOST=your-ozone-host
export HDFS_PORT=9862  # Ozone default port
```

## Running Tests

### 1. Set Environment Variables

```bash
# Set HADOOP_HOME to libhdfs artifacts directory
export HADOOP_HOME=~/libhdfs-artifacts

# Set CLASSPATH to all Hadoop JARs
export CLASSPATH=$(find $HADOOP_HOME/jars -name "*.jar" | tr '\n' ':')

# Set library path for native libraries
export DYLD_LIBRARY_PATH=$HADOOP_HOME/native:$JAVA_HOME/lib/server

# Optional: Configure HDFS connection
export HDFS_HOST=localhost
export HDFS_PORT=9000
export HDFS_USER=hadoop
```

### 2. Run the Test Script

```bash
cd .github/tests
python3 test_libhdfs_pyarrow.py
```

## Expected Output

```
============================================================
libhdfs Native Library Test with PyArrow
============================================================

=== Library Information ===
PyArrow version: 14.0.1
PyArrow built with HDFS: True
✅ PyArrow has HDFS support

Environment:
  HADOOP_HOME: /Users/user/libhdfs-artifacts
  DYLD_LIBRARY_PATH: /Users/user/libhdfs-artifacts/native:/Library/Java/JavaVirtualMachines/...
  JAVA_HOME: /Library/Java/JavaVirtualMachines/...

✅ Environment variables set correctly

=== Testing HDFS Connection ===
Connecting to hdfs://localhost:9000 as user 'hadoop'
✅ Successfully connected to HDFS
   Root directory type: Directory

=== Testing Basic HDFS Operations ===
Creating directory: /tmp/libhdfs_test
  ✅ Directory created
Writing file: /tmp/libhdfs_test/test.txt
  ✅ File written
Reading file: /tmp/libhdfs_test/test.txt
  ✅ File read successfully, content matches
Listing directory: /tmp/libhdfs_test
  ✅ Found 1 items
Cleaning up: /tmp/libhdfs_test
  ✅ Directory deleted

=== Testing Compression Algorithms ===

Testing SNAPPY compression...
  ✅ snappy: Write/Read successful
     File size: 12,345 bytes (0.01 MB)

Testing GZIP compression...
  ✅ gzip: Write/Read successful
     File size: 8,234 bytes (0.01 MB)

Testing LZ4 compression...
  ✅ lz4: Write/Read successful
     File size: 11,123 bytes (0.01 MB)

Testing ZSTD compression...
  ✅ zstd: Write/Read successful
     File size: 7,890 bytes (0.01 MB)

=== Compression Test Summary ===
✅ Working compressions: snappy, gzip, lz4, zstd

============================================================
✅ Test suite completed
============================================================
```

## Troubleshooting

### PyArrow doesn't have HDFS support

```
❌ PyArrow was not built with HDFS support
```

**Solution:** Build PyArrow from source with HDFS enabled:
```bash
# Install build dependencies
brew install cmake

# Build PyArrow with HDFS
pip install --no-binary pyarrow pyarrow
```

### Library not loaded errors

```
Library not loaded: libhdfs.dylib
Reason: image not found
```

**Solution:** Check `DYLD_LIBRARY_PATH`:
```bash
export DYLD_LIBRARY_PATH=$HADOOP_HOME/native:$JAVA_HOME/lib/server
echo $DYLD_LIBRARY_PATH
ls -la $HADOOP_HOME/native/libhdfs.dylib  # Verify file exists
```

### ClassNotFoundException

```
java.lang.ClassNotFoundException: org.apache.hadoop.fs.FileSystem
```

**Solution:** Check `CLASSPATH`:
```bash
echo $CLASSPATH
# Should show all Hadoop JARs
ls $HADOOP_HOME/jars/*.jar
```

### Connection refused

```
Failed to connect to HDFS: [Errno 61] Connection refused
```

**Solution:**
- Verify HDFS/Ozone is running: `docker ps` or check cluster status
- Check host/port are correct
- Verify firewall allows connection

## Testing Specific Compression

To test only specific compression algorithms:

```python
# Modify test_libhdfs_pyarrow.py
test_compression(hdfs, compressions=['snappy'])  # Test only snappy
```

## Integration with CI/CD

You can add this test to GitHub Actions workflow as a manual test job:

```yaml
test-libraries:
  name: Test libhdfs libraries (manual)
  if: github.event_name == 'workflow_dispatch'
  needs: build-libhdfs
  runs-on: macos-13

  steps:
    - uses: actions/checkout@v4

    - name: Download artifacts
      uses: actions/download-artifact@v4
      with:
        name: libhdfs-3.3.6-macos-intel-x86_64
        path: ~/libhdfs-artifacts/native

    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: pip install pyarrow pandas

    - name: Run tests
      run: |
        export HADOOP_HOME=~/libhdfs-artifacts
        export CLASSPATH=$(find $HADOOP_HOME/jars -name "*.jar" | tr '\n' ':')
        export DYLD_LIBRARY_PATH=$HADOOP_HOME/native:$JAVA_HOME/lib/server
        python3 .github/tests/test_libhdfs_pyarrow.py
```

## Verifying Compression Support

The test verifies that the native libraries were built with compression support (Snappy, LZ4, Zstd, Zlib).

If any compression fails, it indicates the native library wasn't built with that codec.

Expected result:
- ✅ **Snappy** - fast compression
- ✅ **LZ4** - very fast compression
- ✅ **Zstd** - high compression ratio
- ✅ **Gzip/Zlib** - standard compression

All should work if libraries were built correctly.
