#include "Protocol.h"
#include "RespawnActions.h"
#include "ShopActions.h"
#include "TransitionActions.h"
#include <Crypt/Random.h>
#include <algorithm>
#include <set>
#include <Network/PacketDef/Lobby/ClientLobbyDef.h>
#include <Network/PacketDef/Zone/ClientZoneDef.h>
#include <Network/PacketDef/Zone/ServerZoneDef.h>
#include <iostream>

using namespace Sapphire::Testing;
void require(bool value, const char* message)
{
  if(!value) throw std::runtime_error(message);
}
template<class F> void rejects(F action)
{
  bool rejected = false;
  try { action(); } catch(const ProtocolError&) { rejected = true; }
  require(rejected, "expected protocol rejection");
}
int main()
{
  try
  {
    std::set<std::string> tokens;
    for(int i = 0; i < 100; ++i)
    {
      auto token = Sapphire::Common::Util::randomHexToken(31);
      require(token.size() == 62 && token.find_first_not_of("0123456789abcdef") == std::string::npos,
        "session token wire format");
      require(tokens.insert(token).second, "independent session tokens");
    }
    // Explicit wire layout checks, in addition to roundtrips using shared definitions.
    using namespace Wire::WorldPackets;
    static_assert(sizeof(Client::FFXIVIpcUpdatePosition) == 24);
    static_assert(sizeof(Client::FFXIVIpcEventHandlerTalk) == 16);
    static_assert(sizeof(Client::FFXIVIpcReturnEventScene2) == 16);
    static_assert(sizeof(Server::FFXIVIpcActorMove) == 16);
    static_assert(sizeof(Server::FFXIVIpcQuestFinish) == 8);
    auto payload = ipc(0x1234, Bytes{1, 2, 3, 4});
    require(payload.size() == 24 && payload[0] == 0x14 && payload[2] == 0x34 && payload[3] == 0x12,
      "IPC little-endian header fixture");
    auto bytes = frame(1, 3, payload, 0x10203040);
    require(bytes.size() == 80 && bytes[24] == 80 && bytes[28] == 1 && bytes[30] == 1,
      "bundle length/channel/count fixture");
    require(bytes[40] == 40 && bytes[44] == 0x40 && bytes[47] == 0x10 && bytes[52] == 3,
      "segment length/source/type fixture");

    for(size_t split = 0; split <= bytes.size(); ++split)
    {
      Decoder decoder;
      auto first = decoder.feed(bytes.data(), split);
      auto second = decoder.feed(bytes.data() + split, bytes.size() - split);
      require(first.size() + second.size() == 1, "every TCP split delivers exactly once");
    }
    Decoder bytewise;
    size_t delivered = 0;
    for(auto byte : bytes) delivered += bytewise.feed(&byte, 1).size();
    require(delivered == 1, "one-byte reads");
    auto two = bytes; two.insert(two.end(), bytes.begin(), bytes.end());
    Decoder coalesced;
    auto segments = coalesced.feed(two.data(), two.size());
    require(segments.size() == 2 && segments[0].data == payload && segments[1].data == payload,
      "coalesced TCP frames");
    for(auto offset : {24, 40})
    {
      auto bad = bytes; bad[offset] = 0;
      rejects([&] { Decoder d; d.feed(bad.data(), bad.size()); });
    }
    auto compressed = bytes; compressed[33] = 1;
    rejects([&] { Decoder d; d.feed(compressed.data(), compressed.size()); });
    auto count = bytes; count[30] = 0;
    rejects([&] { Decoder d; d.feed(count.data(), count.size()); });
    rejects([&] { readObject<uint64_t>(Bytes(7)); });
    rejects([&] { readObject<uint16_t>(Bytes(8), 9); });
    char shortField[4]{};
    rejects([&] { copyText(shortField, "abcd"); });
    char unterminated[2]{'a', 'b'};
    rejects([&] { text(unterminated); });

    // Independent completion-list fixture: quest 150 is byte 18, bit 0x02.
    // The incremental completion packet carries 150 directly; it is not byte order.
    std::array<uint8_t, 310> completion{};
    completion[18] = 0x02;
    require(questCompletionFlag(completion.data(), completion.size(), 150), "quest flag MSB order");
    require(!questCompletionFlag(completion.data(), completion.size(), 145), "quest flag must not use condition-bit order");
    rejects([&] { questCompletionFlag(completion.data(), completion.size(), completion.size() * 8); });

    nlohmann::json exit{{"id", 0x01020304}, {"territory", 130}, {"enabled", true},
      {"shape", 1}, {"exit_type", 1}, {"position", {1, 2, 3}}, {"scale", {4, 6, 8}}, {"rotation", {0, 1.57, 0}}};
    const Bytes expectedExit{4,3,2,1, 0,0,0x80,0x3f, 0,0,0,0x40, 0,0,0x40,0x40, 0,0,0,0};
    require(exitRangeRequest(130, {1,2,3}, exit) == expectedExit, "exit request independent byte fixture");
    rejects([&] { exitRangeRequest(131, {1,2,3}, exit); });
    rejects([&] { exitRangeRequest(130, {4,2,3}, exit); });
    rejects([&] { exitRangeRequest(130, {1,6,3}, exit); });
    auto disabledExit = exit; disabledExit["enabled"] = false;
    rejects([&] { exitRangeRequest(130, {1,2,3}, disabledExit); });
    auto tiltedExit = exit; tiltedExit["rotation"][0] = 0.1;
    rejects([&] { exitRangeRequest(130, {1,2,3}, tiltedExit); });

    nlohmann::json defeatedActors = {{"2097153", {{"hp", 0}}}};
    auto homepoint = returnHomepointRequest(2097153, 141, 9, defeatedActors);
    require(homepoint.size() == 32 && homepoint[0] == 0xC8 && homepoint[4] == 8 &&
            std::all_of(homepoint.begin() + 8, homepoint.end(), [](uint8_t byte) { return byte == 0; }),
            "homepoint return command fixture");
    rejects([&] { returnHomepointRequest(2097153, 130, 9, defeatedActors); });
    rejects([&] { returnHomepointRequest(2097153, 141, 8, defeatedActors); });
    defeatedActors["2097153"]["hp"] = 1;
    rejects([&] { returnHomepointRequest(2097153, 141, 9, defeatedActors); });

    auto sale = shopSaleReturn(0x00040005, 3, 24, 4551);
    require(sale.size() == 1028 && sale[0] == 5 && sale[2] == 4 && sale[4] == 40 && sale[7] == 255,
            "shop sale return header fixture");
    require(sale[12] == 2 && sale[16] == 3 && sale[20] == 24 && sale[28] == 1 &&
            sale[32] == 0xC7 && sale[33] == 0x11, "shop sale result offsets fixture");
    rejects([&] { shopSaleReturn(0x00010005, 3, 24, 4551); });
    rejects([&] { shopSaleReturn(0x00040005, 4, 24, 4551); });
    rejects([&] { shopSaleReturn(0x00040005, 3, 25, 4551); });

    LobbyCipher sender, receiver;
    auto hello = sender.initialize(42, "SapphireE2E");
    receiver.initialize(42, "SapphireE2E");
    require(hello.size() == 104 && hello[100] == 42 && hello[36] == 'S', "handshake fixture");
    auto encrypted = payload; sender.encrypt(encrypted);
    require(encrypted != payload, "encryption changes payload");
    receiver.decrypt(encrypted); require(encrypted == payload, "lobby cipher roundtrip");
    rejects([&] { Bytes bad(3); sender.encrypt(bad); });
    std::cout << "Protocol layout, stream assembly, bounds, and lobby cipher tests passed\n";
    return 0;
  }
  catch(const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
