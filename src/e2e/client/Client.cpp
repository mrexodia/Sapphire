#include "Client.h"
#include "CreationActions.h"
#include "InventoryActions.h"
#include "ShopActions.h"
#include "RespawnActions.h"
#include "TransitionActions.h"
#include "PartyActions.h"
#include "ChatActions.h"
#include <Network/CommonActorControl.h>
#include <Network/PacketDef/Lobby/ClientLobbyDef.h>
#include <Network/PacketDef/Lobby/ServerLobbyDef.h>
#include <Network/PacketDef/Chat/ServerChatDef.h>
#include <Network/PacketDef/Zone/ClientZoneDef.h>
#include <Network/PacketDef/Zone/ServerZoneDef.h>
#include <cmath>
#include <random>

namespace Sapphire::Testing
{
  namespace LC = Wire::LobbyPackets::Client;
  namespace LS = Wire::LobbyPackets::Server;

  static std::string receivedName(const void* bytes, size_t size)
  {
    const auto* begin = static_cast<const uint8_t*>(bytes);
    const auto* end = std::find(begin, begin + size, uint8_t{0});
    if(end == begin || end == begin + size ||
       !std::all_of(begin, end, [](uint8_t c) { return c >= 0x20 && c <= 0x7e; }))
      throw ProtocolError("malformed received character name");
    return {reinterpret_cast<const char*>(begin), reinterpret_cast<const char*>(end)};
  }
  namespace WC = Wire::WorldPackets::Client;
  namespace WS = Wire::WorldPackets::Server;

  bool isLocalNetwork(const asio::ip::address& address)
  {
    if(address.is_loopback()) return true;
    if(!address.is_v4()) return false;
    const auto bytes = address.to_v4().to_bytes();
    return bytes[0] == 10                                   // 10.0.0.0/8
        || (bytes[0] == 172 && (bytes[1] & 0xF0) == 16)     // 172.16.0.0/12
        || (bytes[0] == 192 && bytes[1] == 168)             // 192.168.0.0/16
        || (bytes[0] == 169 && bytes[1] == 254);            // 169.254.0.0/16
  }

  Channel::Channel(asio::io_service& io, Receive receive, std::function<void(const std::string&)> error) :
    m_socket(io), m_receive(std::move(receive)), m_error(std::move(error)) {}

  void Channel::connect(const std::string& host, uint16_t port, std::function<void()> ready)
  {
    // Development servers only: loopback or a private-network address, never a
    // public host.
    auto address = asio::ip::address::from_string(host);
    if(!isLocalNetwork(address) || !port)
      throw ProtocolError("test endpoints must be loopback or private-network addresses with a nonzero port");
    m_socket.async_connect({address, port}, [self = shared_from_this(), ready](auto ec) {
      if(self->m_closed) return;
      if(ec) return self->error("connection failed: " + ec.message());
      self->m_socket.set_option(asio::ip::tcp::no_delay(true));
      self->read();
      try { ready(); } catch(const std::exception& e) { self->error(e.what()); }
    });
  }
  void Channel::read()
  {
    m_socket.async_read_some(asio::buffer(m_input), [self = shared_from_this()](auto ec, size_t size) {
      if(self->m_closed) return;
      if(ec) return self->error("connection closed or read failed");
      try
      {
        auto segments = self->m_decoder.feed(self->m_input.data(), size);
        for(auto& segment : segments)
        {
          if(self->m_closed) break;
          self->m_receive(std::move(segment));
        }
      }
      catch(const std::exception& e) { return self->error(e.what()); }
      if(!self->m_closed) self->read();
    });
  }
  void Channel::send(Bytes bytes, std::function<void()> complete)
  {
    if(m_closed) throw ProtocolError("send on closed channel");
    if(m_queued + bytes.size() > 2 * Decoder::MaxFrame) throw ProtocolError("send queue limit exceeded");
    const bool idle = m_output.empty();
    m_queued += bytes.size();
    m_output.push_back({std::move(bytes), std::move(complete)});
    if(idle) write();
  }
  void Channel::write()
  {
    asio::async_write(m_socket, asio::buffer(m_output.front().bytes), [self = shared_from_this()](auto ec, size_t) {
      if(self->m_closed) return;
      if(ec) return self->error("write failed");
      self->m_queued -= self->m_output.front().bytes.size();
      auto complete = std::move(self->m_output.front().complete);
      self->m_output.pop_front();
      if(complete) complete();
      if(!self->m_output.empty()) self->write();
    });
  }
  void Channel::close()
  {
    m_closed = true;
    asio::error_code ignored;
    m_socket.close(ignored);
    // Keep the write buffer alive until the cancelled handler is delivered.
  }
  void Channel::error(const std::string& reason) { close(); m_error(reason); }

