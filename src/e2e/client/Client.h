#pragma once
// The headless FFXIV 3.3 client: lobby and zone/chat connections, received-state
// bookkeeping and the narrow set of requests the scenarios send. Everything in
// here runs on the Asio thread; scenarios use the synchronous Bot facade.
#include "Protocol.h"
#include "RewardsState.h"
#include "CombatState.h"
#include "TransitionActions.h"
#include <asio.hpp>
#include <nlohmann/json.hpp>
#include <deque>
#include <chrono>
#include <functional>
#include <memory>
#include <optional>

namespace Sapphire::Testing
{
  using Json = nlohmann::json;
  using Emit = std::function<void(const Json&)>;
  using Point = std::array<float, 3>;

  class Channel : public std::enable_shared_from_this<Channel>
  {
  public:
    using Receive = std::function<void(Segment)>;
    Channel(asio::io_service& io, Receive receive, std::function<void(const std::string&)> error);
    void connect(const std::string& host, uint16_t port, std::function<void()> ready);
    void send(Bytes bytes, std::function<void()> complete = {});
    void close();
  private:
    struct Outbound
    {
      Bytes bytes;
      std::function<void()> complete;
    };
    void read();
    void write();
    void error(const std::string& reason);
    asio::ip::tcp::socket m_socket;
    Decoder m_decoder;
    std::array<uint8_t, 16384> m_input{};
    std::deque<Outbound> m_output;
    size_t m_queued = 0;
    bool m_closed = false;
    Receive m_receive;
    std::function<void(const std::string&)> m_error;
  };

  struct LoginOptions
  {
    std::string host;
    uint16_t port = 0;
    std::string session;
    std::string character;
    bool createCharacter = false;
    bool deleteCharacter = false;
    bool expectCharacterAbsent = false;
    bool expectNameRejected = false;
    uint8_t creationClass = 1;
    int timeoutSeconds = 30;
  };

  // Identity of a received scene the scenario answers; the token guards against
  // answering a scene that has since been replaced.
  struct SceneRef
  {
    uint32_t eventId = 0;
    uint32_t sceneId = 0;
    uint64_t token = 0;
  };

  enum class StarterAction : uint32_t
  {
    FastBlade = 9,
    SavageBlade = 11,
    Bootshine = 53,
    TrueStrike = 54,
    Blizzard = 142,
  };

  struct PartyChannel
  {
    uint64_t partyId = 0;
    uint64_t chatChannel = 0;
  };

  class Client : public std::enable_shared_from_this<Client>
  {
  public:
    Client(asio::io_service& io, std::string id, Emit emit);
    const std::string& id() const { return m_id; }

    // A copy of everything received so far (state, rewards, combat), plus
    // "moving" and the local pacing guard.
    Json snapshot() const;
    void close();
    void fail(const std::string& reason);

    void login(const LoginOptions& options);
    void logout();
    void walkTo(const Point& destination, float speed);
    void say(const std::string& message);
    void interact(uint32_t actorId, uint32_t eventId);
    void chooseScene(const SceneRef& scene, const std::vector<uint32_t>& results);

    void startUldahOpening();
    void enterOpeningRange(uint32_t eventId, uint32_t param, const Point& position);
    void leaveOpeningRange(uint32_t eventId, uint32_t param, const Point& position);
    void discoverCentralThanalan(uint32_t layoutId, uint32_t partId, const Point& receivedPosition);

    void sellShopItem(const SceneRef& scene, uint16_t storage, uint16_t slot, uint32_t itemId);
    void buyShopItem(const SceneRef& scene, uint32_t shopId, uint32_t itemId, uint32_t quantity);

    void inviteParty(uint32_t target, const std::string& name);
    void acceptParty();
    void declineParty();
    void leaveParty();
    void disbandParty();
    void kickPartyMember(uint32_t target, const std::string& name);
    void changePartyLeader(uint32_t target, const std::string& name);
    PartyChannel partyChat(const std::string& message);

    void tell(uint32_t target, const std::string& name, const std::string& message, bool expectOffline = false);
    void tellRemote(uint32_t target, const std::string& name, const std::string& message);
    void tellVisible(uint32_t target, const std::string& name, const std::string& message);

