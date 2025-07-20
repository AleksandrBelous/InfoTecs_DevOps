from conan import ConanFile
from conan.tools.cmake import cmake_layout


class Task_8(ConanFile):
    name = "example"
    version = "0.1"
    settings = "os", "compiler", "build_type", "arch"
    requires = "fmt/10.2.1"
    generators = "CMakeDeps", "CMakeToolchain"

    def layout(self):
        cmake_layout(self)
