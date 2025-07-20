from conan import ConanFile
from conan.tools.cmake import CMake, cmake_layout

class ExampleConan(ConanFile):
    name = "example"
    version = "0.1"
    settings = "os", "compiler", "build_type", "arch"
    requires = "fmt/10.2.1"
    generators = "CMakeDeps", "CMakeToolchain"

    def layout(self):
        cmake_layout(self)

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()
