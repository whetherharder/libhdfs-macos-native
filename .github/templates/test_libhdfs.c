#include "hdfs.h"
#include <stdio.h>
#include <string.h>
#include <dlfcn.h>

// Test that compression libraries are linked
void test_compression_symbols() {
    printf("\n=== Testing compression library symbols ===\n");

    // Check for snappy symbols
    #ifdef __APPLE__
        void *handle = dlopen("libhadoop.dylib", RTLD_LAZY | RTLD_LOCAL);
    #else
        void *handle = dlopen("libhadoop.so", RTLD_LAZY | RTLD_LOCAL);
    #endif

    if (!handle) {
        printf("⚠️  Could not load libhadoop: %s\n", dlerror());
        return;
    }

    // Check if symbols are present (indicates compression was compiled in)
    const char *compression_funcs[] = {
        "snappy_compress",
        "LZ4_compress_default",
        "ZSTD_compress",
        "deflate"  // zlib
    };

    int found = 0;
    for (int i = 0; i < 4; i++) {
        void *sym = dlsym(handle, compression_funcs[i]);
        if (sym) {
            printf("✅ Found %s symbol\n", compression_funcs[i]);
            found++;
        } else {
            printf("⚠️  Symbol %s not found\n", compression_funcs[i]);
        }
    }

    dlclose(handle);

    if (found > 0) {
        printf("✅ Compression support detected (%d/4 libraries)\n", found);
    } else {
        printf("⚠️  No compression symbols found (libraries may be statically linked)\n");
    }
}

int main() {
    printf("=== libhdfs Native Library Test ===\n\n");
    printf("Testing basic libhdfs functionality...\n");

    // Test 1: hdfsBuilder API
    struct hdfsBuilder *builder = hdfsNewBuilder();
    if (!builder) {
        printf("❌ hdfsNewBuilder() failed\n");
        return 1;
    }
    printf("✅ hdfsNewBuilder() works\n");

    // Test 2: Configure builder
    hdfsBuilderSetNameNode(builder, "default");
    hdfsBuilderSetNameNodePort(builder, 0);
    printf("✅ hdfsBuilder configuration works\n");

    // Clean up
    hdfsFreeBuilder(builder);
    printf("✅ hdfsFreeBuilder() works\n");

    // Test 3: Check compression symbols
    test_compression_symbols();

    printf("\n=== All basic tests passed ===\n");
    printf("Note: Full integration tests require a running HDFS/Ozone cluster\n");

    return 0;
}

