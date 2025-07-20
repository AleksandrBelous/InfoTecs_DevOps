cmake_minimum_required(VERSION 3.15)
project(Task_8)

# Conan 2.x автоматически ищет зависимости через find_package()
find_package(fmt REQUIRED)

add_executable(main ../main.cpp)
target_link_libraries(main fmt::fmt)
