#include "Client.h"
#include <iostream>
#include <map>
#include <thread>

using namespace Sapphire::Testing;

int main()
{
  const uint16_t endian = 1;
  if(*reinterpret_cast<const uint8_t*>(&endian) != 1)
  {
    std::cerr << "This protocol profile requires a little-endian host.\n";
    return 2;
  }
  asio::io_service io;
  auto work = std::make_unique<asio::io_service::work>(io);
  std::map<std::string, std::shared_ptr<Bot>> bots;
  Emit emit = [](const Json& value) { std::cout << value.dump() << '\n' << std::flush; };
  std::thread thread([&] { io.run(); });
  std::string line;
  while(std::cin)
  {
    line.clear();
    char ch = 0;
    while(std::cin.get(ch) && ch != '\n')
    {
      if(line.size() == 65536) break;
      line += ch;
    }
    if(line.size() == 65536 && ch != '\n')
    { std::cerr << "Control request exceeds 64KiB.\n"; break; }
    if(line.empty() && !std::cin) break;
    io.post([&, line] {
      Json id = nullptr;
      try
      {
        const auto request = Json::parse(line);
        id = request.at("id");
        if(!id.is_number_unsigned()) throw ProtocolError("request id must be an unsigned integer");
        const auto method = request.at("method").get<std::string>();
        const auto args = request.value("args", Json::object());
        Json result = Json::object();
        if(method == "capabilities")
          result = {{"control_version", 1}, {"profile", "sapphire-3.3"}, {"scope", "loopback-only"},
            {"methods", {"login", "snapshot", "walk_to", "interact", "start_uldah_opening", "enter_uldah_opening_range", "discover_central_thanalan", "choose_scene", "sell_shop_item", "buy_shop_item", "buy_shop_equipment", "buy_shop_second_equipment", "buy_shop_third_equipment", "buy_shop_head_equipment", "buy_shop_ear_equipment", "buy_shop_neck_equipment", "buy_shop_wrist_equipment", "say", "development_place_registered", "tell", "tell_visible", "tell_remote", "tell_offline", "use_shop_vfx_item", "discard_item", "request_shop_item_equip", "request_currency_move_rejection", "request_item_move", "request_item_swap", "request_item_split", "request_item_merge", "return_homepoint", "cross_exit", "invite_party", "accept_party", "decline_party", "leave_party", "disband_party", "kick_party_member", "change_party_leader", "party_chat", "invite_party_bound", "accept_party_bound", "decline_party_bound", "party_chat_bound", "disband_party_bound", "cast_return", "sprint", "fast_blade", "savage_blade", "bootshine", "true_strike", "blizzard", "logout", "close", "remove"}},
            {"unsupported", {"compressed_frames", "scene_yield", "general_navigation", "general_combat"}}};
        else
        {
          const auto name = request.at("bot").get<std::string>();
          if(name.empty() || name.size() > 64) throw ProtocolError("bot name must be 1..64 bytes");
          if(method == "login")
          {
            if(bots.count(name) || bots.size() >= 64) throw ProtocolError("duplicate bot or worker bot limit exceeded");
            auto bot = std::make_shared<Bot>(io, name, emit);
            bots.emplace(name, bot);
            try { bot->login(args); }
            catch(...) { bot->close(); bots.erase(name); throw; }
          }
          else
          {
            auto found = bots.find(name);
            if(found == bots.end()) throw ProtocolError("unknown bot");
            if(method == "remove") { found->second->close(); bots.erase(found); }
            else result = found->second->command(method, args);
          }
        }
        emit({{"type", "response"}, {"id", id}, {"ok", true}, {"result", result}});
      }
      catch(const ProtocolError& e)
      {
        emit({{"type", "response"}, {"id", id}, {"ok", false}, {"error", {{"kind", "protocol"}, {"message", e.what()}}}});
      }
      catch(const std::exception&)
      {
        // JSON exceptions can contain sensitive input. Do not emit their what().
        emit({{"type", "response"}, {"id", id}, {"ok", false}, {"error", {{"kind", "invalid_request"}, {"message", "invalid command arguments"}}}});
      }
    });
  }
  io.post([&] { for(auto& entry : bots) entry.second->close(); bots.clear(); work.reset(); });
  thread.join();
  return 0;
}
