#pragma once

// Pure validation for the opt-in administrative fixture lane. No game mutations.
#include <array>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <nlohmann/json.hpp>

namespace Sapphire::World::Development
{
  struct BotBinding
  {
    uint32_t entityId;
    uint64_t characterId;
    std::string name;
  };

  struct PlacementRegistry
  {
    std::string approvalId;
    std::array< BotBinding, 2 > bots;
    std::array< float, 3 > position;
    std::string catalogHash;
  };

  inline bool lowerHex( const std::string& value, size_t size )
  {
    return value.size() == size && value.find_first_not_of( "0123456789abcdef" ) == std::string::npos;
  }

  inline uint64_t positiveId( const nlohmann::json& value, uint64_t maximum )
  {
    if( !value.is_number_integer() || ( value.is_number_integer() && !value.is_number_unsigned() && value.get< int64_t >() < 0 ) )
      throw std::runtime_error( "invalid development identity" );
    const auto id = value.get< uint64_t >();
    if( !id || id > maximum ) throw std::runtime_error( "invalid development identity" );
    return id;
  }

  inline PlacementRegistry parsePlacementRegistry( const nlohmann::json& value )
  {
    if( !value.is_object() || value.size() != 7 || !value.at( "version" ).is_number_integer() ||
        value.at( "version" ) != 1 || value.at( "purpose" ) != "development-bot-placement" ||
        !value.at( "territory" ).is_number_integer() || value.at( "territory" ) != 130 )
      throw std::runtime_error( "unsupported development placement registry" );
    PlacementRegistry result;
    result.approvalId = value.at( "approval_id" ).get< std::string >();
    result.catalogHash = value.at( "catalog_sha256" ).get< std::string >();
    if( !lowerHex( result.approvalId, 32 ) || !lowerHex( result.catalogHash, 64 ) )
      throw std::runtime_error( "invalid development approval identity" );
    const auto& position = value.at( "position" );
    if( !position.is_array() || position.size() != 3 ) throw std::runtime_error( "invalid development destination" );
    for( size_t i = 0; i < 3; ++i )
    {
      if( !position[i].is_number() ) throw std::runtime_error( "invalid development destination" );
      const auto coordinate = position[i].get< double >();
      if( !std::isfinite( coordinate ) || std::abs( coordinate ) >= 1000 )
        throw std::runtime_error( "invalid development destination" );
      result.position[i] = static_cast< float >( coordinate );
    }
    const auto& bots = value.at( "bots" );
    if( !bots.is_array() || bots.size() != 2 ) throw std::runtime_error( "exactly two bot bindings required" );
    for( size_t i = 0; i < 2; ++i )
    {
      const auto& row = bots[i];
      if( !row.is_object() || row.size() != 3 ) throw std::runtime_error( "invalid bot binding fields" );
      auto& bot = result.bots[i];
      bot.entityId = static_cast< uint32_t >( positiveId( row.at( "entity_id" ), UINT32_MAX ) );
      bot.characterId = positiveId( row.at( "character_id" ), UINT64_MAX );
      bot.name = row.at( "name" ).get< std::string >();
      if( bot.name.size() != 19 || bot.name.substr( 0, 7 ) != "Tester " ||
          bot.name.substr( 7 ).find_first_not_of( "ABCDEFGHIJKLMNOPQRSTUVWXYZ" ) != std::string::npos )
        throw std::runtime_error( "only generated dedicated bot names may be registered" );
    }
    if( result.bots[0].entityId == result.bots[1].entityId ||
        result.bots[0].characterId == result.bots[1].characterId || result.bots[0].name == result.bots[1].name )
      throw std::runtime_error( "duplicate bot binding" );
    return result;
  }

  struct PlacementState
  {
    uint32_t entityId;
    uint64_t characterId;
    std::string name;
    bool sessionValid;
    bool loadingComplete;
    bool busy;
    bool alive;
    uint8_t gmRank;
    uint64_t partyId;
    uint32_t territory;
  };

  inline bool mayPlace( const BotBinding& binding, const PlacementState& state,
                        bool enabled, uint8_t operatorRank, uint64_t operatorCharacterId,
                        bool alreadyUsed )
  {
    return enabled && operatorRank > 0 && operatorCharacterId != state.characterId && !alreadyUsed &&
      state.entityId == binding.entityId && state.characterId == binding.characterId && state.name == binding.name &&
      state.sessionValid && state.loadingComplete && !state.busy && state.alive && !state.gmRank && !state.partyId &&
      ( state.territory == 182 || state.territory == 130 );
  }
}
