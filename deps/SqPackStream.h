#pragma once

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <istream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <streambuf>
#include <string>
#include <vector>

namespace xiv::io
{
  // Input stream for a normal SqPack file or the plaintext SDAT profile used by
  // the PS3 retail data in this repository. Callers request the ordinary .datN
  // path; matching the game, the stream prefers .datN.sdat when it exists.
  class SqPackStream : public std::istream
  {
  public:
    explicit SqPackStream( const std::filesystem::path& requestedPath ) : std::istream( nullptr )
    {
      open( requestedPath );
    }

    SqPackStream( const SqPackStream& ) = delete;
    SqPackStream& operator=( const SqPackStream& ) = delete;

    const std::filesystem::path& sourcePath() const
    {
      return m_sourcePath;
    }

    bool isSdat() const
    {
      return m_isSdat;
    }

  private:
    class MemoryBuffer : public std::streambuf
    {
    public:
      explicit MemoryBuffer( std::vector< char >& data )
      {
        auto* begin = data.data();
        setg( begin, begin, begin + data.size() );
      }

    protected:
      pos_type seekoff( off_type offset, std::ios_base::seekdir direction,
                        std::ios_base::openmode mode ) override
      {
        if( !( mode & std::ios_base::in ) )
          return pos_type( off_type( -1 ) );

        off_type origin = 0;
        if( direction == std::ios_base::cur )
          origin = gptr() - eback();
        else if( direction == std::ios_base::end )
          origin = egptr() - eback();
        else if( direction != std::ios_base::beg )
          return pos_type( off_type( -1 ) );

        const off_type size = egptr() - eback();
        if( offset < -origin || offset > size - origin )
          return pos_type( off_type( -1 ) );

        const off_type position = origin + offset;
        setg( eback(), eback() + position, egptr() );
        return pos_type( position );
      }

      pos_type seekpos( pos_type position, std::ios_base::openmode mode ) override
      {
        if( position < pos_type( 0 ) )
          return pos_type( off_type( -1 ) );
        return seekoff( off_type( position ), std::ios_base::beg, mode );
      }
    };

    static uint32_t readBe32( const unsigned char* data )
    {
      return ( uint32_t{ data[ 0 ] } << 24 ) | ( uint32_t{ data[ 1 ] } << 16 ) |
             ( uint32_t{ data[ 2 ] } << 8 ) | uint32_t{ data[ 3 ] };
    }

    static uint64_t readBe64( const unsigned char* data )
    {
      return ( uint64_t{ readBe32( data ) } << 32 ) | readBe32( data + 4 );
    }

    static bool isRegularFile( const std::filesystem::path& path )
    {
      std::error_code error;
      return std::filesystem::is_regular_file( path, error );
    }

    void open( const std::filesystem::path& requestedPath )
    {
      const bool requestedSdat = requestedPath.extension() == ".sdat";
      const auto sdatPath = requestedSdat ? requestedPath
                                          : std::filesystem::path( requestedPath.string() + ".sdat" );
      if( isRegularFile( sdatPath ) )
        m_sourcePath = sdatPath;
      else if( isRegularFile( requestedPath ) )
        m_sourcePath = requestedPath;
      else
        throw std::runtime_error( "SqPack file not found: " + requestedPath.string() +
                                  " (also tried " + sdatPath.string() + ")" );

      std::ifstream probe( m_sourcePath, std::ios_base::in | std::ios_base::binary );
      if( !probe )
        throw std::runtime_error( "Failed to open SqPack file: " + m_sourcePath.string() );

      unsigned char magic[ 4 ]{};
      probe.read( reinterpret_cast< char* >( magic ), sizeof( magic ) );
      if( probe.gcount() == static_cast< std::streamsize >( sizeof( magic ) ) &&
          std::memcmp( magic, "NPD\0", sizeof( magic ) ) == 0 )
      {
        loadPlainSdat( probe );
        m_memoryBuffer = std::make_unique< MemoryBuffer >( m_sdatData );
        rdbuf( m_memoryBuffer.get() );
        m_isSdat = true;
      }
      else
      {
        probe.close();
        if( !m_fileBuffer.open( m_sourcePath, std::ios_base::in | std::ios_base::binary ) )
          throw std::runtime_error( "Failed to open SqPack file: " + m_sourcePath.string() );
        rdbuf( &m_fileBuffer );
      }
      clear();
    }

