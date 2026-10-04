#include <Actor/Player.h>
#include <ScriptObject.h>
#include <Service.h>
#include <Logging/Logger.h>
#include <Exd/ExdData.h>

using namespace Sapphire;

class OpeningUldah : public Sapphire::ScriptAPI::EventScript
{
private:
  static constexpr auto ERANGE_HOWTO_ANN_AND_QUEST = 4101650;
  static constexpr auto ERANGE_HOWTO_QUEST_REWARD = 4102883;
  static constexpr auto ERANGE_SEQ_1_CLOSED_1 = 4101587;
  static constexpr auto POS_SEQ_1_CLOSED_RETURN_1 = 4101691;
  static constexpr auto ERANGE_ALWAYS_CLOSED_1 = 4101537;
  static constexpr auto POS_ALWAYS_CLOSED_RETURN_1 = 4101685;
  static constexpr auto ENPC_ALWAYS_CLOSED_1 = 4101796;
  static constexpr auto ERANGE_ALWAYS_CLOSED_2 = 4101525;
  static constexpr auto POS_ALWAYS_CLOSED_RETURN_2 = 4101680;
  static constexpr auto ENPC_ALWAYS_CLOSED_2 = 4101789;
  static constexpr auto ERANGE_ALWAYS_CLOSED_3 = 4101535;
  static constexpr auto POS_ALWAYS_CLOSED_RETURN_3 = 4101681;
  static constexpr auto ENPC_ALWAYS_CLOSED_3 = 4101787;
  static constexpr auto BGM_MUSIC_ZONE_WIL_TWN = 1035;
  static constexpr auto NCUT_WIL_1 = 186;
  static constexpr auto NCUT_WIL_2 = 139;
  static constexpr auto NCUT_WIL_3 = 187;
  static constexpr auto ENPC_QUEST_OFFER = 3969639;
  static constexpr auto NCUT_LIGHT_ALL = 2;
  static constexpr auto NCUT_LIGHT_WIL_1 = 147;
  static constexpr auto NCUT_LIGHT_WIL_2 = 145;
  static constexpr auto QUEST_COMING_TO_ULDAH = 66130;

  void Scene00000( Entity::Player& player )
  {
    auto callback = [ this ]( Entity::Player& player, const Event::SceneResult& result )
    {
      auto questionAnswer = result.getResult( 0 );

      uint16_t itemId = 0;

      switch( questionAnswer )
      {
        case 1:
          itemId = 4423;
          break;
        case 2:
          itemId = 4424;
          break;
        case 3:
          itemId = 4425;
          break;
        case 4:
          itemId = 4426;
          break;
        default:
          itemId = 4426;
          break;
      }

      auto item = player.addItem( itemId, 1, false, true );

      if( item )
        player.equipItem( Common::GearSetSlot::Ring2, *item, true );

      player.setOpeningSequence( 1 );
      Scene00001( player );
    };

    eventMgr().playScene( player, getId(), 0, NO_DEFAULT_CAMERA | INVIS_ENPC |
                                  CONDITION_CUTSCENE | HIDE_UI |
                                  HIDE_HOTBAR | SILENT_ENTER_TERRI_ENV | SILENT_ENTER_TERRI_BGM | SILENT_ENTER_TERRI_SE |
                                  DISABLE_SKIP | DISABLE_STEALTH, { 1 }, callback );
  }

  void Scene00001( Entity::Player& player )
  {
    eventMgr().playScene( player, getId(), 1, HIDE_HOTBAR | NO_DEFAULT_CAMERA, { 1, 0x32 } );
  }

  // Wymond turns the player around at a closed exit; once the line is acknowledged
  // they are put back at the matching return position, as the opening's return
  // spots in the layout intend. Without the warp the client re-enters the range
  // on every step and the line repeats.
  void Scene00020( Entity::Player& player, uint32_t returnPos )
  {
    auto callback = [ this, returnPos ]( Entity::Player& player, const Event::SceneResult& result )
    {
      warpBack( player, returnPos );
    };

    eventMgr().playScene( player, getId(), 20, HIDE_HOTBAR | NO_DEFAULT_CAMERA, { 1 }, callback );
  }

  void warpBack( Entity::Player& player, uint32_t returnPos )
  {
    // The return spots are Level rows of the opening territory, not pop ranges in the layout.
    auto& exdData = Common::Service< Data::ExdData >::ref();
    auto level = exdData.getRow< Excel::Level >( returnPos );
    if( !level || level->data().TerritoryType != player.getTerritoryTypeId() )
    {
      Logger::error( "OpeningUldah: return position {} is not a Level row of territory {}", returnPos,
                     player.getTerritoryTypeId() );
      return;
    }
    const auto& data = level->data();
    warpMgr().requestWarp( player, Common::WarpType::WARP_TYPE_NORMAL, { data.TransX, data.TransY, data.TransZ },
                           data.RotY );
  }

  // The exits stay closed until Momodi has finished Coming to Ul'dah.
  bool exitsClosed( Entity::Player& player )
  {
    return player.getOpeningSequence() != 0 && !player.isQuestCompleted( QUEST_COMING_TO_ULDAH );
  }

  void Scene00030( Entity::Player& player )
  {
    eventMgr().playScene( player, getId(), 30, HIDE_HOTBAR | NO_DEFAULT_CAMERA );
  }

  void Scene00040( Entity::Player& player )
  {
    auto callback = [ this ]( Entity::Player& player, const Event::SceneResult& result )
    {
      if( player.getOpeningSequence() == 2 )
        Scene00030( player );
    };

    eventMgr().playScene( player, getId(), 40, NO_DEFAULT_CAMERA, { 2, 1 }, callback );
  }


public:
  OpeningUldah() :
    Sapphire::ScriptAPI::EventScript( 1245187 )
  {
  }

  void onEnterTerritory( Entity::Player& player, uint32_t eventId, uint16_t param1, uint16_t param2 ) override
  {
    if( player.getOpeningSequence() == 0 )
      Scene00000( player );
    else
      Scene00040( player );
  }

  void onOutsideRange( Entity::Player& player, uint32_t eventId, uint32_t param1, float x, float y, float z ) override
  {
    // Leaving the arrival area is only blocked while Wymond still has to be spoken to (sequence 1).
    // The client keeps reporting this range afterwards, which used to replay the line on
    // the way up to Momodi.
    if( param1 == ERANGE_SEQ_1_CLOSED_1 && player.getOpeningSequence() == 1 )
      Scene00020( player, POS_SEQ_1_CLOSED_RETURN_1 );
  }

  void onWithinRange( Entity::Player& player, uint32_t eventId, uint32_t param1, float x, float y, float z ) override
  {
    if( !exitsClosed( player ) )
      return;

    if( param1 == ERANGE_ALWAYS_CLOSED_1 )
      Scene00020( player, POS_ALWAYS_CLOSED_RETURN_1 );
    else if( param1 == ERANGE_ALWAYS_CLOSED_2 )
      Scene00020( player, POS_ALWAYS_CLOSED_RETURN_2 );
    else if( param1 == ERANGE_ALWAYS_CLOSED_3 )
      Scene00020( player, POS_ALWAYS_CLOSED_RETURN_3 );
  }
};

EXPOSE_SCRIPT( OpeningUldah );