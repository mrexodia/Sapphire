#include "Client.h"
#include "InventoryActions.h"
#include "ShopActions.h"
#include "RespawnActions.h"
#include "TransitionActions.h"
#include <Network/CommonActorControl.h>
#include <Network/PacketDef/Lobby/ClientLobbyDef.h>
#include <Network/PacketDef/Lobby/ServerLobbyDef.h>
#include <Network/PacketDef/Zone/ClientZoneDef.h>
#include <Network/PacketDef/Zone/ServerZoneDef.h>
#include <cmath>
#include <random>

namespace Sapphire::Testing
{
  namespace LC = Wire::LobbyPackets::Client;
  namespace LS = Wire::LobbyPackets::Server;
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
  void Channel::send(Bytes bytes)
  {
    if(m_closed) throw ProtocolError("send on closed channel");
    if(m_queued + bytes.size() > 2 * Decoder::MaxFrame) throw ProtocolError("send queue limit exceeded");
    const bool idle = m_output.empty();
    m_queued += bytes.size();
    m_output.push_back(std::move(bytes));
    if(idle) write();
  }
  void Channel::write()
  {
    asio::async_write(m_socket, asio::buffer(m_output.front()), [self = shared_from_this()](auto ec, size_t) {
      if(self->m_closed) return;
      if(ec) return self->error("write failed");
      self->m_queued -= self->m_output.front().size();
      self->m_output.pop_front();
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
      {"actors", Json::object()}, {"quests", Json::object()}, {"complete_quests", Json::object()},
      {"chat", Json::array()}, {"created_via_lobby", false},
      {"scene", nullptr}, {"event_id", nullptr}, {"heartbeat_replies", 0},
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
    if(args.value("create_character", false) &&
       !std::all_of(character.begin(), character.end(), [](unsigned char c) {
         return c == ' ' || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z');
       }))
      throw ProtocolError("created character name must contain only alphabetic ASCII and spaces");
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
  void Bot::sendZone(uint16_t opcode, const Bytes& payload)
  {
    if(!m_zone) throw ProtocolError("zone channel not initialized");
    m_zone->send(frame(1, 3, ipc(opcode, payload), m_entity));
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
      throw ProtocolError("lobby rejected request");
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
            (m_state["phase"] == "character_list" || m_state["phase"] == "character_list_after_creation"))
    {
      const bool afterCreation = m_state["phase"] == "character_list_after_creation";
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
      for(const auto& c : m_state["characters"])
      {
        if(c["name"] != wanted) continue;
        if(afterCreation) m_state["created_via_lobby"] = true;
        LC::FFXIVIpcGameLogin request{};
        request.requestNumber = afterCreation ? 6 : 3; request.clientTimeValue = timeSeconds();
        request.playerId = c["entity_id"]; request.characterId = c["character_id"];
        request.characterIndex = c["index"]; request.worldId = c["world"];
        phase("world_handoff");
        sendLobby(request._ServerIpcType, objectBytes(request));
        return;
      }
      if(!afterCreation && m_login.value("create_character", false) && m_state["characters"].empty())
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
            m_state["phase"] == "character_name_reservation")
    {
      const auto p = readObject<LS::FFXIVIpcCharaMakeReply>(segment.data, sizeof(h));
      const std::string wanted = m_login.at("character");
      if(p.optionParam != LC::CharacterOperation::CHARAOPE_RESERVENAME || p.count != 1 ||
         text(p.chrArray[0].chrName) != wanted || !p.chrArray[0].characterId)
        throw ProtocolError("invalid character-name reservation reply");
      m_creationCharacterId = p.chrArray[0].characterId;
      LC::FFXIVIpcCharaMake request{};
      request.requestNumber = 4; request.clientTimeValue = timeSeconds();
      request.characterId = m_creationCharacterId;
      request.operation = LC::CharacterOperation::CHARAOPE_MAKECHARA;
      request.worldId = p.chrArray[0].worldId;
      copyText(request.chracterName, wanted);
      constexpr auto details = "{\"content\":[[\"1\",\"0\",\"1\",\"50\",\"1\",\"1\",\"1\",\"1\",\"0\",\"0\",\"0\",\"1\",\"1\",\"1\",\"1\",\"1\",\"1\",\"1\",\"0\",\"0\",\"0\",\"0\",\"0\",\"0\",\"0\",\"0\"],\"1\",\"1\",\"1\",\"1\",\"1\",\"1\"]}";
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
    if(segment.header.type != 3 || name != "zone") return;
    const auto h = readObject<Wire::FFXIVARR_IPC_HEADER>(segment.data);
    event("packet", {{"channel", name}, {"opcode", h.type}, {"source", segment.header.source_actor}});
    constexpr size_t off = sizeof(Wire::FFXIVARR_IPC_HEADER);
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
      else if(h.type == WS::FFXIVIpcActorControlSelf::_ServerIpcType)
      {
        detail["start"] = m_combat.state()["starts"].back();
        if(detail["start"]["source"] == m_entity && detail["start"]["action"] == 9)
        {
          const auto recast = detail["start"]["recast_centiseconds"].get<uint32_t>();
          if(recast != 250) throw ProtocolError("unsupported Fast Blade recast");
          m_fastBladeReady = std::chrono::steady_clock::now() + std::chrono::milliseconds(recast * 10);
        }
      }
      else
      {
        const size_t count = h.type == WS::FFXIVIpcActionResult1::_ServerIpcType ? 1 :
          readObject<WS::FFXIVIpcActionResult>(segment.data, sizeof(Wire::FFXIVARR_IPC_HEADER)).TargetCount;
        const auto& effects = m_combat.state()["effects"];
        detail["effects"] = Json(effects.end() - count, effects.end());
      }
      event("combat_changed", detail);
    }
    if(h.type == WS::FFXIVIpcPlayerStatus::_ServerIpcType)
    {
      const auto p = readObject<WS::FFXIVIpcPlayerStatus>(segment.data, off);
      m_state["homepoint"] = p.HomePoint;
    }
    if(h.type == WS::FFXIVIpcInitZone::_ServerIpcType)
    {
      const auto p = readObject<WS::FFXIVIpcInitZone>(segment.data, off);
      m_haveZone = true; m_selfSpawn = false;
      m_combat = CombatState{};
      m_movement.cancel(); m_moving = false;
      m_state["territory"] = p.TerritoryType;
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
      Json state{{"position", p.Pos}, {"gm_rank", p.GMRank}, {"level", p.Lv}, {"hp", p.Hp},
        {"hp_max", p.HpMax}, {"tp", p.Tp}, {"mp", p.Mp}, {"kind", p.ObjKind}, {"layout_id", p.LayoutId}, {"base_id", p.NpcId}, {"name_id", p.NameId}};
      m_state["actors"][std::to_string(actor)] = state;
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
      m_state["actors"].erase(std::to_string(p.actorId)); event("despawn", {{"actor", p.actorId}});
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
    sendZone(p._ServerIpcType, objectBytes(p));
    m_state["predicted_position"] = m_predicted;
    if(fraction >= 1) { m_moving = false; event("route_sent", {{"position", m_predicted}}); return; }
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
      state["combat"]["fast_blade_guard_remaining_ms"] =
        fastBladeGuardRemainingMs(m_fastBladeReady, std::chrono::steady_clock::now());
      return state;
    }
    if(method == "close") { close(); phase("closed"); return Json::object(); }
    if(m_state["phase"] != "ready") throw ProtocolError("action requires a world-ready bot");
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
    if(method == "fast_blade")
    {
      if(m_moving || !m_state["event_id"].is_null()) throw ProtocolError("movement/event already in progress");
      if(!args.at("target").is_number_unsigned() || args.at("target") > uint64_t{0xffffffff})
        throw ProtocolError("combat target must be an observed 32-bit actor id");
      if(std::chrono::steady_clock::now() < m_fastBladeReady) throw ProtocolError("Fast Blade recast pending");
      if(m_actionRequest >= 65535) throw ProtocolError("combat request budget exhausted");
      auto payload = fastBladeRequest(m_entity, ++m_actionRequest, args.at("target"), m_predicted,
                                      m_state["actors"], m_rewards.state());
      sendZone(WC::FFXIVIpcActionRequest::_ServerIpcType, payload);
      // Conservative request pacing; the received ActionStart moves this deadline forward.
      m_fastBladeReady = std::chrono::steady_clock::now() + std::chrono::milliseconds(2500);
      return {{"request", m_actionRequest}};
    }
    if(method == "return_homepoint")
    {
      if(m_moving || !m_state["event_id"].is_null()) throw ProtocolError("movement/event already in progress");
      if(m_state["homepoint"].is_null()) throw ProtocolError("return requires a received homepoint");
      auto payload = returnHomepointRequest(m_entity, m_state.at("territory").get<uint16_t>(),
        m_state.at("homepoint").get<uint8_t>(), m_state.at("actors"));
      sendZone(WC::FFXIVIpcClientTrigger::_ServerIpcType, payload);
      phase("zoning");
      m_deadline.expires_from_now(std::chrono::seconds(30));
      m_deadline.async_wait([self = shared_from_this()](auto ec) {
        if(!ec) self->fail("homepoint return deadline exceeded");
      });
      return Json::object();
    }
    if(method == "cross_exit")
    {
      if(m_moving || !m_state["event_id"].is_null()) throw ProtocolError("movement/event already in progress");
      auto payload = exitRangeRequest(m_state.at("territory"), m_predicted, args.at("exit"));
      sendZone(WC::FFXIVIpcZoneJump::_ServerIpcType, payload);
      phase("zoning");
      m_deadline.expires_from_now(std::chrono::seconds(30));
      m_deadline.async_wait([self = shared_from_this()](auto ec) {
        if(!ec) self->fail("territory transition deadline exceeded");
      });
      return Json::object();
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
