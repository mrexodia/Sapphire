#pragma once
// Test double for the connector's BORROWED-stream contract (setBlob(..., false)).
// Does not emulate SQL execution or replace live persistence verification.
#include <cstdint>
#include <istream>
#include <map>
#include <stdexcept>
#include <string>

namespace Mysql
{
  class PreparedStatement
  {
  public:
    std::map< uint32_t, std::istream* > blobs;
    uint32_t throwOn = 0;
    void setBlob( uint32_t index, std::istream* stream )
    {
      if( index == throwOn ) throw std::runtime_error( "synthetic bind failure" );
      blobs[ index ] = stream; // Neither deletes nor assumes ownership.
    }
    void setBoolean( uint32_t i, bool ) { blobs.erase( i ); }
    void setUInt( uint32_t i, uint32_t ) { blobs.erase( i ); }
    void setInt( uint32_t i, int32_t ) { blobs.erase( i ); }
    void setUInt64( uint32_t i, uint64_t ) { blobs.erase( i ); }
    void setInt64( uint32_t i, int64_t ) { blobs.erase( i ); }
    void setDouble( uint32_t i, double ) { blobs.erase( i ); }
    void setString( uint32_t i, const std::string& ) { blobs.erase( i ); }
    void setNull( uint32_t i, int ) { blobs.erase( i ); }
  };
}
