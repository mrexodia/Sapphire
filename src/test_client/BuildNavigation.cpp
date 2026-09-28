// Regenerate a local test asset using the existing exporter, never overwriting input assets.
#include <nav/TiledNavmeshGenerator.h>
#include <filesystem>
#include <iostream>
#include <regex>

int main(int argc, char** argv)
{
  namespace fs = std::filesystem;
  if(argc != 4)
  {
    std::cerr << "Usage: sapphire_test_navbuild <collision.obj> <new-output-directory> <zone-name>\n";
    return 2;
  }
  try
  {
    auto input = fs::absolute(argv[1]);
    auto output = fs::absolute(argv[2]);
    const std::string zone = argv[3];
    if(!fs::is_regular_file(input) || !std::regex_match(zone, std::regex("[a-z0-9_]{1,32}")))
      throw std::runtime_error("invalid input file or zone name");
    if(fs::exists(output)) throw std::runtime_error("output directory already exists; refusing to overwrite");
    fs::create_directories(output);
    fs::current_path(output);
    auto directory = output / "navi" / zone;
    fs::create_directories(directory);
    auto collision = directory / (zone + ".obj");
    fs::copy_file(input, collision);
    TiledNavmeshGenerator generator;
    if(!generator.init(collision.string(), 1) || !generator.buildTiledCache())
      throw std::runtime_error("navigation generation failed");
    generator.saveNavmesh(zone);
    auto mesh = output / "navi" / zone / (zone + ".nav");
    if(!fs::is_regular_file(mesh) || fs::file_size(mesh) < 100)
      throw std::runtime_error("navigation output missing or empty");
    std::cout << "Generated isolated test navigation: " << mesh << '\n';
    return 0;
  }
  catch(const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
