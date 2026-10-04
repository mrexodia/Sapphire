#include "Server.h"
#include <asio.hpp>
#include <chrono>
#include <sstream>
#include <thread>

namespace Sapphire::E2E
{
  Server::Server( std::string host, uint16_t port, std::string secret ) :
    m_host( std::move( host ) ), m_port( port ), m_secret( std::move( secret ) )
  {
  }

  // A plain synchronous HTTP/1.1 POST; the API answers small JSON bodies and
  // closes the connection, which is all the fixture routes need.
  static int httpPost( const std::string& host, uint16_t port, const std::string& path, const std::string& body,
                       std::string& responseBody )
  {
    asio::io_service io;
    asio::ip::tcp::socket socket( io );
    asio::ip::tcp::resolver resolver( io );
    asio::error_code ec;
    asio::ip::tcp::resolver::query query( host, std::to_string( port ) );
    auto endpoints = resolver.resolve( query, ec );
    if( ec )
      throw ApiError( "cannot resolve " + host + ": " + ec.message() );
    asio::connect( socket, endpoints, ec );
    if( ec )
      throw ApiError( "cannot connect to " + host + ":" + std::to_string( port ) + ": " + ec.message() );
    std::ostringstream request;
    request << "POST " << path << " HTTP/1.1\r\n"
            << "Host: " << host << ":" << port << "\r\n"
            << "Content-Type: application/json\r\n"
            << "Content-Length: " << body.size() << "\r\n"
            << "Connection: close\r\n\r\n"
            << body;
    const auto text = request.str();
    asio::write( socket, asio::buffer( text ), ec );
    if( ec )
      throw ApiError( "cannot send request to " + host + ": " + ec.message() );

    std::string response;
    std::array< char, 4096 > chunk{};
    while( true )
    {
      const auto received = socket.read_some( asio::buffer( chunk ), ec );
      if( received )
        response.append( chunk.data(), received );
      if( ec == asio::error::eof || ec == asio::error::connection_reset )
        break;
      if( ec )
        throw ApiError( "cannot read reply from " + host + ": " + ec.message() );
      if( response.size() > 4 * 1024 * 1024 )
        throw ApiError( "reply from " + host + " exceeds 4 MiB" );
    }
    const auto headerEnd = response.find( "\r\n\r\n" );
    if( response.rfind( "HTTP/1.", 0 ) != 0 || headerEnd == std::string::npos )
      throw ApiError( "malformed HTTP reply from " + host );
    int status = 0;
    try { status = std::stoi( response.substr( 9, 3 ) ); }
    catch( const std::exception& ) { throw ApiError( "malformed HTTP status from " + host ); }
    responseBody = response.substr( headerEnd + 4 );
    return status;
  }

  Json Server::post( const std::string& path, const Json& body, int expected )
  {
    std::string text;
    int status = 0;
    try
    {
      status = httpPost( m_host, m_port, path, body.dump(), text );
    }
    catch( const ApiError& error )
    {
      throw ApiError( std::string( error.what() ) + "; is the development stack running?" );
    }
    if( status != expected )
    {
      std::string detail = text.substr( 0, 300 );
      if( status == 404 && path.rfind( "/sapphire-api/dev/", 0 ) == 0 )
        detail += " (the API build predates the bot fixture routes)";
      throw ApiError( path + ": expected HTTP " + std::to_string( expected ) + ", received " +
                      std::to_string( status ) + ": " + detail );
    }
    return text.empty() ? Json::object() : Json::parse( text );
  }

  int Server::tryLogin( const std::string& username, const std::string& password, Json& reply )
  {
    std::string text;
    const int status = httpPost( m_host, m_port, "/sapphire-api/lobby/login",
                                 Json{ { "username", username }, { "pass", password } }.dump(), text );
    reply = text.empty() ? Json::object() : Json::parse( text, nullptr, false );
    return status;
  }

  static Json devBody( const std::string& secret, Json body )
  {
    body[ "secret" ] = secret;
    return body;
  }

