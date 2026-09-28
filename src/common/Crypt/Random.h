#pragma once
#include <cstddef>
#include <string>

namespace Sapphire::Common::Util
{
  // Hex encoding of OS-provided random bytes; throws if entropy acquisition fails.
  std::string randomHexToken(std::size_t byteCount);
}
