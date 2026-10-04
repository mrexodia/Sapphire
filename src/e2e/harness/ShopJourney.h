#pragma once
// The gil-shop journey the quest scenarios buy their way through: which vendor
// is nearest to the quest NPC, what a quest-reward potion funds there, and the
// chain of level-1 equipment purchases (legs, feet, body, then head, ear, neck
// and wrist at other vendors) that the sale proceeds and the liquidated starter
// gear pay for. Every choice is made from the Shop, ShopItem and Item sheets and
// the navmesh at run time, the same way the old catalog tool made it.
#include "Content.h"

namespace Sapphire::E2E
{
  struct ShopListing
  {
    uint32_t shopId = 0;      // gil shop event id
    uint32_t index = 0;       // position in Shop.Item
    uint32_t item = 0;
    uint32_t price = 0;       // Item.Price: what the vendor charges, and pays back on a sale
    uint32_t sourceSlot = 0;  // Item.Slot (equip slot category); the gear slot is one less
    uint32_t stackMax = 1;
    uint32_t gearSlot() const { return sourceSlot - 1; }
  };

  struct ShopJourney
  {
    ShopRoute shop;                               // nearest vendor from the quest NPC, walked first
    uint32_t saleItem = 4551;                     // the Motivational Speaking reward potion
    uint32_t saleGil = 0;
    uint32_t starterLegs = 3296, starterBody = 2983, starterFeet = 3750;  // Gladiator starter gear sold on the way
    uint32_t starterLegsGil = 0, starterBodyGil = 0, starterFeetGil = 0;
    ShopListing purchase;                         // cheapest consumable the potion funds, bought as a stack
    uint32_t purchaseQuantity = 0;
    uint32_t itemActionRow = 0, itemActionType = 0, itemActionArg = 0;  // what using the purchase does
    ShopListing equipment, secondEquipment, thirdEquipment;  // at the first vendor, three different slots
    ShopRoute headShop;                           // from the first vendor
    ShopListing head;
    ShopRoute earShop;                            // from the head vendor
    ShopListing ear;
    ShopRoute neckShop;                           // from the ear vendor
    ShopListing neck;
    ShopListing wrist;                            // at the neck vendor
  };

  ShopJourney planShopJourney( GameData& data, uint16_t territory, const Point& start );
}