  void Server::checkAlive()
  {
    post( "/sapphire-api/dev/listBots", devBody( m_secret, Json::object() ) );
  }

  Auth Server::login( const std::string& username, const std::string& password )
  {
    const auto reply = post( "/sapphire-api/lobby/login", { { "username", username }, { "pass", password } } );
    Auth auth;
    auth.sessionId = reply.at( "sId" ).get< std::string >();
    auth.lobbyHost = reply.at( "lobbyHost" ).get< std::string >();
    auth.lobbyPort = reply.at( "lobbyPort" ).get< uint16_t >();
    return auth;
  }

  Fixture Server::freshCharacter( const CharacterOptions& options )
  {
    Json request{ { "class", options.classJob }, { "territory", options.territory }, { "level", options.level } };
    if( options.position )
      request[ "position" ] = *options.position;
    const auto reply = post( "/sapphire-api/dev/createBot", devBody( m_secret, request ) );
    Fixture fixture;
    fixture.name = reply.at( "name" ).get< std::string >();
    fixture.username = reply.at( "username" ).get< std::string >();
    fixture.password = reply.at( "password" ).get< std::string >();
    fixture.characterId = reply.at( "character_id" ).get< uint64_t >();
    fixture.entityId = reply.at( "entity_id" ).get< uint32_t >();
    // A genuine HTTP login, even though creation also returned a session.
    fixture.auth = login( fixture.username, fixture.password );
    return fixture;
  }

  Account Server::freshAccount()
  {
    const auto reply = post( "/sapphire-api/dev/createBot", devBody( m_secret, { { "character", false } } ) );
    Account account;
    account.username = reply.at( "username" ).get< std::string >();
    account.password = reply.at( "password" ).get< std::string >();
    // A deterministic alphabetic name derived from the account: "bot_<hex>" -> "Bot ABCDEFGHIJ".
    account.name = "Bot ";
    for( size_t i = 4; i < 14 && i < account.username.size(); ++i )
    {
      const char c = account.username[ i ];
      const int value = c >= 'a' ? c - 'a' + 10 : c - '0';
      account.name += static_cast< char >( 'A' + value );
    }
    account.auth = login( account.username, account.password );
    return account;
  }

  void Server::waitOffline( const std::string& characterName, double timeoutSeconds )
  {
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::duration< double >( timeoutSeconds );
    while( true )
    {
      bool online = false;
      for( const auto& account : listBots() )
        for( const auto& character : account.characters )
          if( character.name == characterName && character.online )
            online = true;
      if( !online )
        return;
      if( std::chrono::steady_clock::now() > deadline )
        throw ApiError( characterName + " is still online after " + std::to_string( timeoutSeconds ) + "s" );
      std::this_thread::sleep_for( std::chrono::milliseconds( 250 ) );
    }
  }

  Auth Server::relogin( const Fixture& fixture, double timeoutSeconds )
  {
    waitOffline( fixture.name, timeoutSeconds );
    return login( fixture );
  }

  Auth Server::relogin( const Account& account, double timeoutSeconds )
  {
    waitOffline( account.name, timeoutSeconds );
    return login( account );
  }

  std::vector< BotAccount > Server::listBots()
  {
    const auto reply = post( "/sapphire-api/dev/listBots", devBody( m_secret, Json::object() ) );
    std::vector< BotAccount > accounts;
    for( const auto& row : reply.at( "accounts" ) )
    {
      BotAccount account;
      account.username = row.at( "username" ).get< std::string >();
      for( const auto& character : row.at( "characters" ) )
        account.characters.push_back( { character.at( "name" ).get< std::string >(),
                                        character.at( "online" ).get< bool >() } );
      accounts.push_back( std::move( account ) );
    }
    return accounts;
  }

  Json Server::purgeBots()
  {
    return post( "/sapphire-api/dev/purgeBots", devBody( m_secret, Json::object() ) );
  }
}
