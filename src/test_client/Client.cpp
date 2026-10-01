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

  Channel::Channel(asio::io_service& io, Receive receive, std::function<void(const std::string&)> error) :
    m_socket(io), m_receive(std::move(receive)), m_error(std::move(error)) {}

  void Channel::connect(const std::string& host, uint16_t port, std::function<void()> ready)
  {
    // The initial runner deliberately supports only local, disposable servers.
    auto address = asio::ip::address::from_string(host);
    if(!address.is_loopback() || !port) throw ProtocolError("test endpoints must be loopback with a nonzero port");
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

  Bot::Bot(asio::io_service& io, std::string id, Emit emit) :
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
      {"heartbeat_replies", 0},
      {"heartbeats", {{"zone", 0}, {"chat", 0}}}, {"packets_received", 0}};
  }
  void Bot::event(const std::string& name, Json data)
  {
    m_emit({{"type", "event"}, {"bot", m_id}, {"seq", ++m_seq}, {"event", name}, {"data", std::move(data)}});
  }
  void Bot::phase(const std::string& value) { m_state["phase"] = value; event("phase", {{"phase", value}}); }
  void Bot::close()
  {
    m_deadline.cancel(); m_heartbeat.cancel(); m_movement.cancel(); m_moving = false;
    if(m_lobby) m_lobby->close();
    if(m_zone) m_zone->close();
    if(m_chat) m_chat->close();
  }
  void Bot::fail(const std::string& reason)
  {
    if(m_state["phase"] == "failed" || m_state["phase"] == "closed") return;
    close();
    // Only protocol/transport diagnoses are emitted; never include input payloads/session data.
    m_state["error"] = reason;
    phase("failed");
    event("failure", {{"reason", reason}});
    m_login = Json::object();
  }
  std::shared_ptr<Channel> Bot::channel(const std::string& name)
  {
    std::weak_ptr<Bot> weak = shared_from_this();
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
  void Bot::login(const Json& args)
  {
    if(m_state["phase"] != "disconnected") throw ProtocolError("bot already started; create a fresh bot");
    const auto session = args.at("session").get<std::string>();
    const auto character = args.at("character").get<std::string>();
    if(session.empty() || session.size() >= 64) throw ProtocolError("invalid session length");
    if(character.empty() || character.size() >= 32) throw ProtocolError("invalid character name length");
    const auto createCharacter = args.value("create_character", false);
    const auto deleteCharacter = args.value("delete_character", false);
    const auto expectAbsent = args.value("expect_character_absent", false);
    const auto expectNameRejected = args.value("expect_name_rejected", false);
    if(static_cast<int>(createCharacter) + static_cast<int>(deleteCharacter) + static_cast<int>(expectAbsent) +
       static_cast<int>(expectNameRejected) > 1)
      throw ProtocolError("character lobby modes are mutually exclusive");
    if((createCharacter || deleteCharacter || expectAbsent || expectNameRejected) &&
       !std::all_of(character.begin(), character.end(), [](unsigned char c) {
         return c == ' ' || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z');
       }))
      throw ProtocolError("character lobby operation name must contain only alphabetic ASCII and spaces");
    if(createCharacter)
      canonicalUldahCreationPayload(args.value("creation_class", 1));
    else if(args.contains("creation_class"))
      throw ProtocolError("creation class is valid only for character creation");
    const auto timeout = args.value("timeout", 30);
    if(timeout < 1 || timeout > 120) throw ProtocolError("login timeout outside 1..120 seconds");
    m_login = args;
    m_deadline.expires_from_now(std::chrono::seconds(timeout));
    m_deadline.async_wait([self = shared_from_this()](auto ec) { if(!ec) self->fail("login deadline exceeded"); });
    m_lobby = channel("lobby");
    phase("lobby_connecting");
    m_lobby->connect(args.at("host"), args.at("port"), [self = shared_from_this()] {
      auto handshake = self->m_cipher.initialize(std::random_device{}(), "SapphireE2E");
      self->phase("lobby_encryption");
      self->m_lobby->send(frame(0, 9, handshake));
    });
  }
  void Bot::sendLobby(uint16_t opcode, const Bytes& payload)
  {
    auto bytes = ipc(opcode, payload);
    m_cipher.encrypt(bytes);
    // Sapphire's client-receive profile excludes a 16-byte trailer from decryption.
    bytes.resize(bytes.size() + 16, 0);
    m_lobby->send(frame(0, 3, bytes));
  }
  void Bot::sendZone(uint16_t opcode, const Bytes& payload, std::function<void()> complete)
  {
    if(!m_zone) throw ProtocolError("zone channel not initialized");
    m_zone->send(frame(1, 3, ipc(opcode, payload), m_entity), std::move(complete));
  }
  void Bot::sendChat(uint16_t opcode, const Bytes& payload)
  {
    if(!m_chat) throw ProtocolError("chat channel not initialized");
    m_chat->send(frame(2, 3, ipc(opcode, payload), m_entity));
  }
  void Bot::receive(const std::string& name, Segment segment)
  {
    m_state["packets_received"] = m_state["packets_received"].get<uint64_t>() + 1;
    if(name == "lobby") lobbyPacket(std::move(segment));
    else worldPacket(name, std::move(segment));
  }
  void Bot::lobbyPacket(Segment segment)
  {
    if(segment.header.type == 10 && m_state["phase"] == "lobby_encryption")
    {
      m_cipher.decrypt(segment.data);
      if(readObject<uint32_t>(segment.data) != 0xE0003C2A) throw ProtocolError("unexpected lobby encryption reply");
      LC::FFXIVIpcLoginEx p{};
      p.requestNumber = 1; p.clientTimeValue = timeSeconds(); p.clientLangCode = 1;
      copyText(p.sessionId, m_login.at("session"));
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
      if(m_state["phase"] == "character_name_reservation" && m_login.value("expect_name_rejected", false) &&
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
      const std::string wanted = m_login.at("character");
      const auto found = std::find_if(m_state["characters"].begin(), m_state["characters"].end(),
        [&](const auto& character) { return character.at("name") == wanted; });
      if(afterDeletion || m_login.value("expect_character_absent", false))
      {
        if(found != m_state["characters"].end()) throw ProtocolError("deleted character remains in refreshed lobby list");
        m_deadline.cancel();
        m_state["deleted_via_lobby"] = afterDeletion;
        phase(afterDeletion ? "lobby_deleted" : "character_absent");
        return;
      }
      if(m_login.value("delete_character", false))
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
      if(!afterCreation && (m_login.value("create_character", false) ||
                            m_login.value("expect_name_rejected", false)) && m_state["characters"].empty())
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
         text(p.chrArray[0].chrName) != m_login.at("character"))
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
      const std::string wanted = m_login.at("character");
      if(p.optionParam != LC::CharacterOperation::CHARAOPE_RESERVENAME || p.count != 1 ||
         text(p.chrArray[0].chrName) != wanted || !p.chrArray[0].characterId)
        throw ProtocolError("invalid character-name reservation reply");
      if(m_login.value("expect_name_rejected", false))
        throw ProtocolError("duplicate character name was unexpectedly reserved");
      m_creationCharacterId = p.chrArray[0].characterId;
      LC::FFXIVIpcCharaMake request{};
      request.requestNumber = 4; request.clientTimeValue = timeSeconds();
      request.characterId = m_creationCharacterId;
      request.operation = LC::CharacterOperation::CHARAOPE_MAKECHARA;
      request.worldId = p.chrArray[0].worldId;
      copyText(request.chracterName, wanted);
      const auto details = canonicalUldahCreationPayload(m_login.value("creation_class", 1));
      copyText(request.charaMakeData, details);
      phase("character_creating");
      sendLobby(request._ServerIpcType, objectBytes(request));
    }
    else if(h.type == LS::FFXIVIpcCharaMakeReply::_ServerIpcType && m_state["phase"] == "character_creating")
    {
      const auto p = readObject<LS::FFXIVIpcCharaMakeReply>(segment.data, sizeof(h));
      if(p.optionParam != LC::CharacterOperation::CHARAOPE_MAKECHARA || p.count != 1 ||
         text(p.chrArray[0].chrName) != m_login.at("character"))
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
      m_login = Json::object(); // Drop the session secret as soon as handoff has completed.
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
  void Bot::worldLogin()
  {
    phase("loading");
    WC::FFXIVIpcLoginHandler login{};
    login.clientTimeValue = timeSeconds();
    sendZone(login._ServerIpcType, objectBytes(login));
    heartbeat();
  }
  void Bot::heartbeat()
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
  void Bot::updateQuests()
  {
    m_state["quests"] = Json::object();
    for(const auto& q : m_quests)
      if(!q.is_null() && q["id"] != 0) m_state["quests"][std::to_string(q["id"].get<uint32_t>())] = q;
  }
  void Bot::worldPacket(const std::string& name, Segment segment)
  {
    if(segment.header.type == 8)
    {
      m_state["heartbeat_replies"] = m_state["heartbeat_replies"].get<uint64_t>() + 1;
      m_state["heartbeats"][name] = m_state["heartbeats"][name].get<uint64_t>() + 1;
      event("heartbeat", {{"channel", name}}); return;
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
    event("packet", {{"channel", name}, {"opcode", h.type}, {"source", segment.header.source_actor}});
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

  void Bot::moveStep()
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

  Json Bot::command(const std::string& method, const Json& args)
  {
    if(method == "snapshot")
    {
      auto state = m_state; state["seq"] = m_seq; state["moving"] = m_moving;
      state["rewards"] = m_rewards.state(); state["combat"] = m_combat.state();
      state["combat"]["starting_action_guard_remaining_ms"] =
        startingActionGuardRemainingMs(m_startingActionReady, std::chrono::steady_clock::now());
      return state;
    }
    if(method == "close") { close(); phase("closed"); return Json::object(); }
    if(m_state["phase"] != "ready") throw ProtocolError("action requires a world-ready bot");
    if(method == "invite_party_bound" || method == "accept_party_bound" || method == "decline_party_bound" ||
       method == "party_chat_bound" || method == "disband_party_bound")
    {
      // Validate and publish on this same Asio thread. Distinct method names
      // make old workers reject the operation instead of ignoring new guards.
      requirePartyContext(m_state["party"], m_state["pending_party_invite"], args);
      return command(method.substr(0, method.size() - 6), args);
    }
    if(method == "walk_to")
    {
      if(m_moving || !m_state["scene"].is_null()) throw ProtocolError("movement/event already in progress");
      auto destination = args.at("position").get<std::array<float, 3>>();
      float speed = args.value("speed", 2.0f);
      float distance = 0;
      for(size_t i = 0; i < 3; ++i)
      {
        if(!std::isfinite(destination[i])) throw ProtocolError("nonfinite waypoint");
        distance += std::pow(destination[i] - m_predicted[i], 2);
      }
      if(!std::isfinite(speed) || speed <= 0 || speed > 6 || distance > 100 * 100)
        throw ProtocolError("waypoint exceeds 100m or speed outside (0,6]");
      m_destination = destination; m_speed = speed; m_moving = true;
      // Include the first tick in the cadence, also when chaining short waypoints.
      m_movement.expires_from_now(std::chrono::milliseconds(100));
      m_movement.async_wait([self = shared_from_this()](auto ec) {
        if(ec) return;
        try { self->moveStep(); } catch(const std::exception& e) { self->fail(e.what()); }
      });
      return {{"completion", "route_sent is prediction only; verify with an observer"}};
    }
    if(method == "interact")
    {
      if(m_moving || !m_state["event_id"].is_null()) throw ProtocolError("movement/event already in progress");
      WC::FFXIVIpcEventHandlerTalk p{};
      p.actorId = args.at("actor_id"); p.eventId = args.at("event_id");
      sendZone(p._ServerIpcType, objectBytes(p)); return Json::object();
    }
    if(method == "start_uldah_opening")
    {
      if(m_moving || !m_state["event_id"].is_null() || !m_state["scene"].is_null() ||
         m_state["territory"] != 182)
        throw ProtocolError("Ul'dah opening requires an idle character in opening territory 182");
      WC::FFXIVIpcEnterTerritoryHandler p{};
      p.eventId = 1245187;
      sendZone(p._ServerIpcType, objectBytes(p));
      return Json::object();
    }
    if(method == "enter_uldah_opening_range")
    {
      if(m_moving || !m_state["event_id"].is_null() || !m_state["scene"].is_null())
        throw ProtocolError("opening range requires an idle character");
      const auto position = args.at("position").get<std::array<float, 3>>();
      auto payload = openingWithinRangeRequest(m_state["territory"], args.at("event_id"),
                                               args.at("param"), m_predicted, position);
      sendZone(WC::FFXIVIpcEventHandlerWithinRange::_ServerIpcType, payload);
      return Json::object();
    }
    if(method == "discover_central_thanalan")
    {
      if(m_moving || !m_state["event_id"].is_null() || m_state["territory"] != 141)
        throw ProtocolError("discovery requires an idle character in territory 141");
      const auto layout = args.at("layout_id").get<uint32_t>();
      const auto part = args.at("part_id").get<uint32_t>();
      if((layout != 3643706 || part != 1) && (layout != 4204061 || part != 3))
        throw ProtocolError("unsupported discovery layout/part identity");
      if(std::find(m_state["discovery_requests_sent"].begin(), m_state["discovery_requests_sent"].end(), layout) !=
           m_state["discovery_requests_sent"].end() ||
         std::find(m_state["central_thanalan_discoveries"].begin(),
                   m_state["central_thanalan_discoveries"].end(), part) !=
           m_state["central_thanalan_discoveries"].end())
        throw ProtocolError("discovery part was already requested or received");
      const auto receivedPosition = args.at("received_position").get<std::array<float, 3>>();
      if(std::sqrt(std::pow(receivedPosition[0]-m_predicted[0], 2) +
                   std::pow(receivedPosition[1]-m_predicted[1], 2) +
                   std::pow(receivedPosition[2]-m_predicted[2], 2)) > 0.15f)
        throw ProtocolError("discovery witness does not match the actor's predicted endpoint");
      auto payload = centralThanalanDiscoveryRequest(m_state["territory"], layout, receivedPosition);
      m_state["discovery_requests_sent"].push_back(layout);
      sendZone(WC::FFXIVIpcNewDiscovery::_ServerIpcType, payload);
      return Json::object();
    }
    if(method == "choose_scene")
    {
      const auto& scene = m_state["scene"];
      if(scene.is_null() || scene.at("token") != args.at("token") || scene.at("event_id") != args.at("event_id") ||
         scene.at("scene_id") != args.at("scene_id")) throw ProtocolError("scene identity/token mismatch");
      auto results = args.at("results").get<std::vector<uint32_t>>();
      if(results.empty() || results.size() > 2) throw ProtocolError("only explicit one/two-result scenes supported");
      WC::FFXIVIpcReturnEventScene2 p{};
      p.handlerId = scene.at("event_id"); p.sceneId = scene.at("scene_id"); p.numOfResults = static_cast<uint8_t>(results.size());
      std::copy(results.begin(), results.end(), p.results);
      sendZone(p._ServerIpcType, objectBytes(p)); m_state["scene"] = nullptr;
      return Json::object();
    }
    if(method == "sell_shop_item")
    {
      const auto& scene = m_state["scene"];
      if(scene.is_null() || scene.at("token") != args.at("token") ||
         scene.at("event_id") != args.at("event_id") || scene.at("scene_id") != 40 ||
         (scene.at("event_id").get<uint32_t>() >> 16) != 4)
        throw ProtocolError("shop sale requires the matching received gil-shop scene 40");
      const auto storage = args.at("storage").get<uint16_t>();
      const auto slot = args.at("slot").get<uint16_t>();
      const auto item = args.at("expected_item").get<uint32_t>();
      const auto count = args.at("expected_count").get<uint32_t>();
      if(storage > 3 || slot >= 25 || item > 0xffff || count != 1)
        throw ProtocolError("shop sale supports one observed single-item ordinary-bag stack");
      const auto key = std::to_string(storage) + ":" + std::to_string(slot);
      const auto& inventory = m_rewards.state()["inventory"];
      if(!inventory.contains(key) || inventory.at(key).at("storage") != storage ||
         inventory.at(key).at("slot") != slot || inventory.at(key).at("id") != item ||
         inventory.at(key).at("count") != count)
        throw ProtocolError("shop sale source does not match the complete received inventory");
      sendZone(WC::FFXIVIpcReturnEventScene255::_ServerIpcType,
               shopSaleReturn(scene.at("event_id"), storage, slot, static_cast<uint16_t>(item)));
      m_state["scene"] = nullptr;
      return Json::object();
    }
    if(method == "buy_shop_item")
    {
      constexpr uint32_t shop = 262468, item = 5890, gil = 28;
      unsigned stage = 0;
      try
      {
        const auto& scene = m_state["scene"];
        const auto& rewards = m_rewards.state();
        stage = 1;
        if(!scene.is_object() || !args.contains("token") || !args.contains("event_id") ||
           !scene.contains("token") || !scene.contains("event_id") || !scene.contains("scene_id") ||
           scene["token"] != args["token"] || scene["event_id"] != args["event_id"] ||
           scene["event_id"] != shop || scene["scene_id"] != 40)
          throw ProtocolError("shop purchase requires the matching received supported scene 40");
        stage = 2;
        const auto& inventory = rewards.at("inventory");
        if(!inventory.is_object() || !inventory.contains("2000:0") ||
           inventory.at("2000:0").at("id") != 1 || inventory.at("2000:0").at("count") != gil)
          throw ProtocolError("shop purchase requires the exact received sale proceeds");
        stage = 3;
        for(const auto& entry : inventory)
          if(entry.at("id") == item)
            throw ProtocolError("supported purchase item must be absent before purchase");
        stage = 4;
        sendZone(WC::FFXIVIpcReturnEventScene255::_ServerIpcType, shopPurchaseReturn(shop));
        m_state["scene"] = nullptr;
        return Json::object();
      }
      catch(const ProtocolError&) { throw; }
      catch(const std::exception&)
      {
        throw ProtocolError("malformed received shop purchase state at validation stage " + std::to_string(stage));
      }
    }
    if(method == "buy_shop_equipment")
    {
      constexpr uint32_t shop = 262468, item = 3286, gil = 56;
      const auto& scene = m_state["scene"];
      const auto& inventory = m_rewards.state().at("inventory");
      if(!scene.is_object() || scene.value("token", uint64_t{0}) != args.at("token") ||
         scene.value("event_id", 0u) != args.at("event_id") ||
         scene.value("event_id", 0u) != shop || scene.value("scene_id", 0u) != 40 ||
         !inventory.contains("2000:0") || inventory.at("2000:0").value("id", 0u) != 1 ||
         inventory.at("2000:0").value("count", 0u) != gil)
        throw ProtocolError("equipment purchase requires exact received shop and sale proceeds");
      for(const auto& entry : inventory)
        if(entry.value("id", 0u) == item || entry.value("id", 0u) == 5890 || entry.value("id", 0u) == 4551)
          throw ProtocolError("equipment purchase requires exact post-sale inventory");
      sendZone(WC::FFXIVIpcReturnEventScene255::_ServerIpcType,
               shopEquipmentPurchaseReturn(shop));
      m_state["scene"] = nullptr;
      return Json::object();
    }
    if(method == "buy_shop_second_equipment")
    {
      constexpr uint32_t shop = 262468, item = 3748, gil = 56;
      const auto& scene = m_state["scene"];
      const auto& inventory = m_rewards.state().at("inventory");
      if(!scene.is_object() || scene.value("token", uint64_t{0}) != args.at("token") ||
         scene.value("event_id", 0u) != args.at("event_id") ||
         scene.value("event_id", 0u) != shop || scene.value("scene_id", 0u) != 40 ||
         !inventory.contains("2000:0") || inventory.at("2000:0").value("id", 0u) != 1 ||
         inventory.at("2000:0").value("count", 0u) != gil)
        throw ProtocolError("second equipment purchase requires exact received shop and resale proceeds");
      for(const auto& entry : inventory)
        if(entry.value("id", 0u) == item || entry.value("id", 0u) == 3286 ||
           entry.value("id", 0u) == 5890 || entry.value("id", 0u) == 4551)
          throw ProtocolError("second equipment purchase requires exact post-resale inventory");
      sendZone(WC::FFXIVIpcReturnEventScene255::_ServerIpcType,
               shopSecondEquipmentPurchaseReturn(shop));
      m_state["scene"] = nullptr;
      return Json::object();
    }
    if(method == "buy_shop_third_equipment")
    {
      constexpr uint32_t shop = 262468, item = 2967, gil = 101;
      const auto& scene = m_state["scene"];
      const auto& inventory = m_rewards.state().at("inventory");
      if(!scene.is_object() || scene.value("token", uint64_t{0}) != args.at("token") ||
         scene.value("event_id", 0u) != args.at("event_id") ||
         scene.value("event_id", 0u) != shop || scene.value("scene_id", 0u) != 40 ||
         !inventory.contains("2000:0") || inventory.at("2000:0").value("id", 0u) != 1 ||
         inventory.at("2000:0").value("count", 0u) != gil)
        throw ProtocolError("third equipment purchase requires exact received shop and liquidation proceeds");
      for(const auto& entry : inventory)
        if(entry.value("id", 0u) == item || entry.value("id", 0u) == 3748 ||
           entry.value("id", 0u) == 3286 || entry.value("id", 0u) == 3296 ||
           entry.value("id", 0u) == 5890 || entry.value("id", 0u) == 4551)
          throw ProtocolError("third equipment purchase requires exact post-liquidation inventory");
      sendZone(WC::FFXIVIpcReturnEventScene255::_ServerIpcType,
               shopThirdEquipmentPurchaseReturn(shop));
      m_state["scene"] = nullptr;
      return Json::object();
    }
    if(method == "buy_shop_head_equipment")
    {
      constexpr uint32_t shop = 262415, item = 2638, gil = 101;
      const auto& scene = m_state["scene"];
      const auto& inventory = m_rewards.state().at("inventory");
      if(!scene.is_object() || scene.value("token", uint64_t{0}) != args.at("token") ||
         scene.value("event_id", 0u) != args.at("event_id") ||
         scene.value("event_id", 0u) != shop || scene.value("scene_id", 0u) != 40 ||
         !inventory.contains("2000:0") || inventory.at("2000:0").value("id", 0u) != 1 ||
         inventory.at("2000:0").value("count", 0u) != gil ||
         !inventory.contains("1000:3") || inventory.at("1000:3").value("id", 0u) != 2967)
        throw ProtocolError("head equipment purchase requires exact received shop/funds/equipment state");
      for(const auto& entry : inventory)
        if(entry.value("id", 0u) == item || entry.value("id", 0u) == 2983)
          throw ProtocolError("head equipment purchase requires exact post-body-liquidation inventory");
      sendZone(WC::FFXIVIpcReturnEventScene255::_ServerIpcType,
               shopHeadEquipmentPurchaseReturn(shop));
      m_state["scene"] = nullptr;
      return Json::object();
    }
    if(method == "buy_shop_ear_equipment")
    {
      constexpr uint32_t shop = 262425, item = 4200, gil = 102;
      const auto& scene = m_state["scene"];
      const auto& inventory = m_rewards.state().at("inventory");
      if(!scene.is_object() || scene.value("token", uint64_t{0}) != args.at("token") ||
         scene.value("event_id", 0u) != args.at("event_id") ||
         scene.value("event_id", 0u) != shop || scene.value("scene_id", 0u) != 40 ||
         !inventory.contains("2000:0") || inventory.at("2000:0").value("id", 0u) != 1 ||
         inventory.at("2000:0").value("count", 0u) != gil ||
         !inventory.contains("1000:2") || inventory.at("1000:2").value("id", 0u) != 2638)
        throw ProtocolError("ear equipment purchase requires exact received shop/funds/equipment state");
      for(const auto& entry : inventory)
        if(entry.value("id", 0u) == item || entry.value("id", 0u) == 3750)
          throw ProtocolError("ear equipment purchase requires exact post-feet-liquidation inventory");
      sendZone(WC::FFXIVIpcReturnEventScene255::_ServerIpcType,
               shopEarEquipmentPurchaseReturn(shop));
      m_state["scene"] = nullptr;
      return Json::object();
    }
    if(method == "buy_shop_neck_equipment")
    {
      constexpr uint32_t shop = 262640, item = 15130, gil = 208;
      const auto& scene = m_state["scene"];
      const auto& inventory = m_rewards.state().at("inventory");
      if(!scene.is_object() || scene.value("token", uint64_t{0}) != args.at("token") ||
         scene.value("event_id", 0u) != args.at("event_id") ||
         scene.value("event_id", 0u) != shop || scene.value("scene_id", 0u) != 40 ||
         !inventory.contains("2000:0") || inventory.at("2000:0").value("id", 0u) != 1 ||
         inventory.at("2000:0").value("count", 0u) != gil)
        throw ProtocolError("neck equipment purchase requires exact received shop/funds state");
      for(const auto& entry : inventory)
        if(entry.value("id", 0u) == item || entry.value("id", 0u) == 2967 ||
           entry.value("id", 0u) == 2638 || entry.value("id", 0u) == 4200)
          throw ProtocolError("neck equipment purchase requires exact post-liquidation inventory");
      for(const auto slot : {3u, 2u, 8u, 9u})
        if(inventory.contains("1000:" + std::to_string(slot)))
          throw ProtocolError("neck equipment purchase requires exact empty supported equipment slots");
      sendZone(WC::FFXIVIpcReturnEventScene255::_ServerIpcType,
               shopNeckEquipmentPurchaseReturn(shop));
      m_state["scene"] = nullptr;
      return Json::object();
    }
    if(method == "buy_shop_wrist_equipment")
    {
      constexpr uint32_t shop = 262640, item = 15132, gil = 208;
      const auto& scene = m_state["scene"];
      const auto& inventory = m_rewards.state().at("inventory");
      if(!scene.is_object() || scene.value("token", uint64_t{0}) != args.at("token") ||
         scene.value("event_id", 0u) != args.at("event_id") ||
         scene.value("event_id", 0u) != shop || scene.value("scene_id", 0u) != 40 ||
         !inventory.contains("2000:0") || inventory.at("2000:0").value("id", 0u) != 1 ||
         inventory.at("2000:0").value("count", 0u) != gil ||
         inventory.contains("1000:9") || inventory.contains("1000:10"))
        throw ProtocolError("wrist equipment purchase requires exact received shop/funds/equipment state");
      for(const auto& entry : inventory)
        if(entry.value("id", 0u) == item || entry.value("id", 0u) == 15130)
          throw ProtocolError("wrist equipment purchase requires exact post-neck-liquidation inventory");
      sendZone(WC::FFXIVIpcReturnEventScene255::_ServerIpcType,
               shopWristEquipmentPurchaseReturn(shop));
      m_state["scene"] = nullptr;
      return Json::object();
    }
    if(method == "invite_party")
    {
      const auto& party = m_state["party"];
      const auto count = party.at("count").get<uint8_t>();
      const auto leaderIndex = party.at("leader_index").get<size_t>();
      const auto isLeader = count == 0 ||
        (leaderIndex < party.at("members").size() &&
         party.at("members")[leaderIndex].value("entity_id", 0u) == m_entity);
      if(m_moving || !m_state["event_id"].is_null() || count >= 8 || !isLeader)
        throw ProtocolError("party invite requires an idle ungrouped character or received party leadership");
      auto payload = partyInviteRequest(m_state["actors"], args.at("target"), args.at("name"));
      sendZone(WC::FFXIVIpcInvite::_ServerIpcType, payload);
      return Json::object();
    }
    if(method == "accept_party" || method == "decline_party")
    {
      if(m_moving || !m_state["event_id"].is_null() || m_state["party"].at("count") != 0)
        throw ProtocolError("party reply requires an idle ungrouped character");
      auto payload = method == "accept_party" ? partyAcceptRequest(m_state["pending_party_invite"]) :
                                                partyDeclineRequest(m_state["pending_party_invite"]);
      m_state["pending_party_invite"] = nullptr;
      m_state["party_invite_reply"] = nullptr;
      sendZone(WC::FFXIVIpcInviteReply::_ServerIpcType, payload);
      return Json::object();
    }
    if(method == "leave_party")
    {
      if(m_moving || !m_state["event_id"].is_null()) throw ProtocolError("party leave requires an idle character");
      auto payload = partyLeaveRequest(m_state["party"], m_entity);
      sendZone(WC::FFXIVIpcPcPartyLeave::_ServerIpcType, payload);
      return Json::object();
    }
    if(method == "disband_party")
    {
      if(m_moving || !m_state["event_id"].is_null())
        throw ProtocolError("party disband requires an idle character");
      auto payload = partyDisbandRequest(m_state["party"], m_entity);
      sendZone(WC::FFXIVIpcPcPartyDisband::_ServerIpcType, payload);
      return Json::object();
    }
    if(method == "kick_party_member")
    {
      if(m_moving || !m_state["event_id"].is_null())
        throw ProtocolError("party kick requires an idle character");
      auto payload = partyKickRequest(m_state["party"], m_entity,
                                      args.at("target"), args.at("name"));
      sendZone(WC::FFXIVIpcPcPartyKick::_ServerIpcType, payload);
      return Json::object();
    }
    if(method == "change_party_leader")
    {
      if(m_moving || !m_state["event_id"].is_null())
        throw ProtocolError("party leader change requires an idle character");
      auto payload = partyChangeLeaderRequest(m_state["party"], m_entity,
                                               args.at("target"), args.at("name"));
      sendZone(WC::FFXIVIpcPcPartyChangeLeader::_ServerIpcType, payload);
      return Json::object();
    }
    if(method == "party_chat")
    {
      if(m_moving || !m_state["event_id"].is_null()) throw ProtocolError("party chat requires an idle character");
      auto payload = partyChatRequest(m_state["party"], m_entity, args.at("message"));
      sendChat(WC::FFXIVIpcChatToChannel::_ServerIpcType, payload);
      return {{"party_id", m_state["party"].at("id")},
              {"channel", m_state["party"].at("chat_channel")}};
    }
    if(method == "cast_return")
    {
      if(m_moving || !m_state["event_id"].is_null()) throw ProtocolError("living Return requires an idle character");
      if(std::chrono::steady_clock::now() < m_startingActionReady) throw ProtocolError("starting-action recast pending");
      if(m_actionRequest >= 65535) throw ProtocolError("action request budget exhausted");
      auto payload = livingReturnRequest(m_entity, ++m_actionRequest,
                                         m_state.at("territory"), m_state.at("homepoint"),
                                         m_state["actors"]);
      sendZone(WC::FFXIVIpcActionRequest::_ServerIpcType, payload);
      m_startingActionReady = std::chrono::steady_clock::now() + std::chrono::milliseconds(5000);
      return {{"request", m_actionRequest}};
    }
    if(method == "sprint")
    {
      if(m_moving || !m_state["event_id"].is_null()) throw ProtocolError("movement/event already in progress");
      if(std::chrono::steady_clock::now() < m_startingActionReady) throw ProtocolError("starting-action recast pending");
      if(m_actionRequest >= 65535) throw ProtocolError("combat request budget exhausted");
      auto payload = sprintRequest(m_entity, ++m_actionRequest, m_state["actors"]);
      sendZone(WC::FFXIVIpcActionRequest::_ServerIpcType, payload);
      m_startingActionReady = std::chrono::steady_clock::now() + std::chrono::milliseconds(2500);
      return {{"request", m_actionRequest}};
    }
    if(method == "fast_blade" || method == "savage_blade" || method == "bootshine" ||
       method == "true_strike" || method == "blizzard")
    {
      if(m_moving || !m_state["event_id"].is_null()) throw ProtocolError("movement/event already in progress");
      if(!args.at("target").is_number_unsigned() || args.at("target") > uint64_t{0xffffffff})
        throw ProtocolError("combat target must be an observed 32-bit actor id");
      if(std::chrono::steady_clock::now() < m_startingActionReady) throw ProtocolError("starting-action recast pending");
      if(m_actionRequest >= 65535) throw ProtocolError("combat request budget exhausted");
      Bytes payload;
      if(method == "fast_blade")
        payload = fastBladeRequest(m_entity, ++m_actionRequest, args.at("target"), m_predicted,
                                   m_state["actors"], m_rewards.state());
      else if(method == "savage_blade")
      {
        if(args.at("target") != m_fastBladeComboTarget ||
           std::chrono::steady_clock::now() > m_fastBladeComboDeadline)
          throw ProtocolError("Savage Blade requires unexpired received Fast Blade combo readiness");
        payload = savageBladeRequest(m_entity, ++m_actionRequest, args.at("target"), m_predicted,
                                     m_state["actors"], m_rewards.state(), m_combat.state());
        m_fastBladeComboTarget = 0;
        m_fastBladeComboDeadline = {};
      }
      else if(method == "bootshine")
        payload = bootshineRequest(m_entity, ++m_actionRequest, args.at("target"), m_predicted,
                                   m_state["actors"], m_rewards.state());
      else if(method == "true_strike")
        payload = trueStrikeRequest(m_entity, ++m_actionRequest, args.at("target"), m_predicted,
                                    m_state["actors"], m_rewards.state());
      else
        payload = blizzardRequest(m_entity, ++m_actionRequest, args.at("target"), m_predicted,
                                  m_state["actors"], m_rewards.state());
      sendZone(WC::FFXIVIpcActionRequest::_ServerIpcType, payload);
      // Conservative request pacing; the received ActionStart moves this deadline forward.
      m_startingActionReady = std::chrono::steady_clock::now() + std::chrono::milliseconds(2500);
      return {{"request", m_actionRequest}};
    }
    if(method == "return_homepoint")
    {
      if(m_moving || !m_state["event_id"].is_null()) throw ProtocolError("movement/event already in progress");
      if(m_state["homepoint"].is_null()) throw ProtocolError("return requires a received homepoint");
      auto payload = returnHomepointRequest(m_entity, m_state.at("territory").get<uint16_t>(),
        m_state.at("homepoint").get<uint8_t>(), m_state.at("actors"));
      const auto deadline = args.value("deadline_seconds", 30u);
      if(deadline < 30 || deadline > 90) throw ProtocolError("return deadline must be 30..90 seconds");
      sendZone(WC::FFXIVIpcClientTrigger::_ServerIpcType, payload);
      phase("zoning");
      m_deadline.expires_from_now(std::chrono::seconds(deadline));
      m_deadline.async_wait([self = shared_from_this()](auto ec) {
        if(!ec) self->fail("homepoint return deadline exceeded");
      });
      return Json::object();
    }
    if(method == "cross_exit")
    {
      if(m_moving || !m_state["event_id"].is_null()) throw ProtocolError("movement/event already in progress");
      auto payload = exitRangeRequest(m_state.at("territory"), m_predicted, args.at("exit"));
      const auto deadline = args.value("deadline_seconds", 30u);
      if(deadline < 30 || deadline > 90) throw ProtocolError("transition deadline must be 30..90 seconds");
      sendZone(WC::FFXIVIpcZoneJump::_ServerIpcType, payload);
      phase("zoning");
      m_deadline.expires_from_now(std::chrono::seconds(deadline));
      m_deadline.async_wait([self = shared_from_this()](auto ec) {
        if(!ec) self->fail("territory transition deadline exceeded");
      });
      return Json::object();
    }
    if(method == "use_shop_vfx_item")
    {
      if(m_moving || !m_state["event_id"].is_null()) throw ProtocolError("item action requires an idle character");
      for(const auto* key : {"storage", "slot", "expected_count"})
        if(!args.at(key).is_number_unsigned() || args.at(key) > uint64_t{0xffffffff})
          throw ProtocolError("item action arguments must be unsigned 32-bit integers");
      if(m_actionRequest >= 65535) throw ProtocolError("action request budget exhausted");
      auto payload = shopVfxItemRequest(m_rewards.state(), m_entity, ++m_actionRequest,
                                        args.at("storage"), args.at("slot"), args.at("expected_count"));
      sendZone(WC::FFXIVIpcActionRequest::_ServerIpcType, payload);
      return {{"request", m_actionRequest}};
    }
    if(method == "discard_item")
    {
      if(m_moving || !m_state["event_id"].is_null()) throw ProtocolError("movement/event already in progress");
      for(const auto* key : {"storage", "slot", "expected_item"})
        if(!args.at(key).is_number_unsigned() || args.at(key) > uint64_t{0xffffffff})
          throw ProtocolError("inventory arguments must be unsigned 32-bit integers");
      if(m_inventoryContext == 0xffffffff) throw ProtocolError("inventory context budget exhausted");
      auto payload = discardItemRequest(m_rewards.state(), m_entity, ++m_inventoryContext,
                                       args.at("storage"), args.at("slot"), args.at("expected_item"));
      sendZone(WC::FFXIVIpcClientInventoryItemOperation::_ServerIpcType, payload);
      return {{"context", m_inventoryContext}};
    }
    if(method == "request_item_unequip")
    {
      if(m_moving || !m_state["event_id"].is_null()) throw ProtocolError("movement/event already in progress");
      for(const auto* key : {"gear_slot", "expected_item", "destination_storage", "destination_slot"})
        if(!args.at(key).is_number_unsigned() || args.at(key) > uint64_t{0xffffffff})
          throw ProtocolError("inventory arguments must be unsigned 32-bit integers");
      if(m_inventoryContext == 0xffffffff) throw ProtocolError("inventory context budget exhausted");
      auto payload = unequipItemRequest(m_rewards.state(), m_entity, ++m_inventoryContext,
                                    args.at("gear_slot"), args.at("expected_item"),
                                    args.at("destination_storage"), args.at("destination_slot"));
      sendZone(WC::FFXIVIpcClientInventoryItemOperation::_ServerIpcType, payload);
      return {{"context", m_inventoryContext}};
    }
    if(method == "request_shop_item_equip")
    {
      if(m_moving || !m_state["event_id"].is_null()) throw ProtocolError("movement/event already in progress");
      for(const auto* key : {"storage", "slot", "expected_item", "gear_slot"})
        if(!args.at(key).is_number_unsigned() || args.at(key) > uint64_t{0xffffffff})
          throw ProtocolError("inventory arguments must be unsigned 32-bit integers");
      if(m_inventoryContext == 0xffffffff) throw ProtocolError("inventory context budget exhausted");
      auto payload = equipShopItemRequest(m_rewards.state(), m_entity, ++m_inventoryContext,
                                          args.at("storage"), args.at("slot"), args.at("expected_item"),
                                          args.at("gear_slot"));
      sendZone(WC::FFXIVIpcClientInventoryItemOperation::_ServerIpcType, payload);
      return {{"context", m_inventoryContext}};
    }
    if(method == "request_item_reequip_starter")
    {
      if(m_moving || !m_state["event_id"].is_null()) throw ProtocolError("movement/event already in progress");
      for(const auto* key : {"storage", "slot", "expected_item", "gear_slot"})
        if(!args.at(key).is_number_unsigned() || args.at(key) > uint64_t{0xffffffff})
          throw ProtocolError("inventory arguments must be unsigned 32-bit integers");
      if(m_inventoryContext == 0xffffffff) throw ProtocolError("inventory context budget exhausted");
      auto payload = reequipStarterItemRequest(m_rewards.state(), m_entity, ++m_inventoryContext,
                                    args.at("storage"), args.at("slot"), args.at("expected_item"),
                                    args.at("gear_slot"));
      sendZone(WC::FFXIVIpcClientInventoryItemOperation::_ServerIpcType, payload);
      return {{"context", m_inventoryContext}};
    }
    if(method == "request_currency_move_rejection")
    {
      if(m_moving || !m_state["event_id"].is_null()) throw ProtocolError("movement/event already in progress");
      if(!args.at("expected_gil").is_number_unsigned() || args.at("expected_gil") > uint64_t{0xffffffff})
        throw ProtocolError("expected gil must be an unsigned 32-bit integer");
      if(m_inventoryContext == 0xffffffff) throw ProtocolError("inventory context budget exhausted");
      auto payload = currencyMoveRejectionRequest(m_rewards.state(), m_entity, ++m_inventoryContext,
                                                   args.at("expected_gil"));
      sendZone(WC::FFXIVIpcClientInventoryItemOperation::_ServerIpcType, payload);
      return {{"context", m_inventoryContext}};
    }
    if(method == "request_item_move")
    {
      if(m_moving || !m_state["event_id"].is_null()) throw ProtocolError("movement/event already in progress");
      for(const auto* key : {"storage", "slot", "expected_item", "destination_storage", "destination_slot"})
        if(!args.at(key).is_number_unsigned() || args.at(key) > uint64_t{0xffffffff})
          throw ProtocolError("inventory arguments must be unsigned 32-bit integers");
      if(m_inventoryContext == 0xffffffff) throw ProtocolError("inventory context budget exhausted");
      auto payload = moveItemRequest(m_rewards.state(), m_entity, ++m_inventoryContext,
                                    args.at("storage"), args.at("slot"), args.at("expected_item"),
                                    args.at("destination_storage"), args.at("destination_slot"));
      sendZone(WC::FFXIVIpcClientInventoryItemOperation::_ServerIpcType, payload);
      return {{"context", m_inventoryContext}};
    }
    if(method == "request_item_swap")
    {
      if(m_moving || !m_state["event_id"].is_null()) throw ProtocolError("movement/event already in progress");
      for(const auto* key : {"storage", "slot", "expected_item", "destination_storage",
                             "destination_slot", "expected_destination_item"})
        if(!args.at(key).is_number_unsigned() || args.at(key) > uint64_t{0xffffffff})
          throw ProtocolError("inventory arguments must be unsigned 32-bit integers");
      if(m_inventoryContext == 0xffffffff) throw ProtocolError("inventory context budget exhausted");
      auto payload = swapItemRequest(m_rewards.state(), m_entity, ++m_inventoryContext,
                                    args.at("storage"), args.at("slot"), args.at("expected_item"),
                                    args.at("destination_storage"), args.at("destination_slot"),
                                    args.at("expected_destination_item"));
      sendZone(WC::FFXIVIpcClientInventoryItemOperation::_ServerIpcType, payload);
      return {{"context", m_inventoryContext}};
    }
    if(method == "request_item_split" || method == "request_item_merge")
    {
      if(m_moving || !m_state["event_id"].is_null()) throw ProtocolError("movement/event already in progress");
      const auto keys = method == "request_item_split"
        ? std::vector<const char*>{"storage", "slot", "expected_item", "expected_count", "split_count",
                                   "destination_storage", "destination_slot"}
        : std::vector<const char*>{"storage", "slot", "expected_item", "expected_count",
                                   "destination_storage", "destination_slot", "expected_destination_count"};
      for(const auto* key : keys)
        if(!args.at(key).is_number_unsigned() || args.at(key) > uint64_t{0xffffffff})
          throw ProtocolError("inventory arguments must be unsigned 32-bit integers");
      if(m_inventoryContext == 0xffffffff) throw ProtocolError("inventory context budget exhausted");
      Bytes payload;
      if(method == "request_item_split")
        payload = splitItemRequest(m_rewards.state(), m_entity, ++m_inventoryContext,
          args.at("storage"), args.at("slot"), args.at("expected_item"), args.at("expected_count"),
          args.at("split_count"), args.at("destination_storage"), args.at("destination_slot"));
      else
        payload = mergeItemRequest(m_rewards.state(), m_entity, ++m_inventoryContext,
          args.at("storage"), args.at("slot"), args.at("expected_item"), args.at("expected_count"),
          args.at("destination_storage"), args.at("destination_slot"), args.at("expected_destination_count"));
      sendZone(WC::FFXIVIpcClientInventoryItemOperation::_ServerIpcType, payload);
      return {{"context", m_inventoryContext}};
    }
    if(method == "tell_visible")
    {
      auto payload = visibleTellRequest(m_state, m_moving, args);
      sendChat(WC::FFXIVIpcChatTo::_ServerIpcType, payload);
      return Json::object(); // Local publication only, not delivery evidence.
    }
    if(method == "tell_remote")
    {
      if(m_moving || !m_state["event_id"].is_null()) throw ProtocolError("remote tell requires an idle character");
      auto payload = remoteTellRequest(m_state["actors"], m_state["known_players"], m_state["party"],
                                       m_state["party_chat"], m_state["tells"], m_seq,
                                       args.at("target"), args.at("name"), args.at("message"));
      sendChat(WC::FFXIVIpcChatTo::_ServerIpcType, payload);
      return Json::object();
    }
    if(method == "tell" || method == "tell_offline")
    {
      if(m_moving || !m_state["event_id"].is_null()) throw ProtocolError("tell requires an idle character");
      const auto target = args.at("target").get<uint32_t>();
      const auto targetName = args.at("name").get<std::string>();
      const auto expectOffline = method == "tell_offline";
      bool allowRemoteParty = false;
      if(!expectOffline && !m_state["actors"].contains(std::to_string(target)))
      {
        const auto& party = m_state["party"];
        for(auto it = m_state["party_chat"].rbegin(); it != m_state["party_chat"].rend(); ++it)
          if(it->value("actor", 0u) == target && it->value("name", "") == targetName &&
             it->value("party_id", uint64_t{0}) == party.value("id", uint64_t{0}) &&
             it->value("channel", uint64_t{0}) == party.value("chat_channel", uint64_t{0}) &&
             it->value("token", uint64_t{0}) <= m_seq && m_seq - it->value("token", uint64_t{0}) <= 16)
          {
            allowRemoteParty = true;
            break;
          }
      }
      auto payload = tellRequest(m_state["actors"], m_state["party"], target, targetName,
                                 args.at("message"), expectOffline, allowRemoteParty);
      if(expectOffline)
      {
        m_state["tell_not_found"] = nullptr;
        m_state["offline_tell_pending"] = true;
      }
      sendChat(WC::FFXIVIpcChatTo::_ServerIpcType, payload);
      return Json::object();
    }
    if(method == "development_place_registered")
    {
      // Separate administrative API; ordinary Say and non-GM gameplay remain
      // unable to send debug commands. Validate/consume on this Asio thread.
      const auto message = m_developmentPlacements.consume(m_state, m_moving, args);
      WC::FFXIVIpcChatHandler p{};
      p.clientTimeValue = timeSeconds(); p.position.originEntityId = m_entity;
      std::copy(m_predicted.begin(), m_predicted.end(), p.position.pos);
      p.chatType = Common::ChatType::Say; copyText(p.message, message);
      sendZone(p._ServerIpcType, objectBytes(p));
      return {{"scope", "administrative-preparation-not-gameplay"},
              {"publication", "local-only"}, {"placement_verified", false}};
    }
    if(method == "say")
    {
      const auto message = args.at("message").get<std::string>();
      if(message.empty() || message.size() > 128 || message[0] == '!' ||
         !std::all_of(message.begin(), message.end(), [](unsigned char c) { return c >= 32 && c <= 126; }))
        throw ProtocolError("say requires 1..128 printable ASCII characters, not a debug command");
      WC::FFXIVIpcChatHandler p{};
      p.clientTimeValue = timeSeconds(); p.position.originEntityId = m_entity;
      std::copy(m_predicted.begin(), m_predicted.end(), p.position.pos);
      p.chatType = Common::ChatType::Say; copyText(p.message, message);
      sendZone(p._ServerIpcType, objectBytes(p)); return Json::object();
    }
    if(method == "logout")
    {
      m_movement.cancel(); m_moving = false;
      // Sapphire 3.3 registers logoutHandler under StartLogoutCountdown.
      sendZone(WC::ClientZoneIpcType::StartLogoutCountdown, Bytes(8, 0)); phase("logging_out"); return Json::object();
    }
    throw ProtocolError("unknown bot method");
  }
}