    // Combat and other actions return the request id the server echoes in its results.
    uint32_t castReturn();
    uint32_t sprint();
    uint32_t starterAction(StarterAction action, uint32_t target);
    uint32_t useShopVfxItem(uint32_t storage, uint32_t slot, uint32_t expectedCount);
    void returnHomepoint(unsigned deadlineSeconds = 30);
    void crossExit(const ExitRange& exit, unsigned deadlineSeconds = 30);

    // Inventory operations return the context id acknowledged by the server.
    uint32_t discardItem(uint32_t storage, uint32_t slot, uint32_t expectedItem);
    uint32_t unequipItem(uint32_t gearSlot, uint32_t expectedItem, uint32_t destinationStorage, uint32_t destinationSlot);
    uint32_t equipShopItem(uint32_t storage, uint32_t slot, uint32_t expectedItem, uint32_t gearSlot);
    uint32_t reequipStarterItem(uint32_t storage, uint32_t slot, uint32_t expectedItem, uint32_t gearSlot);
    uint32_t currencyMoveRejection(uint32_t expectedGil);
    uint32_t moveItem(uint32_t storage, uint32_t slot, uint32_t expectedItem,
                      uint32_t destinationStorage, uint32_t destinationSlot);
    uint32_t swapItem(uint32_t storage, uint32_t slot, uint32_t expectedItem,
                      uint32_t destinationStorage, uint32_t destinationSlot, uint32_t expectedDestinationItem);
    uint32_t splitItem(uint32_t storage, uint32_t slot, uint32_t expectedItem, uint32_t expectedCount,
                       uint32_t splitCount, uint32_t destinationStorage, uint32_t destinationSlot);
    uint32_t mergeItem(uint32_t storage, uint32_t slot, uint32_t expectedItem, uint32_t expectedCount,
                       uint32_t destinationStorage, uint32_t destinationSlot, uint32_t expectedDestinationCount);

  private:
    std::shared_ptr<Channel> channel(const std::string& name);
    void receive(const std::string& name, Segment segment);
    void lobbyPacket(Segment segment);
    void worldPacket(const std::string& name, Segment segment);
    void worldLogin();
    void heartbeat();
    void moveStep();
    void sendLobby(uint16_t opcode, const Bytes& payload);
    void sendZone(uint16_t opcode, const Bytes& payload, std::function<void()> complete = {});
    void sendChat(uint16_t opcode, const Bytes& payload);
    void event(const std::string& name, Json data = Json::object());
    void phase(const std::string& phase);
    void updateQuests();
    void requireReady() const;
    void requireIdle(const char* what) const;
    void requireScene(const SceneRef& scene) const;
    uint32_t nextInventoryContext();
    uint32_t nextActionRequest();
    void armDeadline(unsigned seconds, const char* reason);
    asio::io_service& m_io;
    std::string m_id;
    Emit m_emit;
    uint64_t m_seq = 0;
    Json m_state;
    RewardsState m_rewards;
    CombatState m_combat;
    uint32_t m_actionRequest = 0;
    std::chrono::steady_clock::time_point m_startingActionReady{}, m_fastBladeComboDeadline{};
    uint32_t m_fastBladeComboTarget = 0;
    LoginOptions m_login;
    bool m_loginActive = false;
    std::shared_ptr<Channel> m_lobby, m_zone, m_chat;
    LobbyCipher m_cipher;
    asio::steady_timer m_deadline, m_heartbeat, m_movement;
    uint32_t m_entity = 0;
    uint64_t m_creationCharacterId = 0;
    uint64_t m_serviceAccountId = 0;
    uint8_t m_serviceAccountIndex = 0;
    uint32_t m_inventoryContext = 0x40000000;
    std::string m_worldHost;
    uint16_t m_worldPort = 0;
    bool m_zoneAck = false, m_chatAck = false, m_haveZone = false, m_selfSpawn = false;
    std::array<Json, 30> m_quests{};
    Point m_predicted{}, m_destination{};
    float m_speed = 2.0f;
    bool m_moving = false;
  };
}
