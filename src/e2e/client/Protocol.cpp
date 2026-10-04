#include "Protocol.h"
#include <Crypt/md5.h>
#include <Crypt/blowfish.h>
#include <chrono>

namespace Sapphire::Testing
{
  static_assert(sizeof(Wire::FFXIVARR_PACKET_HEADER) == 40);
  static_assert(sizeof(Wire::FFXIVARR_PACKET_SEGMENT_HEADER) == 16);
  static_assert(sizeof(Wire::FFXIVARR_IPC_HEADER) == 16);

  uint64_t timeMillis()
  {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
      std::chrono::system_clock::now().time_since_epoch()).count();
  }
  uint32_t timeSeconds() { return static_cast<uint32_t>(timeMillis() / 1000); }

  std::vector<Segment> Decoder::feed(const uint8_t* data, size_t size)
  {
    if(size > MaxFrame || m_buffer.size() + size > 2 * MaxFrame)
      throw ProtocolError("receive buffer limit exceeded");
    if(size) m_buffer.insert(m_buffer.end(), data, data + size);
    std::vector<Segment> result;
    size_t consumed = 0;
    while(m_buffer.size() - consumed >= sizeof(Wire::FFXIVARR_PACKET_HEADER))
    {
      const auto h = readObject<Wire::FFXIVARR_PACKET_HEADER>(m_buffer, consumed);
      if(h.size < sizeof(h) || h.size > MaxFrame || h.count > 255)
        throw ProtocolError("invalid frame length/count");
      if(h.isCompressed) throw ProtocolError("compressed frames are unsupported by this profile");
      if(m_buffer.size() - consumed < h.size) break;
      size_t cursor = consumed + sizeof(h);
      const size_t end = consumed + h.size;
      for(size_t n = 0; n < h.count; ++n)
      {
        if(end - cursor < sizeof(Wire::FFXIVARR_PACKET_SEGMENT_HEADER))
          throw ProtocolError("truncated segment header");
        const auto s = readObject<Wire::FFXIVARR_PACKET_SEGMENT_HEADER>(m_buffer, cursor);
        if(s.size < sizeof(s) || s.size > end - cursor)
          throw ProtocolError("invalid segment length");
        result.push_back({s, Bytes(m_buffer.begin() + cursor + sizeof(s), m_buffer.begin() + cursor + s.size)});
        cursor += s.size;
      }
      if(cursor != end) throw ProtocolError("frame count/length mismatch");
      consumed = end;
    }
    m_buffer.erase(m_buffer.begin(), m_buffer.begin() + consumed);
    return result;
  }

  Bytes frame(uint16_t channel, uint16_t type, const Bytes& payload, uint32_t actor)
  {
    Wire::FFXIVARR_PACKET_SEGMENT_HEADER s{};
    s.size = static_cast<uint32_t>((sizeof(s) + payload.size() + 7) & ~size_t(7));
    s.source_actor = actor;
    s.target_actor = actor;
    s.type = type;
    Wire::FFXIVARR_PACKET_HEADER h{};
    h.unknown_0 = 0xE2465DFF41A05252;
    h.unknown_8 = 0x75C4997B4D642A7F;
    h.timestamp = timeMillis();
    h.size = sizeof(h) + s.size;
    if(h.size > Decoder::MaxFrame) throw ProtocolError("outgoing frame too large");
    h.connectionType = channel;
    h.count = 1;
    h.unknown_20 = 1;
    Bytes bytes(h.size, 0);
    std::memcpy(bytes.data(), &h, sizeof(h));
    std::memcpy(bytes.data() + sizeof(h), &s, sizeof(s));
    if(!payload.empty()) std::memcpy(bytes.data() + sizeof(h) + sizeof(s), payload.data(), payload.size());
    return bytes;
  }

  Bytes ipc(uint16_t opcode, const Bytes& payload)
  {
    Wire::FFXIVARR_IPC_HEADER h{};
    h.reserved = 0x14;
    h.type = opcode;
    h.timestamp = timeSeconds();
    auto result = objectBytes(h);
    result.insert(result.end(), payload.begin(), payload.end());
    result.resize((result.size() + 7) & ~size_t(7), 0);
    return result;
  }

  Bytes LobbyCipher::initialize(uint32_t nonce, const std::string& phrase)
  {
    if(phrase.size() >= 32) throw ProtocolError("lobby key phrase too long");
    struct Base { uint32_t magic, key, version; char phrase[32]; } base{};
    static_assert(sizeof(base) == 44);
    base.magic = 0x12345678;
    base.key = nonce;
    base.version = 3000;
    copyText(base.phrase, phrase);
    auto bytes = objectBytes(base);
    Common::Util::md5(bytes.data(), m_key.data(), static_cast<int32_t>(bytes.size()));
    Bytes handshake(104, 0);
    std::memcpy(handshake.data() + 36, phrase.c_str(), phrase.size() + 1);
    std::memcpy(handshake.data() + 100, &nonce, sizeof(nonce));
    return handshake;
  }

  void LobbyCipher::encrypt(Bytes& data) const
  {
    if(data.empty() || data.size() % 8) throw ProtocolError("unaligned lobby payload");
    BlowFish cipher;
    auto key = m_key;
    cipher.initialize(key.data(), static_cast<int32_t>(key.size()));
    cipher.Encode(data.data(), data.data(), static_cast<uint32_t>(data.size()));
  }
  void LobbyCipher::decrypt(Bytes& data) const
  {
    if(data.empty() || data.size() % 8) throw ProtocolError("unaligned lobby payload");
    BlowFish cipher;
    auto key = m_key;
    cipher.initialize(key.data(), static_cast<int32_t>(key.size()));
    cipher.Decode(data.data(), data.data(), static_cast<uint32_t>(data.size()));
  }
}
