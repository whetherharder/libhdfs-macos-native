
# Patch for macOS OpenSSL and ZLIB
# Supports both Intel (/usr/local) and Apple Silicon (/opt/homebrew)
if(APPLE)
  # Detect and set target architecture explicitly
  execute_process(
    COMMAND uname -m
    OUTPUT_VARIABLE NATIVE_ARCH
    OUTPUT_STRIP_TRAILING_WHITESPACE
  )

  if(NATIVE_ARCH STREQUAL "arm64")
    set(CMAKE_OSX_ARCHITECTURES "arm64" CACHE STRING "Target architecture" FORCE)
    message(STATUS "Building for Apple Silicon (arm64)")
  elseif(NATIVE_ARCH STREQUAL "x86_64")
    set(CMAKE_OSX_ARCHITECTURES "x86_64" CACHE STRING "Target architecture" FORCE)
    message(STATUS "Building for Intel (x86_64)")
  else()
    message(WARNING "Unknown architecture: ${NATIVE_ARCH}, using default")
  endif()

  # Fix OpenSSL paths - use environment variable set by workflow
  if(DEFINED ENV{OPENSSL_ROOT_DIR})
    set(OPENSSL_ROOT_DIR $ENV{OPENSSL_ROOT_DIR})
    message(STATUS "Using OpenSSL from env: ${OPENSSL_ROOT_DIR}")
  else()
    message(WARNING "OPENSSL_ROOT_DIR environment variable not set!")
  endif()

  if(OPENSSL_ROOT_DIR)
    set(OPENSSL_INCLUDE_DIR "${OPENSSL_ROOT_DIR}/include")
    set(OPENSSL_CRYPTO_LIBRARY "${OPENSSL_ROOT_DIR}/lib/libcrypto.dylib")
    set(OPENSSL_SSL_LIBRARY "${OPENSSL_ROOT_DIR}/lib/libssl.dylib")
    include_directories(${OPENSSL_INCLUDE_DIR})
    message(STATUS "OpenSSL include: ${OPENSSL_INCLUDE_DIR}")
    message(STATUS "OpenSSL crypto: ${OPENSSL_CRYPTO_LIBRARY}")
    message(STATUS "OpenSSL ssl: ${OPENSSL_SSL_LIBRARY}")
  endif()

  # ZLIB is usually found automatically by CMake on macOS
  # No hardcoded paths needed
endif()
