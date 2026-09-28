#include "CreationActions.h"
#include <nlohmann/json.hpp>

namespace Sapphire::Testing
{
  std::string canonicalUldahCreationPayload(uint8_t classJob)
  {
    if(classJob != 1 && classJob != 2 && classJob != 7)
      throw ProtocolError("creation supports only the three source-defined Ul'dah starting classes");
    nlohmann::json look = {"1","0","1","50","1","1","1","1","0","0","0","1","1",
                           "1","1","1","1","1","0","0","0","0","0","0","0","0"};
    nlohmann::json content = nlohmann::json::array({look, "1", "1", "1", "1",
                                                     std::to_string(classJob), "1"});
    return nlohmann::json({{"content", content}}).dump();
  }
}