    void loadPlainSdat( std::ifstream& input )
    {
      constexpr uint32_t supportedVersion = 4;
      constexpr uint32_t supportedFlags = 0x8100003C;
      constexpr uint32_t supportedBlockSize = 0x4000;
      constexpr uint64_t firstDataOffset = 0x120;
      constexpr uint64_t metadataSize = 0x20;

      unsigned char header[ 0x90 ]{};
      input.clear();
      input.seekg( 0 );
      input.read( reinterpret_cast< char* >( header ), sizeof( header ) );
      if( input.gcount() != static_cast< std::streamsize >( sizeof( header ) ) )
        throw std::runtime_error( "Truncated SDAT header: " + m_sourcePath.string() );

      const uint32_t version = readBe32( header + 0x04 );
      const uint32_t flags = readBe32( header + 0x80 );
      const uint32_t blockSize = readBe32( header + 0x84 );
      const uint64_t logicalSize = readBe64( header + 0x88 );
      if( version != supportedVersion || flags != supportedFlags || blockSize != supportedBlockSize )
        throw std::runtime_error( "Unsupported SDAT profile in " + m_sourcePath.string() );
      if( logicalSize > std::numeric_limits< size_t >::max() ||
          logicalSize > static_cast< uint64_t >( std::numeric_limits< std::streamsize >::max() ) )
        throw std::runtime_error( "SDAT logical stream is too large: " + m_sourcePath.string() );

      input.clear();
      input.seekg( 0, std::ios_base::end );
      const auto endPosition = input.tellg();
      if( endPosition < 0 )
        throw std::runtime_error( "Failed to determine SDAT size: " + m_sourcePath.string() );
      const uint64_t physicalSize = static_cast< uint64_t >( endPosition );
      if( logicalSize > physicalSize )
        throw std::runtime_error( "Invalid SDAT logical size: " + m_sourcePath.string() );

      m_sdatData.resize( static_cast< size_t >( logicalSize ) );
      uint64_t logicalOffset = 0;
      uint64_t blockIndex = 0;
      while( logicalOffset < logicalSize )
      {
        const uint64_t length = std::min< uint64_t >( blockSize, logicalSize - logicalOffset );
        if( blockIndex > ( std::numeric_limits< uint64_t >::max() - firstDataOffset ) /
                                 ( uint64_t{ blockSize } + metadataSize ) )
          throw std::runtime_error( "SDAT block offset overflow: " + m_sourcePath.string() );
        const uint64_t physicalOffset = firstDataOffset + blockIndex * ( uint64_t{ blockSize } + metadataSize );
        if( physicalOffset > physicalSize || length > physicalSize - physicalOffset )
          throw std::runtime_error( "Truncated SDAT data block: " + m_sourcePath.string() );

        input.clear();
        input.seekg( static_cast< std::streamoff >( physicalOffset ) );
        input.read( m_sdatData.data() + static_cast< size_t >( logicalOffset ),
                    static_cast< std::streamsize >( length ) );
        if( input.gcount() != static_cast< std::streamsize >( length ) )
          throw std::runtime_error( "Failed to read SDAT data block: " + m_sourcePath.string() );

        logicalOffset += length;
        ++blockIndex;
      }

      if( m_sdatData.size() < 8 || std::memcmp( m_sdatData.data(), "SqPack\0\0", 8 ) != 0 )
        throw std::runtime_error( "SDAT payload is not a SqPack stream: " + m_sourcePath.string() );
    }

    std::filesystem::path m_sourcePath;
    std::filebuf m_fileBuffer;
    std::vector< char > m_sdatData;
    std::unique_ptr< MemoryBuffer > m_memoryBuffer;
    bool m_isSdat = false;
  };
}// namespace xiv::io
