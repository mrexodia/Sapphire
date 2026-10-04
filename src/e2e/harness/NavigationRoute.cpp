#include "NavigationRoute.h"
#include <DetourNavMesh.h>
#include <DetourNavMeshQuery.h>
#include <cmath>
#include <stdexcept>
#include <algorithm>

namespace Sapphire::Testing
{
  static float distance(const Point& a, const Point& b)
  {
    float d = 0;
    for(size_t i = 0; i < 3; ++i) d += (a[i]-b[i]) * (a[i]-b[i]);
    return std::sqrt(d);
  }
  std::vector<Point> navigationRoute(const dtNavMesh& mesh, const Point& start, const Point& end)
  {
    for(auto p : {start, end})
      for(float coordinate : p)
        if(!std::isfinite(coordinate)) throw std::runtime_error("nonfinite route endpoint");
    dtNavMeshQuery query;
    if(dtStatusFailed(query.init(&mesh, 4096))) throw std::runtime_error("cannot initialize navigation query");
    dtQueryFilter filter;
    filter.setIncludeFlags(0xffff);
    // NPCs can stand on a decorative/disconnected polygon. Choose an approach
    // polygon within interaction distance, never broaden to an arbitrary remote endpoint.
    auto approaches = [&](const Point& point) {
      std::vector<std::pair<dtPolyRef, Point>> candidates;
      std::array<dtPolyRef, 128> refs{};
      int count = 0;
      const float extents[3] = {2, 1.5f, 2};
      auto status = query.queryPolygons(point.data(), extents, &filter, refs.data(), &count, refs.size());
      if(dtStatusFailed(status) || dtStatusDetail(status, DT_BUFFER_TOO_SMALL))
        throw std::runtime_error("cannot enumerate endpoint approach polygons");
      for(int i = 0; i < count; ++i)
      {
        Point surface{};
        if(dtStatusSucceed(query.closestPointOnPoly(refs[i], point.data(), surface.data(), nullptr)) &&
           distance(point, surface) <= 2 && std::abs(point[1]-surface[1]) <= 1.0f)
          candidates.emplace_back(refs[i], surface);
      }
      std::sort(candidates.begin(), candidates.end(), [&](const auto& a, const auto& b) {
        return distance(a.second, point) < distance(b.second, point);
      });
      if(candidates.size() > 16) candidates.resize(16);
      return candidates;
    };
    const auto starts = approaches(start), ends = approaches(end);
    if(starts.empty() || ends.empty()) throw std::runtime_error("no walkable polygon within endpoint interaction range");
    constexpr int Max = 2048;
    std::array<dtPolyRef, Max> corridor{};
    int count = 0;
    Point from{}, to{};
    bool connected = false;
    for(const auto& a : starts)
    {
      for(const auto& b : ends)
      {
        auto status = query.findPath(a.first, b.first, a.second.data(), b.second.data(), &filter, corridor.data(), &count, Max);
        if(dtStatusSucceed(status) && !dtStatusDetail(status, DT_PARTIAL_RESULT | DT_BUFFER_TOO_SMALL | DT_OUT_OF_NODES) &&
           count > 0 && corridor[count-1] == b.first)
        { from = a.second; to = b.second; connected = true; break; }
      }
      if(connected) break;
    }
    if(!connected) throw std::runtime_error("incomplete navigation corridor");
    std::array<float, Max * 3> straight{};
    std::array<unsigned char, Max> flags{};
    std::array<dtPolyRef, Max> refs{};
    int corners = 0;
    auto status = query.findStraightPath(from.data(), to.data(), corridor.data(), count, straight.data(), flags.data(),
                                   refs.data(), &corners, Max, DT_STRAIGHTPATH_ALL_CROSSINGS);
    if(dtStatusFailed(status) || dtStatusDetail(status, DT_BUFFER_TOO_SMALL) || !corners ||
       !(flags[corners-1] & DT_STRAIGHTPATH_END)) throw std::runtime_error("incomplete navigation funnel");
    std::vector<Point> result{from};
    for(int i = 0; i + 1 < corners; ++i)
    {
      if((flags[i] | flags[i+1]) & DT_STRAIGHTPATH_OFFMESH_CONNECTION)
        throw std::runtime_error("route requires an unsupported off-mesh transition");
      Point x{straight[i*3], straight[i*3+1], straight[i*3+2]};
      Point y{straight[(i+1)*3], straight[(i+1)*3+1], straight[(i+1)*3+2]};
      int steps = std::max(1, static_cast<int>(std::ceil(distance(x, y) / 0.5f)));
      for(int step = 1; step <= steps; ++step)
      {
        Point sample{}, surface{};
        for(size_t k = 0; k < 3; ++k) sample[k] = x[k] + (y[k]-x[k]) * (static_cast<float>(step)/steps);
        bool over = false;
        status = query.closestPointOnPoly(refs[i], sample.data(), surface.data(), &over);
        if(dtStatusFailed(status) || std::hypot(surface[0]-sample[0], surface[2]-sample[2]) > 0.1f ||
           distance(result.back(), surface) > 1.5f)
          throw std::runtime_error("navigation surface projection is discontinuous");
        if(result.size() >= 2048) throw std::runtime_error("route exceeds supported waypoint budget");
        if(distance(result.back(), surface) > 0.001f) result.push_back(surface);
      }
    }
    if(distance(result.back(), to) > 0.1f) throw std::runtime_error("route does not reach destination");
    return result;
  }
}
