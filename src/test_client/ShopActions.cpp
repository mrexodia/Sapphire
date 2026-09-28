#include "ShopActions.h"
#include <Network/PacketDef/Zone/ClientZoneDef.h>

namespace Sapphire::Testing
{
  Bytes shopSaleReturn(uint32_t eventId, uint16_t storage, uint16_t slot, uint16_t itemId)
  {
    if((eventId >> 16) != 4 || storage > 3 || slot >= 25 || !itemId)
      throw ProtocolError("invalid bounded gil-shop sale return");
    Wire::WorldPackets::Client::FFXIVIpcReturnEventScene255 packet{};
    packet.handlerId = eventId;
    packet.sceneId = 40;
    packet.numOfResults = 255;
    packet.results[0] = 0;
    packet.results[1] = 2;
    packet.results[2] = storage;
    packet.results[3] = slot;
    packet.results[5] = 1;
    packet.results[6] = itemId;
    return objectBytes(packet);
  }
}
