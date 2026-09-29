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

  Bytes shopPurchaseReturn(uint32_t eventId)
  {
    constexpr uint32_t supportedShop = 262468;
    constexpr uint16_t supportedItem = 5890;
    if(eventId != supportedShop) throw ProtocolError("unsupported bounded gil-shop purchase");
    Wire::WorldPackets::Client::FFXIVIpcReturnEventScene255 packet{};
    packet.handlerId = eventId;
    packet.sceneId = 40;
    packet.numOfResults = 255;
    packet.results[0] = 0;
    packet.results[1] = 1;
    packet.results[4] = supportedShop;
    packet.results[5] = 3;
    packet.results[6] = supportedItem;
    return objectBytes(packet);
  }

  Bytes shopEquipmentPurchaseReturn(uint32_t eventId)
  {
    constexpr uint32_t supportedShop = 262468;
    if(eventId != supportedShop) throw ProtocolError("unsupported bounded equipment purchase");
    Wire::WorldPackets::Client::FFXIVIpcReturnEventScene255 packet{};
    packet.handlerId = eventId;
    packet.sceneId = 40;
    packet.numOfResults = 255;
    packet.results[0] = 0;
    packet.results[1] = 1;
    packet.results[4] = supportedShop;
    packet.results[5] = 1;
    packet.results[6] = 3286;
    return objectBytes(packet);
  }

  Bytes shopSecondEquipmentPurchaseReturn(uint32_t eventId)
  {
    constexpr uint32_t supportedShop = 262468;
    if(eventId != supportedShop) throw ProtocolError("unsupported bounded second equipment purchase");
    Wire::WorldPackets::Client::FFXIVIpcReturnEventScene255 packet{};
    packet.handlerId = eventId;
    packet.sceneId = 40;
    packet.numOfResults = 255;
    packet.results[0] = 0;
    packet.results[1] = 1;
    packet.results[4] = supportedShop;
    packet.results[5] = 1;
    packet.results[6] = 3748;
    return objectBytes(packet);
  }

  Bytes shopThirdEquipmentPurchaseReturn(uint32_t eventId)
  {
    constexpr uint32_t supportedShop = 262468;
    if(eventId != supportedShop) throw ProtocolError("unsupported bounded third equipment purchase");
    Wire::WorldPackets::Client::FFXIVIpcReturnEventScene255 packet{};
    packet.handlerId = eventId;
    packet.sceneId = 40;
    packet.numOfResults = 255;
    packet.results[0] = 0;
    packet.results[1] = 1;
    packet.results[4] = supportedShop;
    packet.results[5] = 1;
    packet.results[6] = 2967;
    return objectBytes(packet);
  }

  Bytes shopHeadEquipmentPurchaseReturn(uint32_t eventId)
  {
    constexpr uint32_t supportedShop = 262415;
    if(eventId != supportedShop) throw ProtocolError("unsupported bounded head-equipment purchase");
    Wire::WorldPackets::Client::FFXIVIpcReturnEventScene255 packet{};
    packet.handlerId = eventId;
    packet.sceneId = 40;
    packet.numOfResults = 255;
    packet.results[0] = 0;
    packet.results[1] = 1;
    packet.results[4] = supportedShop;
    packet.results[5] = 1;
    packet.results[6] = 2638;
    return objectBytes(packet);
  }
}
