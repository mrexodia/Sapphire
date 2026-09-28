#pragma once

#include <Network/CommonNetwork.h>
#include <array>
#include <cstring>
#include <stdexcept>
#include <string>
#include <type_traits>

namespace Sapphire::Testing
{
  namespace Wire = Network::Packets;
  using Bytes = std::vector<uint8_t>;

  struct ProtocolError : std::runtime_error { using std::runtime_error::runtime_error; };

  template<class T> T readObject(const Bytes& bytes, size_t offset = 0)
  {
    static_assert(std::is_trivially_copyable_v<T>);
    if(offset > bytes.size() || sizeof(T) > bytes.size() - offset)
      throw ProtocolError("truncated packet payload");
    T value{};
    std::memcpy(&value, bytes.data() + offset, sizeof(T));
    return value;
  }

  template<class T> Bytes objectBytes(const T& value)
  {
    static_assert(std::is_trivially_copyable_v<T>);
    Bytes result(sizeof(T));
    std::memcpy(result.data(), &value, sizeof(T));
    return result;
  }

  template<size_t N> void copyText(char (&dest)[N], const std::string& source)
  {
    if(source.size() >= N || source.find('\0') != std::string::npos)
      throw ProtocolError("text does not fit protocol field");
    std::memcpy(dest, source.c_str(), source.size() + 1);
  }

  template<size_t N> std::string text(const char (&source)[N])
  {
    auto end = static_cast<const char*>(std::memchr(source, 0, N));
    if(!end) throw ProtocolError("unterminated protocol string");
    return {source, end};
  }

  struct Segment
  {
    Wire::FFXIVARR_PACKET_SEGMENT_HEADER header{};
    Bytes data;
  };

  class Decoder
  {
  public:
    static constexpr size_t MaxFrame = 1024 * 1024;
    std::vector<Segment> feed(const uint8_t* data, size_t size);
  private:
    Bytes m_buffer;
  };

  Bytes frame(uint16_t channel, uint16_t type, const Bytes& payload, uint32_t actor = 0);
  Bytes ipc(uint16_t opcode, const Bytes& payload);
  uint32_t timeSeconds();
  uint64_t timeMillis();
  inline bool questCompletionFlag(const uint8_t* bytes, size_t byteCount, size_t questId)
  {
    if(questId / 8 >= byteCount) throw ProtocolError("quest flag index out of range");
    // Quest completion uses MSB-first bits, unlike player condition flags.
    return (bytes[questId / 8] & (0x80u >> (questId % 8))) != 0;
  }

  class LobbyCipher
  {
  public:
    // The key exchange is the version-3000 Sapphire lobby profile.
    Bytes initialize(uint32_t nonce, const std::string& phrase);
    void encrypt(Bytes& data) const;
    void decrypt(Bytes& data) const;
  private:
    std::array<uint8_t, 16> m_key{};
  };
}