  Client::Client(asio::io_service& io, std::string id, Emit emit) :
    m_io(io), m_id(std::move(id)), m_emit(std::move(emit)),
    m_deadline(io), m_heartbeat(io), m_movement(io)
  {
    m_state = {{"phase", "disconnected"}, {"entity_id", 0}, {"territory", 0}, {"homepoint", nullptr},
      {"actors", Json::object()}, {"known_players", Json::object()},
      {"quests", Json::object()}, {"complete_quests", Json::object()},
      {"chat", Json::array()}, {"party_chat", Json::array()}, {"tells", Json::array()},
      {"tell_not_found", nullptr}, {"offline_tell_pending", false},
      {"created_via_lobby", false}, {"deleted_via_lobby", false},
      {"scene", nullptr}, {"event_id", nullptr}, {"name_rejection", nullptr}, {"pending_party_invite", nullptr},
      {"party_invite_result", nullptr}, {"party_invite_reply", nullptr}, {"party_invite_update", nullptr},
      {"party", {{"id", 0}, {"chat_channel", 0}, {"count", 0},
                                                            {"leader_index", 0}, {"members", Json::array()}}},
      {"discovery_reply", nullptr}, {"discovery_requests_sent", Json::array()},
      {"central_thanalan_discoveries", Json::array()}, {"central_thanalan_discovery", false},
      {"heartbeat_replies", 0}, {"last_warp", nullptr},
      {"heartbeats", {{"zone", 0}, {"chat", 0}}}, {"packets_received", 0}};
  }
  void Client::event(const std::string& name, Json data)
  {
    m_emit({{"type", "event"}, {"bot", m_id}, {"seq", ++m_seq}, {"event", name}, {"data", std::move(data)}});
  }
  void Client::phase(const std::string& value) { m_state["phase"] = value; event("phase", {{"phase", value}}); }
  void Client::close()
  {
    m_deadline.cancel(); m_heartbeat.cancel(); m_movement.cancel(); m_moving = false;
    if(m_lobby) m_lobby->close();
    if(m_zone) m_zone->close();
    if(m_chat) m_chat->close();
  }
  void Client::fail(const std::string& reason)
  {
    if(m_state["phase"] == "failed" || m_state["phase"] == "closed") return;
    close();
    // Only protocol/transport diagnoses are emitted; never include input payloads/session data.
    m_state["error"] = reason;
    phase("failed");
    event("failure", {{"reason", reason}});
    m_login = LoginOptions{}; m_loginActive = false;
  }
  std::shared_ptr<Channel> Client::channel(const std::string& name)
  {
    std::weak_ptr<Client> weak = shared_from_this();
    return std::make_shared<Channel>(m_io,
      [weak, name](Segment segment) { if(auto bot = weak.lock()) bot->receive(name, std::move(segment)); },
      [weak, name](const std::string& reason) {
        if(auto bot = weak.lock())
        {
          if(bot->m_state["phase"] == "logged_out")
          {
            bot->phase("logout_complete");
            bot->event("server_logout_complete", {{"channel", name}});
            return;
          }
          if(bot->m_state["phase"] == "logout_complete") return;
          bot->fail(name + ": " + reason);
        }
      });
  }
  void Client::login(const LoginOptions& options)
  {
    if(m_state["phase"] != "disconnected") throw ProtocolError("bot already started; create a fresh bot");
    if(options.session.empty() || options.session.size() >= 64) throw ProtocolError("invalid session length");
    if(options.character.empty() || options.character.size() >= 32) throw ProtocolError("invalid character name length");
    if(static_cast<int>(options.createCharacter) + static_cast<int>(options.deleteCharacter) +
       static_cast<int>(options.expectCharacterAbsent) + static_cast<int>(options.expectNameRejected) > 1)
      throw ProtocolError("character lobby modes are mutually exclusive");
    if((options.createCharacter || options.deleteCharacter || options.expectCharacterAbsent || options.expectNameRejected) &&
       !std::all_of(options.character.begin(), options.character.end(), [](unsigned char c) {
         return c == ' ' || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z');
       }))
      throw ProtocolError("character lobby operation name must contain only alphabetic ASCII and spaces");
    if(options.createCharacter)
      canonicalUldahCreationPayload(options.creationClass);
    if(options.timeoutSeconds < 1 || options.timeoutSeconds > 120) throw ProtocolError("login timeout outside 1..120 seconds");
    m_login = options;
    m_loginActive = true;
    m_deadline.expires_from_now(std::chrono::seconds(options.timeoutSeconds));
    m_deadline.async_wait([self = shared_from_this()](auto ec) { if(!ec) self->fail("login deadline exceeded"); });
    m_lobby = channel("lobby");
    phase("lobby_connecting");
    m_lobby->connect(options.host, options.port, [self = shared_from_this()] {
      auto handshake = self->m_cipher.initialize(std::random_device{}(), "SapphireE2E");
      self->phase("lobby_encryption");
      self->m_lobby->send(frame(0, 9, handshake));
    });
  }
  void Client::sendLobby(uint16_t opcode, const Bytes& payload)
  {
    auto bytes = ipc(opcode, payload);
    m_cipher.encrypt(bytes);
    // Sapphire's client-receive profile excludes a 16-byte trailer from decryption.
    bytes.resize(bytes.size() + 16, 0);
    m_lobby->send(frame(0, 3, bytes));
  }
  void Client::sendZone(uint16_t opcode, const Bytes& payload, std::function<void()> complete)
  {
    if(!m_zone) throw ProtocolError("zone channel not initialized");
    // Journal what goes out (except the chatty movement/ping traffic) so a server
    // log can be compared against exactly what the client sent.
    if(opcode != WC::FFXIVIpcUpdatePosition::_ServerIpcType && opcode != WC::FFXIVIpcPingHandler::_ServerIpcType)
      event("tx", {{"channel", "zone"}, {"opcode", opcode}, {"size", payload.size()}});
    m_zone->send(frame(1, 3, ipc(opcode, payload), m_entity), std::move(complete));
  }
  void Client::sendChat(uint16_t opcode, const Bytes& payload)
  {
    if(!m_chat) throw ProtocolError("chat channel not initialized");
    m_chat->send(frame(2, 3, ipc(opcode, payload), m_entity));
  }
  void Client::receive(const std::string& name, Segment segment)
  {
    m_state["packets_received"] = m_state["packets_received"].get<uint64_t>() + 1;
    if(name == "lobby") lobbyPacket(std::move(segment));
    else worldPacket(name, std::move(segment));
  }
  void Client::lobbyPacket(Segment segment)
  {
    if(segment.header.type == 10 && m_state["phase"] == "lobby_encryption")
    {
      m_cipher.decrypt(segment.data);
      if(readObject<uint32_t>(segment.data) != 0xE0003C2A) throw ProtocolError("unexpected lobby encryption reply");
      LC::FFXIVIpcLoginEx p{};
      p.requestNumber = 1; p.clientTimeValue = timeSeconds(); p.clientLangCode = 1;
      copyText(p.sessionId, m_login.session);
      copyText(p.version, "2016.07.05.0000.0001");
      phase("lobby_authenticating");
      sendLobby(p._ServerIpcType, objectBytes(p));
      return;
    }
    if(segment.header.type != 3) return;
    m_cipher.decrypt(segment.data);
    const auto h = readObject<Wire::FFXIVARR_IPC_HEADER>(segment.data);
    event("packet", {{"channel", "lobby"}, {"opcode", h.type}});
    if(h.type == Wire::LobbyPackets::ServerLobbyIpcType::NackReply)
    {
      const auto p = readObject<LS::FFXIVIpcNackReply>(segment.data, sizeof(h));
      event("lobby_nack", {{"request", p.requestNumber}, {"error_code", p.errorCode},
                            {"error_status", p.errorStatus}, {"message_number", p.errorMessageNo}});
      if(m_state["phase"] == "character_name_reservation" && m_login.expectNameRejected &&
         p.errorCode == 3074 && p.errorStatus == 0 && p.errorMessageNo == 13004)
      {
        m_state["name_rejection"] = {{"error_code", p.errorCode}, {"error_status", p.errorStatus},
                                     {"message_number", p.errorMessageNo}};
        m_deadline.cancel(); phase("name_rejected");
        event("name_rejected", m_state["name_rejection"]);
        return;
      }
      throw ProtocolError("lobby rejected request");
    }
    if(h.type == LS::FFXIVIpcLoginReply::_ServerIpcType && m_state["phase"] == "lobby_authenticating")
    {
      const auto p = readObject<LS::FFXIVIpcLoginReply>(segment.data, sizeof(h));
      if(p.activeAccountCount == 0) throw ProtocolError("no service account available");
      LC::FFXIVIpcServiceLogin request{};
      request.requestNumber = 2; request.clientTimeValue = timeSeconds();
      m_serviceAccountId = p.accountArray[0].accountId;
      m_serviceAccountIndex = p.accountArray[0].accountIndex;
      request.accountId = m_serviceAccountId; request.accountIndex = m_serviceAccountIndex;
      phase("character_list");
      m_state["characters"] = Json::array();
      sendLobby(request._ServerIpcType, objectBytes(request));
    }
    else if(h.type == LS::FFXIVIpcServiceLoginReply::_ServerIpcType &&
            (m_state["phase"] == "character_list" || m_state["phase"] == "character_list_after_creation" ||
             m_state["phase"] == "character_list_after_deletion"))
    {
      const bool afterCreation = m_state["phase"] == "character_list_after_creation";
      const bool afterDeletion = m_state["phase"] == "character_list_after_deletion";
      auto p = readObject<LS::FFXIVIpcServiceLoginReply>(segment.data, sizeof(h));
      if(p.count > 2) throw ProtocolError("invalid character list count");
      for(size_t i = 0; i < p.count; ++i)
      {
        const auto& c = p.chrArray[i];
        if(c.playerId && c.characterId)
          m_state["characters"].push_back({{"name", text(c.chrName)}, {"entity_id", c.playerId},
            {"character_id", c.characterId}, {"index", c.chrIndex}, {"world", c.worldId}});
      }
      if(!p.endOfList) return;
      const std::string wanted = m_login.character;
      const auto found = std::find_if(m_state["characters"].begin(), m_state["characters"].end(),
        [&](const auto& character) { return character.at("name") == wanted; });
      if(afterDeletion || m_login.expectCharacterAbsent)
      {
        if(found != m_state["characters"].end()) throw ProtocolError("deleted character remains in refreshed lobby list");
        m_deadline.cancel();
        m_state["deleted_via_lobby"] = afterDeletion;
        phase(afterDeletion ? "lobby_deleted" : "character_absent");
        return;
      }
      if(m_login.deleteCharacter)
      {
        if(found == m_state["characters"].end() || m_state["characters"].size() != 1)
          throw ProtocolError("character deletion requires exactly one matching lobby character");
        auto payload = characterDeleteRequest(3, timeSeconds(), *found, wanted);
        phase("character_deleting");
        sendLobby(LC::FFXIVIpcCharaMake::_ServerIpcType, payload);
        return;
      }
      if(found != m_state["characters"].end())
      {
        const auto& c = *found;
        if(afterCreation) m_state["created_via_lobby"] = true;
        LC::FFXIVIpcGameLogin request{};
        request.requestNumber = afterCreation ? 6 : 3; request.clientTimeValue = timeSeconds();
        request.playerId = c["entity_id"]; request.characterId = c["character_id"];
        request.characterIndex = c["index"]; request.worldId = c["world"];
        phase("world_handoff");
        sendLobby(request._ServerIpcType, objectBytes(request));
        return;
      }
      if(!afterCreation && (m_login.createCharacter ||
                            m_login.expectNameRejected) && m_state["characters"].empty())
      {
        LC::FFXIVIpcCharaMake request{};
        request.requestNumber = 3; request.clientTimeValue = timeSeconds();
        request.operation = LC::CharacterOperation::CHARAOPE_RESERVENAME;
        copyText(request.chracterName, wanted);
        phase("character_name_reservation");
        sendLobby(request._ServerIpcType, objectBytes(request));
        return;
      }
      throw ProtocolError(afterCreation ? "created character absent from refreshed lobby list" :
                                           "requested character not found in lobby list");
    }
    else if(h.type == LS::FFXIVIpcCharaMakeReply::_ServerIpcType &&
            m_state["phase"] == "character_deleting")
    {
      const auto p = readObject<LS::FFXIVIpcCharaMakeReply>(segment.data, sizeof(h));
      if(p.optionParam != LC::CharacterOperation::CHARAOPE_DELETECHARA || p.count != 1 ||
         text(p.chrArray[0].chrName) != m_login.character)
        throw ProtocolError("invalid character-deletion reply");
      LC::FFXIVIpcServiceLogin request{};
      request.requestNumber = 4; request.clientTimeValue = timeSeconds();
      request.accountId = m_serviceAccountId; request.accountIndex = m_serviceAccountIndex;
      m_state["characters"] = Json::array();
      phase("character_list_after_deletion");
      sendLobby(request._ServerIpcType, objectBytes(request));
    }
    else if(h.type == LS::FFXIVIpcCharaMakeReply::_ServerIpcType &&
            m_state["phase"] == "character_name_reservation")
    {
      const auto p = readObject<LS::FFXIVIpcCharaMakeReply>(segment.data, sizeof(h));
      const std::string wanted = m_login.character;
      if(p.optionParam != LC::CharacterOperation::CHARAOPE_RESERVENAME || p.count != 1 ||
         text(p.chrArray[0].chrName) != wanted || !p.chrArray[0].characterId)
        throw ProtocolError("invalid character-name reservation reply");
      if(m_login.expectNameRejected)
        throw ProtocolError("duplicate character name was unexpectedly reserved");
      m_creationCharacterId = p.chrArray[0].characterId;
      LC::FFXIVIpcCharaMake request{};
      request.requestNumber = 4; request.clientTimeValue = timeSeconds();
      request.characterId = m_creationCharacterId;
      request.operation = LC::CharacterOperation::CHARAOPE_MAKECHARA;
      request.worldId = p.chrArray[0].worldId;
      copyText(request.chracterName, wanted);
      const auto details = canonicalUldahCreationPayload(m_login.creationClass);
      copyText(request.charaMakeData, details);
      phase("character_creating");
      sendLobby(request._ServerIpcType, objectBytes(request));
    }
    else if(h.type == LS::FFXIVIpcCharaMakeReply::_ServerIpcType && m_state["phase"] == "character_creating")
    {
      const auto p = readObject<LS::FFXIVIpcCharaMakeReply>(segment.data, sizeof(h));
      if(p.optionParam != LC::CharacterOperation::CHARAOPE_MAKECHARA || p.count != 1 ||
         text(p.chrArray[0].chrName) != m_login.character)
        throw ProtocolError("invalid character-creation reply");
      LC::FFXIVIpcServiceLogin request{};
      request.requestNumber = 5; request.clientTimeValue = timeSeconds();
      request.accountId = m_serviceAccountId; request.accountIndex = m_serviceAccountIndex;
      m_state["characters"] = Json::array();
      phase("character_list_after_creation");
      sendLobby(request._ServerIpcType, objectBytes(request));
    }
    else if(h.type == LS::FFXIVIpcGameLoginReply::_ServerIpcType && m_state["phase"] == "world_handoff")
    {
      const auto p = readObject<LS::FFXIVIpcGameLoginReply>(segment.data, sizeof(h));
      m_entity = p.ticketId; m_worldHost = text(p.frontendHost); m_worldPort = p.frontendPort;
      m_state["entity_id"] = m_entity;
      m_lobby->close();
      m_login = LoginOptions{}; m_loginActive = false; // Drop the session secret as soon as handoff has completed.
      m_zone = channel("zone");
      phase("zone_connecting");
      m_zone->connect(m_worldHost, m_worldPort, [self = shared_from_this()] {
        Bytes init(72, 0);
        auto id = std::to_string(self->m_entity);
        std::memcpy(init.data() + 4, id.c_str(), id.size() + 1);
        self->m_zone->send(frame(1, 1, init, self->m_entity));
      });
    }
  }
  void Client::worldLogin()
  {
    phase("loading");
    WC::FFXIVIpcLoginHandler login{};
    login.clientTimeValue = timeSeconds();
    sendZone(login._ServerIpcType, objectBytes(login));
    heartbeat();
  }
  void Client::heartbeat()
  {
    m_heartbeat.expires_from_now(std::chrono::seconds(3));
    m_heartbeat.async_wait([self = shared_from_this()](auto ec) {
      if(ec) return;
      try
      {
        std::array<uint32_t, 2> ping{self->m_entity, timeSeconds()};
        self->m_zone->send(frame(1, 7, objectBytes(ping), self->m_entity));
        self->m_chat->send(frame(2, 7, objectBytes(ping), self->m_entity));
        WC::FFXIVIpcPingHandler sync{};
        sync.clientTimeValue = timeSeconds(); sync.position.originEntityId = self->m_entity;
        std::copy(self->m_predicted.begin(), self->m_predicted.end(), sync.position.pos);
        self->sendZone(sync._ServerIpcType, objectBytes(sync));
        self->heartbeat();
      }
      catch(const std::exception& e) { self->fail(e.what()); }
    });
  }
  void Client::updateQuests()
  {
    m_state["quests"] = Json::object();
    for(const auto& q : m_quests)
      if(!q.is_null() && q["id"] != 0) m_state["quests"][std::to_string(q["id"].get<uint32_t>())] = q;
  }
  void Client::worldPacket(const std::string& name, Segment segment)
  {
    if(segment.header.type == 8)
    {
      m_state["heartbeat_replies"] = m_state["heartbeat_replies"].get<uint64_t>() + 1;
      m_state["heartbeats"][name] = m_state["heartbeats"][name].get<uint64_t>() + 1;
      // Heartbeats are counted in snapshots; emitting every one would wake
      // state predicates without a semantic state transition.
      return;
    }
    if(segment.header.type == 2)
    {
      if(name == "zone" && !m_zoneAck)
      {
        m_zoneAck = true; m_chat = channel("chat"); phase("chat_connecting");
        m_chat->connect(m_worldHost, m_worldPort, [self = shared_from_this()] {
          Bytes init(72, 0); auto id = std::to_string(self->m_entity);
          std::memcpy(init.data() + 4, id.c_str(), id.size() + 1);
          self->m_chat->send(frame(2, 1, init, self->m_entity));
        });
      }
      else if(name == "chat" && !m_chatAck) { m_chatAck = true; worldLogin(); }
      return;
    }
    if(segment.header.type != 3) return;
    const auto h = readObject<Wire::FFXIVARR_IPC_HEADER>(segment.data);
    // Semantic handlers below emit bounded state events. A second generic
    // event for every IPC frame doubles control-pipe traffic and can delay
    // ordinary client commands during sustained combat.
    constexpr size_t off = sizeof(Wire::FFXIVARR_IPC_HEADER);
    if(name == "chat")
    {
      if(h.type == Wire::Server::FFXIVIpcTellNotFound::_ServerIpcType &&
         m_state["offline_tell_pending"].get<bool>())
      {
        const auto p = readObject<Wire::Server::FFXIVIpcTellNotFound>(segment.data, off);
        m_state["tell_not_found"] = {{"name", receivedName(p.toName, sizeof(p.toName))}};
        m_state["offline_tell_pending"] = false;
        event("tell_not_found", m_state["tell_not_found"]);
        return;
      }
      if(h.type == Wire::Server::FFXIVChatFrom::_ServerIpcType)
      {
        const auto p = readObject<Wire::Server::FFXIVChatFrom>(segment.data, off);
        const auto sender = receivedName(p.fromName, sizeof(p.fromName));
        const auto message = text(p.message);
        const auto& party = m_state["party"];
        std::vector<uint32_t> actorMatches;
        for(auto it = m_state["actors"].begin(); it != m_state["actors"].end(); ++it)
          if(it.value().value("kind", 0) == 1 && it.value().value("name", "") == sender)
            actorMatches.push_back(static_cast<uint32_t>(std::stoul(it.key())));
        std::vector<uint32_t> partyMatches;
        for(const auto& member : party.at("members"))
          if(member.value("character_id", uint64_t{0}) == p.fromCharacterID &&
             member.value("name", "") == sender && member.value("entity_id", 0u) != 0)
            partyMatches.push_back(member.at("entity_id"));
        std::vector<uint32_t> knownMatches;
        for(auto it = m_state["known_players"].begin(); it != m_state["known_players"].end(); ++it)
          if(it.value().value("name", "") == sender)
            knownMatches.push_back(static_cast<uint32_t>(std::stoul(it.key())));
        std::vector<uint32_t> identities;
        for(const auto& matches : {actorMatches, partyMatches, knownMatches})
          for(const auto actor : matches)
            if(std::find(identities.begin(), identities.end(), actor) == identities.end()) identities.push_back(actor);
        if(p.type != 0 || !p.fromCharacterID || message.empty() || message.size() > 128 ||
           !std::all_of(message.begin(), message.end(), [](unsigned char c) { return c >= 0x20 && c <= 0x7e; }) ||
           actorMatches.size() > 1 || partyMatches.size() > 1 || knownMatches.size() > 1 || identities.size() != 1)
          throw ProtocolError("tell sender does not match one bounded received player identity");
        const auto actor = identities[0];
        for(const auto& member : party.at("members"))
          if(member.value("entity_id", 0u) == actor && member.value("name", "") == sender &&
             member.value("character_id", uint64_t{0}) != p.fromCharacterID)
            throw ProtocolError("tell sender character ID disagrees with received party identity");
        const auto partyId = partyMatches.empty() ? uint64_t{0} : party.at("id").get<uint64_t>();
        Json received{{"party_id", partyId}, {"actor", actor},
                      {"character_id", p.fromCharacterID}, {"name", sender},
                      {"message", message}, {"token", m_seq + 1}};
        m_state["tells"].push_back(received);
        if(m_state["tells"].size() > 64) m_state["tells"].erase(m_state["tells"].begin());
        event("tell", received);
        return;
      }
      if(h.type != Wire::Server::FFXIVChatToChannel::_ServerIpcType) return;
      const auto p = readObject<Wire::Server::FFXIVChatToChannel>(segment.data, off);
      const auto speaker = receivedName(p.speakerName, sizeof(p.speakerName));
      const auto message = text(p.message);
      const auto& party = m_state["party"];
      if(p.channelID == 0 || p.channelID != party.value("chat_channel", uint64_t{0}) ||
         party.value("count", 0) < 2 || p.speakerEntityID == m_entity ||
         std::none_of(party.at("members").begin(), party.at("members").end(), [&](const auto& member) {
           return member.value("entity_id", 0u) == p.speakerEntityID &&
                  member.value("character_id", uint64_t{0}) == p.speakerCharacterID &&
                  member.value("name", "") == speaker;
         }))
        throw ProtocolError("party chat sender/channel does not match received membership");
      Json received{{"party_id", party.at("id")}, {"channel", p.channelID},
                    {"actor", p.speakerEntityID}, {"character_id", p.speakerCharacterID},
                    {"name", speaker}, {"message", message}, {"token", m_seq + 1}};
      m_state["party_chat"].push_back(received);
      if(m_state["party_chat"].size() > 64) m_state["party_chat"].erase(m_state["party_chat"].begin());
      event("party_chat", received);
      return;
    }
    if(name != "zone") return;
    if(segment.header.source_actor == m_entity && m_rewards.receive(h.type, segment.data))
    {
      Json detail{{"opcode", h.type}};
      if(h.type == WS::FFXIVIpcItemOperationBatch::_ServerIpcType)
        detail["batch"] = m_rewards.state()["operation_batches"].back();
      else if(h.type == WS::FFXIVIpcItemSize::_ServerIpcType)
      {
        const auto p = readObject<WS::FFXIVIpcItemSize>(segment.data, off);
        Json items = Json::object();
        for(const auto& entry : m_rewards.state()["inventory"].items())
          if(entry.value()["storage"] == p.storageId) items[entry.key()] = entry.value();
        detail["snapshot"] = {{"context", p.contextId}, {"storage", p.storageId},
                              {"size", p.size}, {"items", items}};
      }
      event("rewards_changed", detail);
    }
    if(m_combat.receive(h.type, segment.header.source_actor, segment.data))
    {
      Json detail{{"opcode", h.type}};
      if(h.type == WS::FFXIVIpcActionIntegrity::_ServerIpcType)
      {
        const auto& latest = m_combat.state()["integrities"].back();
        const auto key = std::to_string(latest["target"].get<uint32_t>());
        if(m_state["actors"].contains(key))
          m_combat.annotateLatestIntegrity(m_state["actors"][key]["hp"].get<uint32_t>());
        const auto& integrity = m_combat.state()["integrities"].back();
        if(m_state["actors"].contains(key))
          for(const auto* field : {"hp", "hp_max", "mp", "tp"}) m_state["actors"][key][field] = integrity[field];
        detail["integrity"] = integrity;
      }
      else if(h.type == WS::FFXIVIpcActorCast::_ServerIpcType)
        detail["cast"] = m_combat.state()["casts"].back();
      else if(h.type == WS::FFXIVIpcHudParam::_ServerIpcType)
      {
        const auto& hud = m_combat.state()["hud_params"].back();
        const auto key = std::to_string(hud["target"].get<uint32_t>());
        if(m_state["actors"].contains(key))
          for(const auto* field : {"hp", "hp_max", "mp", "tp"}) m_state["actors"][key][field] = hud[field];
        detail["hud_params"] = hud;
      }
      else if(h.type == WS::FFXIVIpcActorControlSelf::_ServerIpcType)
      {
        detail["start"] = m_combat.state()["starts"].back();
        if(detail["start"]["source"] == m_entity &&
           (detail["start"]["action"] == 9 || detail["start"]["action"] == 11 ||
            detail["start"]["action"] == 53 || detail["start"]["action"] == 54 ||
            detail["start"]["action"] == 142))
        {
          const auto recast = detail["start"]["recast_centiseconds"].get<uint32_t>();
          if(recast != 250) throw ProtocolError("unsupported starting-melee recast");
          m_startingActionReady = std::chrono::steady_clock::now() + std::chrono::milliseconds(recast * 10);
        }
      }
      else
      {
        const size_t count = h.type == WS::FFXIVIpcActionResult1::_ServerIpcType ? 1 :
          readObject<WS::FFXIVIpcActionResult>(segment.data, sizeof(Wire::FFXIVARR_IPC_HEADER)).TargetCount;
        const auto& effects = m_combat.state()["effects"];
        detail["effects"] = Json(effects.end() - count, effects.end());
        for(const auto& row : detail["effects"])
          if(row["source"] == m_entity && row["action"] == 9)
            for(const auto& effect : row["source_effects"])
              if(effect["type"] == 29 && effect["value"] == 9 && effect["flag"] == 0x80)
              {
                m_fastBladeComboTarget = row["target"];
                m_fastBladeComboDeadline = std::chrono::steady_clock::now() +
                  std::chrono::milliseconds(Common::MAX_COMBO_LENGTH);
              }
      }
      event("combat_changed", detail);
    }
    if(h.type == WS::FFXIVIpcPlayerStatus::_ServerIpcType)
    {
      const auto p = readObject<WS::FFXIVIpcPlayerStatus>(segment.data, off);
      m_state["homepoint"] = p.HomePoint;
      Json discoveries = Json::array();
      for(const auto part : {1u, 3u})
        if((p.Discovery16[16] & (uint8_t{1} << part)) != 0) discoveries.push_back(part);
      for(const auto part : {1u, 3u})
      {
        const auto oldValue = std::find(m_state["central_thanalan_discoveries"].begin(),
                                        m_state["central_thanalan_discoveries"].end(), part) !=
                              m_state["central_thanalan_discoveries"].end();
        const auto newValue = std::find(discoveries.begin(), discoveries.end(), part) != discoveries.end();
        if(oldValue != newValue)
          event("discovery_state", {{"map_id", 21}, {"part_id", part}, {"discovered", newValue}});
      }
      m_state["central_thanalan_discoveries"] = discoveries;
      m_state["central_thanalan_discovery"] = !discoveries.empty() && discoveries[0] == 1;
    }
    if(h.type == WS::FFXIVIpcInviteResult::_ServerIpcType)
    {
      const auto p = readObject<WS::FFXIVIpcInviteResult>(segment.data, off);
      if(p.AuthType != Common::HierarchyType::PCPARTY)
        throw ProtocolError("unsupported invite result type");
      m_state["party_invite_result"] = {{"result", p.Result}, {"target", receivedName(p.TargetName, sizeof(p.TargetName))}};
      event("party_invite_result", m_state["party_invite_result"]);
    }
    if(h.type == WS::FFXIVIpcInviteUpdate::_ServerIpcType)
    {
      const auto p = readObject<WS::FFXIVIpcInviteUpdate>(segment.data, off);
      if(p.AuthType != Common::HierarchyType::PCPARTY || p.InviteCharacterID == 0 ||
         (p.Result != Common::InviteUpdateType::NEW_INVITE && p.Result != Common::InviteUpdateType::ACCEPT_INVITE &&
          p.Result != Common::InviteUpdateType::REJECT_INVITE))
        throw ProtocolError("unsupported party invite update");
      Json update{{"character_id", p.InviteCharacterID}, {"auth_type", p.AuthType}, {"result", p.Result},
                  {"name", receivedName(p.InviteName, sizeof(p.InviteName))}};
      m_state["party_invite_update"] = update;
      if(p.Result == Common::InviteUpdateType::NEW_INVITE) m_state["pending_party_invite"] = update;
      event("party_invite_update", update);
    }
    if(h.type == WS::FFXIVIpcInviteReplyResult::_ServerIpcType)
    {
      const auto p = readObject<WS::FFXIVIpcInviteReplyResult>(segment.data, off);
      if(p.AuthType != Common::HierarchyType::PCPARTY ||
         (p.Answer != Common::InviteReplyType::DENY && p.Answer != Common::InviteReplyType::ACCEPT))
        throw ProtocolError("unsupported party invite reply result");
      m_state["party_invite_reply"] = {{"result", p.Result}, {"auth_type", p.AuthType},
                                        {"answer", p.Answer},
                                        {"name", receivedName(p.InviteCharacterName,
                                                               sizeof(p.InviteCharacterName))}};
      event("party_invite_reply", m_state["party_invite_reply"]);
    }
    if(h.type == WS::FFXIVIpcUpdateParty::_ServerIpcType)
    {
      const auto p = readObject<WS::FFXIVIpcUpdateParty>(segment.data, off);
      if(p.PartyCount > 8 || (p.PartyCount == 0) != (p.PartyID == 0) ||
         (p.PartyCount == 0) != (p.ChatChannel == 0) ||
         (p.PartyCount && p.LeaderIndex >= p.PartyCount))
        throw ProtocolError("malformed received party state");
      Json members = Json::array();
      for(size_t i = 0; i < p.PartyCount; ++i)
      {
        const auto& member = p.Member[i];
        if(!member.CharaId || !member.EntityId) throw ProtocolError("party member identity missing");
        members.push_back({{"character_id", member.CharaId}, {"entity_id", member.EntityId},
                           {"name", receivedName(member.Name, sizeof(member.Name))},
                           {"territory", member.TerritoryType}, {"level", member.Lv},
                           {"class_job", member.ClassJob}});
      }
      m_state["party"] = {{"id", p.PartyID}, {"chat_channel", p.ChatChannel},
                          {"count", p.PartyCount}, {"leader_index", p.LeaderIndex},
                          {"members", members}};
      event("party_state", m_state["party"]);
    }
    if(h.type == WS::FFXIVIpcDiscoveryReply::_ServerIpcType)
    {
      const auto p = readObject<WS::FFXIVIpcDiscoveryReply>(segment.data, off);
      if(p.mapId != 21 || (p.mapPartId != 1 && p.mapPartId != 3))
        throw ProtocolError("unsupported discovery reply identity");
      m_state["discovery_reply"] = {{"map_id", p.mapId}, {"part_id", p.mapPartId}};
      event("discovery_reply", m_state["discovery_reply"]);
    }
    if(h.type == WS::FFXIVIpcInitZone::_ServerIpcType)
    {
      const auto p = readObject<WS::FFXIVIpcInitZone>(segment.data, off);
      m_haveZone = true; m_selfSpawn = false;
      m_combat = CombatState{};
      m_movement.cancel(); m_moving = false;
      m_state["territory"] = p.TerritoryType;
      for(auto it = m_state["actors"].begin(); it != m_state["actors"].end(); ++it)
        if(it.value().value("kind", 0) == 1 && m_state["known_players"].contains(it.key()))
          m_state["known_players"][it.key()].update({{"spawned", false}, {"last_seen_token", m_seq + 1}});
      m_state["actors"] = Json::object();
      m_state["observed_position"] = p.Pos;
      std::copy(std::begin(p.Pos), std::end(p.Pos), m_predicted.begin());
      m_state["predicted_position"] = m_predicted;
      phase("loading");
      event("init_zone", {{"territory", p.TerritoryType}, {"position", p.Pos}});
      // This branch's SetLanguage handler is its load-completion acknowledgement.
      sendZone(WC::ClientZoneIpcType::SetLanguage, Bytes(8, 0));
    }
    else if(h.type == WS::FFXIVIpcPlayerSpawn::_ServerIpcType)
    {
      const auto p = readObject<WS::FFXIVIpcPlayerSpawn>(segment.data, off);
      const auto actor = segment.header.source_actor;
      const auto name = p.ObjKind == 1 ? receivedName(p.Name, sizeof(p.Name)) : std::string{};
      Json state{{"position", p.Pos}, {"gm_rank", p.GMRank}, {"level", p.Lv}, {"hp", p.Hp},
        {"hp_max", p.HpMax}, {"tp", p.Tp}, {"mp", p.Mp}, {"kind", p.ObjKind}, {"layout_id", p.LayoutId},
        {"base_id", p.NpcId}, {"name_id", p.NameId}, {"name", name}};
      m_state["actors"][std::to_string(actor)] = state;
      if(p.ObjKind == 1 && actor && !name.empty())
        m_state["known_players"][std::to_string(actor)] =
          {{"name", name}, {"spawned", true}, {"last_seen_token", m_seq + 1}};
      event("spawn", {{"actor", actor}, {"state", state}});
      if(actor == m_entity)
      {
        m_selfSpawn = true; m_state["gm_rank"] = p.GMRank; m_state["observed_position"] = p.Pos;
        if(m_haveZone && m_chatAck)
        {
          WC::FFXIVIpcClientTrigger finish{};
          finish.Id = Network::ActorControl::PacketCommand::FINISH_LOADING;
          sendZone(finish._ServerIpcType, objectBytes(finish));
          // Readiness is confirmed by the resulting condition update, not by sending this command.
        }
      }
    }
    else if(h.type == WS::FFXIVIpcWarp::_ServerIpcType && segment.header.source_actor == m_entity)
    {
      // A same-zone warp of this character: the server moved us without a zone change.
      const auto p = readObject<WS::FFXIVIpcWarp>(segment.data, off);
      const std::array<float, 3> position{p.x, p.y, p.z};
      m_movement.cancel(); m_moving = false;
      m_state["observed_position"] = position;
      m_predicted = position;
      m_state["predicted_position"] = m_predicted;
      m_state["last_warp"] = {{"type", p.Type}, {"position", position}, {"token", m_seq + 1}};
      event("warp", {{"type", p.Type}, {"position", position}});
    }
    else if(h.type == WS::FFXIVIpcCondition::_ServerIpcType)
    {
      auto p = readObject<WS::FFXIVIpcCondition>(segment.data, off);
      constexpr auto flag = static_cast<size_t>(Common::PlayerCondition::BetweenAreas);
      bool loading = (p.conditionFlags[flag / 8] & (1 << (flag % 8))) != 0;
      m_state["between_areas"] = loading;
      event("conditions", {{"between_areas", loading}});
      if(!loading && m_haveZone && m_selfSpawn && m_chatAck && m_state["phase"] == "loading")
      { m_deadline.cancel(); phase("ready"); }
    }
    else if(h.type == WS::FFXIVIpcResting::_ServerIpcType)
    {
      const auto p = readObject<WS::FFXIVIpcResting>(segment.data, off);
      auto key = std::to_string(segment.header.source_actor);
      if(m_state["actors"].contains(key))
        m_state["actors"][key].update(Json{{"hp", p.Hp}, {"tp", p.Tp}, {"mp", p.Mp}});
      event("hp_changed", {{"actor", segment.header.source_actor}, {"hp", p.Hp}, {"mp", p.Mp}, {"tp", p.Tp}});
    }
    else if(h.type == WS::FFXIVIpcActorMove::_ServerIpcType)
    {
      const auto p = readObject<WS::FFXIVIpcActorMove>(segment.data, off);
      std::array<float, 3> position{};
      for(size_t i = 0; i < 3; ++i) position[i] = static_cast<float>(p.pos[i]) / 65535.0f * 2000.0f - 1000.0f;
      const auto actor = segment.header.source_actor;
      auto key = std::to_string(actor);
      if(m_state["actors"].contains(key)) m_state["actors"][key]["position"] = position;
      event("movement", {{"actor", actor}, {"position", position}});
    }
    else if(h.type == WS::FFXIVIpcActorFreeSpawn::_ServerIpcType)
    {
      auto p = readObject<WS::FFXIVIpcActorFreeSpawn>(segment.data, off);
      const auto key = std::to_string(p.actorId);
      m_state["actors"].erase(key);
      if(m_state["known_players"].contains(key))
        m_state["known_players"][key].update({{"spawned", false}, {"last_seen_token", m_seq + 1}});
      event("despawn", {{"actor", p.actorId}});
    }
    else if(h.type == WS::FFXIVIpcQuests::_ServerIpcType)
    {
      auto p = readObject<WS::FFXIVIpcQuests>(segment.data, off);
      for(size_t i = 0; i < m_quests.size(); ++i)
        m_quests[i] = {{"id", p.activeQuests[i].c.questId}, {"sequence", p.activeQuests[i].c.sequence}};
      updateQuests(); event("quests", m_state["quests"]);
    }
    else if(h.type == WS::FFXIVIpcQuest::_ServerIpcType)
    {
      auto p = readObject<WS::FFXIVIpcQuest>(segment.data, off);
      if(p.index >= m_quests.size()) throw ProtocolError("invalid quest slot");
      m_quests[p.index] = {{"id", p.questInfo.c.questId}, {"sequence", p.questInfo.c.sequence}};
      updateQuests(); event("quests", m_state["quests"]);
    }
    else if(h.type == WS::FFXIVIpcQuestCompleteList::_ServerIpcType)
    {
      auto p = readObject<WS::FFXIVIpcQuestCompleteList>(segment.data, off);
      m_state["complete_quests"] = Json::object();
      for(size_t i = 0; i < sizeof(p.questCompleteMask) * 8; ++i)
        if(questCompletionFlag(p.questCompleteMask, sizeof(p.questCompleteMask), i))
          m_state["complete_quests"][std::to_string(i)] = true;
      event("quest_completion_list");
    }
    else if(h.type == WS::FFXIVIpcQuestFinish::_ServerIpcType)
    {
      auto p = readObject<WS::FFXIVIpcQuestFinish>(segment.data, off);
      m_state["complete_quests"][std::to_string(p.bitIndex)] = p.completed != 0;
      event("quest_complete", {{"id", p.bitIndex}, {"completed", p.completed != 0}});
    }
    else if(h.type == WS::FFXIVIpcEventStart::_ServerIpcType)
    {
      auto p = readObject<WS::FFXIVIpcEventStart>(segment.data, off);
      m_state["event_id"] = p.handlerId; event("event_start", {{"event_id", p.handlerId}});
    }
    else if(h.type >= WS::ServerZoneIpcType::EventPlayHeader && h.type <= WS::ServerZoneIpcType::EventPlay255)
    {
      auto p = readObject<WS::FFXIVIpcPlayEventSceneHeader>(segment.data, off);
      m_state["scene"] = {{"event_id", p.eventId}, {"scene_id", p.scene}, {"flags", p.sceneFlags}, {"token", m_seq + 1}};
      event("scene", m_state["scene"]);
    }
    else if(h.type == WS::FFXIVIpcEventFinish::_ServerIpcType)
    {
      auto p = readObject<WS::FFXIVIpcEventFinish>(segment.data, off);
      m_state["event_id"] = nullptr; m_state["scene"] = nullptr;
      event("event_finish", {{"event_id", p.handlerId}});
    }
    else if(h.type == WS::FFXIVIpcChat::_ServerIpcType)
    {
      auto p = readObject<WS::FFXIVIpcChat>(segment.data, off);
      Json message{{"actor", p.entityId}, {"kind", p.type}, {"message", text(p.message)}, {"token", m_seq + 1}};
      m_state["chat"].push_back(message);
      if(m_state["chat"].size() > 64) m_state["chat"].erase(m_state["chat"].begin());
      event("chat", message);
    }
    else if(h.type == WS::FFXIVIpcEnableLogout::_ServerIpcType)
    {
      readObject<WS::FFXIVIpcEnableLogout>(segment.data, off);
      m_heartbeat.cancel(); m_movement.cancel(); phase("logged_out"); event("logout_ack");
    }
  }

