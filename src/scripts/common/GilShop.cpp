#include <ScriptObject.h>
#include <Actor/Player.h>

#include <Manager/ShopMgr.h>
#include <Service.h>
#include <Logging/Logger.h>

using namespace Sapphire;

class GilShop :
  public Sapphire::ScriptAPI::EventScript
{
public:
  GilShop() :
    Sapphire::ScriptAPI::EventScript( 0x00040000 )
  {
  }

  constexpr static auto SCENE_FLAGS = HIDE_HOTBAR | NO_DEFAULT_CAMERA;

  void onTalk( uint32_t eventId, Entity::Player& player, uint64_t actorId ) override
  {
    eventMgr().playScene( player, eventId, 0, SCENE_FLAGS, { 2 }, std::bind( &GilShop::shopCallback, this, std::placeholders::_1, std::placeholders::_2 ) );
  }

private:
  void shopInteractionCallback( Entity::Player& player, const Event::SceneResult& result )
  {
    // item purchase
    if( result.numOfResults == 255 )
    {
      // buy
      if( result.getResult( 1 ) == 1 )
      {
        auto& shopMgr = Common::Service< Sapphire::World::Manager::ShopMgr >::ref();
        shopMgr.purchaseGilShopItem( player, result.getResult( 4 ), result.getResult( 6 ), result.getResult( 5 ) );
      }

      // sell
      // can't sell if the vendor is yourself (eg, housing permit shop)
      else if( result.getResult( 1 ) == 2 && result.actorId != player.getId() )
      {
        auto& shopMgr = Common::Service< Sapphire::World::Manager::ShopMgr >::ref();
        shopMgr.sellGilShopItem( player, result.getResult( 2 ), result.getResult( 3 ), result.getResult( 6 ), result.getResult( 5 ) );
      }

      eventMgr().playGilShop( player, result.eventId, SCENE_FLAGS, result.getResult( 0 ), [ & ]( Entity::Player& player, const Event::SceneResult& result )
      {
        shopInteractionCallback( player, result );
      });
      return;
    }

    // exit: the client closes the window with a single result
    if( result.numOfResults <= 1 )
    {
      eventMgr().eventFinish( player, result.eventId, 1 );
      return;
    }

    // buyback: five results, 0, 3, list index, quantity, unit price (captured from a real client)
    if( result.numOfResults == 5 && result.getResult( 1 ) == 3 )
    {
      auto& shopMgr = Common::Service< Sapphire::World::Manager::ShopMgr >::ref();
      shopMgr.buybackGilShopItem( player, result.getResult( 2 ), result.getResult( 3 ) );
    }
    else
    {
      // Finishing the event on an unknown command closes the window under the player
      // mid-action and leaves the client "occupied" until it relogs, so keep the shop open.
      Logger::debug( "GilShop: unsupported shop command {} ({} results) from {}, re-listing",
                     result.getResult( 1 ), result.numOfResults, player.getId() );
    }

    // Re-list so the window shows the updated buyback entries, like after a buy or sell.
    eventMgr().playGilShop( player, result.eventId, SCENE_FLAGS, 0, [ & ]( Entity::Player& player, const Event::SceneResult& result )
    {
      shopInteractionCallback( player, result );
    });
  }

  void shopCallback( Entity::Player& player, const Event::SceneResult& result )
  {
    eventMgr().playGilShop( player, result.eventId, SCENE_FLAGS, 0, [ & ]( Entity::Player& player, const Event::SceneResult& result )
    {
      shopInteractionCallback( player, result );
    });
  }
};

EXPOSE_SCRIPT( GilShop );