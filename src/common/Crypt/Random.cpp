#include "Random.h"
#include <array>
#include <stdexcept>

#ifdef _WIN32
#include <windows.h>
#include <bcrypt.h>
#elif defined(__linux__)
#include <sys/random.h>
#include <cerrno>
#elif defined(__APPLE__)
#include <cstdlib>
#else
#error Unsupported OS random source
#endif

std::string Sapphire::Common::Util::randomHexToken(std::size_t byteCount)
{
  // All current uses are session IDs; keep allocations and OS API sizes bounded.
  if(byteCount == 0 || byteCount > 256)
    throw std::invalid_argument("random token size must be between 1 and 256 bytes");
  std::array<unsigned char, 256> bytes{};
#ifdef _WIN32
  if(BCryptGenRandom(nullptr, bytes.data(), static_cast<ULONG>(byteCount), BCRYPT_USE_SYSTEM_PREFERRED_RNG) != 0)
    throw std::runtime_error("OS random generation failed");
#elif defined(__linux__)
  std::size_t filled = 0;
  while(filled < byteCount)
  {
    auto count = getrandom(bytes.data() + filled, byteCount - filled, 0);
    if(count < 0 && errno == EINTR) continue;
    if(count <= 0) throw std::runtime_error("OS random generation failed");
    filled += static_cast<std::size_t>(count);
  }
#elif defined(__APPLE__)
  arc4random_buf(bytes.data(), byteCount);
#endif
  constexpr char hex[] = "0123456789abcdef";
  std::string result;
  result.reserve(byteCount * 2);
  for(std::size_t i = 0; i < byteCount; ++i)
  {
    result += hex[bytes[i] >> 4];
    result += hex[bytes[i] & 15];
  }
  return result;
}
