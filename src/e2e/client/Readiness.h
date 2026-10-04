#pragma once
// Combat readiness checks over received state. They mirror the real client's
// own gating before it sends an action: the local pacing guard, received
// resources and the estimated range from the predicted position to the target.
// Nothing here sends or retries; a scenario waits until a check holds.
//
// Inconsistent state (a GM, the wrong class, a dead fighter, a missing guard)
// is a scenario error, not "not ready yet", and throws ReadinessError.
#include <cstdint>
#include <nlohmann/json.hpp>
#include <stdexcept>

namespace Sapphire::Testing
{
  struct ReadinessError : std::invalid_argument { using std::invalid_argument::invalid_argument; };

  // Sprint: idle, living player, pacing guard elapsed, at least 50 TP.
  bool sprintReady( const nlohmann::json& state );

  // A starting-class action against an observed enemy: 9 Fast Blade, 11 Savage
  // Blade (needs level 4 and the received Fast Blade combo marker), 53 Bootshine,
  // 54 True Strike (level 2, 50 TP) and 142 Blizzard (Thaumaturge, 4 MP, 24.5m).
  bool actionReady( const nlohmann::json& state, uint32_t action, uint32_t target );

  // Damage an effect row carries: the plain (flag 0) damage entries of type 3 and 5.
  uint32_t damageValue( const nlohmann::json& effect );

  // The identical effect is in the state and an integrity row commits exactly
  // targetBefore.hp - damage for the same target and result id.
  bool committedDamage( const nlohmann::json& state, const nlohmann::json& effect, const nlohmann::json& targetBefore );
}
