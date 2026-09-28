#pragma once
#include "Protocol.h"
#include "RewardsState.h"
#include "CombatState.h"
#include <asio.hpp>
#include <nlohmann/json.hpp>
#include <deque>
#include <chrono>
#include <functional>
#include <memory>

namespace Sapphire::Testing
{
  using Json = nlohmann::json;
  using Emit = std::function<void(const Json&)>;

  class Channel : public std::enable_shared_from_this<Channel>
  {
  public:
    using Receive = std::function<void(Segment)>;
    Channel(asio::io_service& io, Receive receive, std::function<void(const std::string&)> error);
    void connect(const std::string& host, uint16_t port, std::function<void()> ready);
    void send(Bytes bytes);
    void close();
  private:
    void read();
    void write();
    void error(const std::string& reason);
    asio::ip::tcp::socket m_socket;
    Decoder m_decoder;
    std::array<uint8_t, 16384> m_input{};
    std::deque<Bytes> m_output;
    size_t m_queued = 0;
    bool m_closed = false;
    Receive m_receive;
    std::function<void(const std::string&)> m_error;
  };

  class Bot : public std::enable_shared_from_this<Bot>
  {
  public:
    Bot(asio::io_service& io, std::string id, Emit emit);
    void login(const Json& args);
    Json command(const std::string& method, const Json& args);
    void close();
    void fail(const std::string& reason);
  private:
    std::shared_ptr<Channel> channel(const std::string& name);
    void receive(const std::string& name, Segment segment);
    void lobbyPacket(Segment segment);
    void worldPacket(const std::string& name, Segment segment);
    void worldLogin();
    void heartbeat();
    void moveStep();
    void sendLobby(uint16_t opcode, const Bytes& payload);
    void sendZone(uint16_t opcode, const Bytes& payload);
    void event(const std::string& name, Json data = Json::object());
    void phase(const std::string& phase);
    void updateQuests();
    asio::io_service& m_io;
    std::string m_id;
    Emit m_emit;
    uint64_t m_seq = 0;
    Json m_state;
    RewardsState m_rewards;
    CombatState m_combat;
    uint32_t m_actionRequest = 0;
    std::chrono::steady_clock::time_point m_fastBladeReady{};
    Json m_login;
    std::shared_ptr<Channel> m_lobby, m_zone, m_chat;
    LobbyCipher m_cipher;
    asio::steady_timer m_deadline, m_heartbeat, m_movement;
    uint32_t m_entity = 0;
    uint32_t m_inventoryContext = 0x40000000;
    std::string m_worldHost;
    uint16_t m_worldPort = 0;
    bool m_zoneAck = false, m_chatAck = false, m_haveZone = false, m_selfSpawn = false;
    std::array<Json, 30> m_quests{};
    std::array<float, 3> m_predicted{}, m_destination{};
    float m_speed = 2.0f;
    bool m_moving = false;
  };
}
