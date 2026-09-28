#pragma once
#include <array>
#include <vector>
class dtNavMesh;
namespace Sapphire::Testing
{
  using Point = std::array<float, 3>;
  // Full corridor only; no partial paths, off-mesh links, or straight-line fallback.
  std::vector<Point> navigationRoute(const dtNavMesh& mesh, const Point& start, const Point& end);
}
