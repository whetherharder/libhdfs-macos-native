
# Patch for macOS OpenSSL and ZLIB
# Supports both Intel (/usr/local) and Apple Silicon (/opt/homebrew)
if(APPLE)
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