  void Client::moveStep()
  {
    float distance = 0;
    for(size_t i = 0; i < 3; ++i) distance += std::pow(m_destination[i] - m_predicted[i], 2);
    distance = std::sqrt(distance);
    const auto fraction = distance > 0 ? std::min(1.0f, m_speed * 0.1f / distance) : 1.0f;
    WC::FFXIVIpcUpdatePosition p{};
    p.dir = std::atan2(m_destination[0] - m_predicted[0], m_destination[2] - m_predicted[2]);
    for(size_t i = 0; i < 3; ++i) m_predicted[i] += (m_destination[i] - m_predicted[i]) * fraction;
    p.pos.x = m_predicted[0]; p.pos.y = m_predicted[1]; p.pos.z = m_predicted[2];
    p.flag = fraction < 1 ? Common::Walking : 0;
    const bool final = fraction >= 1;
    std::function<void()> complete;
    if(final)
    {
      complete = [self = shared_from_this()] {
        self->m_moving = false;
        self->event("route_sent", {{"position", self->m_predicted}});
      };
    }
    sendZone(p._ServerIpcType, objectBytes(p), std::move(complete));
    m_state["predicted_position"] = m_predicted;
    if(final) return;
    m_movement.expires_from_now(std::chrono::milliseconds(100));
    m_movement.async_wait([self = shared_from_this()](auto ec) {
      if(ec) return;
      try { self->moveStep(); } catch(const std::exception& e) { self->fail(e.what()); }
    });
  }
}
