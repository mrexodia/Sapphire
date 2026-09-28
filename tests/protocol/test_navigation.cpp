#include "NavigationRoute.h"
#include <DetourNavMesh.h>
#include <DetourNavMeshBuilder.h>
#include <array>
#include <iostream>
#include <memory>
#include <stdexcept>

int main()
{
  try
  {
    // Two deliberately disconnected flat squares, independent of game assets/exporter.
    unsigned short vertices[] = {0,0,0, 0,0,10, 10,0,10, 10,0,0,
                                  30,0,0, 30,0,10, 40,0,10, 40,0,0};
    std::array<unsigned short, 24> polygons;
    polygons.fill(0xffff);
    for(int i = 0; i < 4; ++i) { polygons[i] = i; polygons[12+i] = 4+i; }
    unsigned short flags[] = {1, 1}; unsigned char areas[] = {0, 0};
    dtNavMeshCreateParams p{};
    p.verts = vertices; p.vertCount = 8; p.polys = polygons.data(); p.polyCount = 2;
    p.polyFlags = flags; p.polyAreas = areas; p.nvp = 6;
    p.bmax[0] = 40; p.bmax[1] = 2; p.bmax[2] = 10;
    p.cs = p.ch = 1; p.walkableHeight = 2; p.walkableRadius = 0.5f; p.walkableClimb = 0.6f;
    p.buildBvTree = true;
    unsigned char* data = nullptr; int size = 0;
    if(!dtCreateNavMeshData(&p, &data, &size)) throw std::runtime_error("synthetic mesh build failed");
    dtNavMesh mesh;
    if(dtStatusFailed(mesh.init(data, size, DT_TILE_FREE_DATA))) { dtFree(data); throw std::runtime_error("mesh init failed"); }
    auto route = Sapphire::Testing::navigationRoute(mesh, {1,0,1}, {9,0,9});
    if(route.size() < 3 || route.front()[0] != 1 || route.back()[0] != 9)
      throw std::runtime_error("connected route endpoints incorrect");
    for(const auto& point : route)
      if(point[0] < 0 || point[0] > 10 || point[2] < 0 || point[2] > 10 || point[1] != 0)
        throw std::runtime_error("route left the known walkable square");
    for(auto end : {Sapphire::Testing::Point{31,0,1}, Sapphire::Testing::Point{100,0,100}})
    {
      bool rejected = false;
      try { Sapphire::Testing::navigationRoute(mesh, {1,0,1}, end); }
      catch(const std::runtime_error&) { rejected = true; }
      if(!rejected) throw std::runtime_error("disconnected/off-mesh route was accepted");
    }
    std::cout << "Connected, disconnected and off-mesh route tests passed\n";
    return 0;
  }
  catch(const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
