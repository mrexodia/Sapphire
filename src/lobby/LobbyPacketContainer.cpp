#include "LobbyPacketContainer.h"
#include <Network/CommonNetwork.h>
#include <Network/GamePacket.h>
#include <Crypt/blowfish.h>
#include <Common.h>

using namespace Sapphire;
using namespace Sapphire::Common;
using namespace Sapphire::Network::Packets;

LobbyPacketContainer::LobbyPacketContainer( uint8_t* encKey )
{
  memset( &m_header, 0, sizeof( Sapphire::Network::Packets::FFXIVARR_PACKET_HEADER ) );
  m_header.size = sizeof( Sapphire::Network::Packets::FFXIVARR_PACKET_HEADER );

  m_encKey = encKey;

  memset( m_dataBuf.data(), 0, 0x1570 );
}

LobbyPacketContainer::~LobbyPacketContainer()
{
  m_entryList.clear();
}

void LobbyPacketContainer::addPacket( FFXIVPacketBasePtr pEntry )
{
  const auto entrySize = static_cast< uint32_t >( pEntry->getSize() );
  const auto paddedSize = ( entrySize + 7u ) & ~7u;
  if( m_header.size + paddedSize > m_dataBuf.size() )
    throw std::runtime_error( "Lobby packet container capacity exceeded" );
  memcpy( m_dataBuf.data() + m_header.size, &pEntry->getData()[ 0 ], entrySize );
  // Blowfish emits complete eight-byte blocks. Publish that padding in both the
  // segment and outer lengths; otherwise a non-aligned NACK truncates ciphertext.
  FFXIVARR_PACKET_SEGMENT_HEADER segment{};
  memcpy( &segment, m_dataBuf.data() + m_header.size, sizeof( segment ) );
  segment.size = paddedSize;
  memcpy( m_dataBuf.data() + m_header.size, &segment, sizeof( segment ) );

  // encryption key is set, we want to encrypt this packet
  if( m_encKey != nullptr )
  {
    BlowFish blowfish;
    blowfish.initialize( m_encKey, 0x10 );
    blowfish.Encode( m_dataBuf.data() + m_header.size + 0x10, m_dataBuf.data() + m_header.size + 0x10,
                     paddedSize - 0x10 );
  }

  m_header.size += paddedSize;
  m_header.count++;
}

uint16_t LobbyPacketContainer::getSize() const
{
  return m_header.size;
}

uint8_t* LobbyPacketContainer::getRawData( bool addstuff )
{
  if( addstuff )
  {
    m_header.unknown_0 = 0xff41a05252;
    m_header.timestamp = Common::Util::getTimeMs();
  }

  memcpy( m_dataBuf.data(), &m_header, sizeof( Sapphire::Network::Packets::FFXIVARR_PACKET_HEADER ) );

  return m_dataBuf.data();
}
