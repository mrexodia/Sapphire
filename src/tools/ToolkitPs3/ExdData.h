#pragma once

#include <unordered_map>
#include <string>
#include <memory>
#include <vector>
#include <stdint.h>

#include <typeindex>

#if !_WIN32
# include <cxxabi.h>
#endif

#include <datReaderPs3/GameData.h>
#include <datReaderPs3/File.h>
#include <datReaderPs3/ExdData.h>
#include <datReaderPs3/ExdCat.h>
#include <datReaderPs3/Exd.h>

#include <Logging/Logger.h>

namespace Data
{

  class ExdData
  {
  public:
    bool init( const std::string& path );

    const std::vector< std::string >& getSheetNames() const { return m_exd_data->get_cat_names(); }
    const xivps3::exd::Cat& getCategory( const std::string& name ) { return m_exd_data->get_category( name ); }

    // subrow is an ordinal; use Exd::get_subrow_keys() for the stored key IDs.
    template< typename T >
    std::shared_ptr< Excel::Ps3::ExcelStruct< T > > getRow( uint32_t row, uint32_t subrow = 0 )
    {
      try
      {
        const auto& sheet = getCategory( getSheetName< T >() ).get_data( xivps3::exd::Language::en );
        return sheet.template get_row< T >( row, subrow );
      }
      catch( const std::out_of_range& ) { return nullptr; }
      catch( const std::runtime_error& ex )
      {
        Sapphire::Logger::error( "PS3 sheet {} row {}: {}", getSheetName< T >(), row, ex.what() );
        return nullptr;
      }
    }

    template< typename T >
    std::vector< uint32_t > getIdList()
    {
      return getCategory( getSheetName< T >() ).get_data( xivps3::exd::Language::en ).get_ids();
    }

    std::shared_ptr< xivps3::dat::GameData > getGameData()
    {
      return m_data;
    }

  private:
    template< typename T >
    std::string getSheetName()
    {
      auto origName = std::string( typeid( T ).name() );
#if _WIN32
      auto pos = origName.find_last_of(':');
      if (pos != std::string::npos)
      {
          return origName.substr(pos + 1);
      }

      throw std::runtime_error( "Cannot determine PS3 sheet name: " + origName );
#else

      int status = -4;

      auto res = abi::__cxa_demangle( origName.c_str(), NULL, NULL, &status );

      auto name = ( status == 0 ) ? res : origName;

      std::string demangledName( name );

      auto pos = demangledName.find_last_of( ':' );
      if( pos != std::string::npos )
      {
        demangledName = demangledName.substr( pos + 1 );
      }

      free( res );

      return demangledName;
#endif
    }

    std::shared_ptr< xivps3::dat::GameData > m_data;
    std::shared_ptr< xivps3::exd::ExdData > m_exd_data;
  };

}

