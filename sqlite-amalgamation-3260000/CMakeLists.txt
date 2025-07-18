cmake_minimum_required(VERSION 3.15)
project(sqlite_from_scratch C)

# ---------------------------------------------------------------------------
# 0.  Куда ставить «готовый релиз» (можно переопределить -DCMAKE_INSTALL_PREFIX)
# ---------------------------------------------------------------------------
if(CMAKE_INSTALL_PREFIX_INITIALIZED_TO_DEFAULT)
    # По-умолчанию кладём подкаталог Release/ рядом с CMakeLists.txt
    set(CMAKE_INSTALL_PREFIX "${CMAKE_SOURCE_DIR}/Release" CACHE PATH "" FORCE)
endif()

# ---------------------------------------------------------------------------
# 1.  Общие исходники
# ---------------------------------------------------------------------------
set(SQLITE_SOURCES sqlite3.c)   # Амальгамированная SQLite
set(SHELL_SOURCES  shell.c)     # Исходник консольного клиента

# ---------------------------------------------------------------------------
# 2.  Ветка Linux
# ---------------------------------------------------------------------------
if(CMAKE_SYSTEM_NAME STREQUAL "Linux")

    # 2.1 Динамическая библиотека libsqlite3.so
    add_library(sqlite3 SHARED ${SQLITE_SOURCES})
    target_compile_options(sqlite3 PRIVATE -fPIC)        # Position-Independent Code
    target_link_libraries(sqlite3 PRIVATE pthread dl m)  # Системные либы

    # 2.2 Консольная утилита sqlite3_cli
    add_executable(sqlite3_cli ${SHELL_SOURCES})
    target_link_libraries(sqlite3_cli PRIVATE sqlite3 pthread dl m)

    # RPATH: во время запуска искать .so в ../lib относительно бинаря
    set_target_properties(sqlite3_cli PROPERTIES
        INSTALL_RPATH "$ORIGIN/../lib")

# ---------------------------------------------------------------------------
# 3.  Ветка Windows + MSVC
# ---------------------------------------------------------------------------
elseif(MSVC)
    message(STATUS "MSVC detected — building sqlite3.dll")

    # Автоматически экспортировать все публичные символы, если нет __declspec(dllexport)
    set(CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS ON)

    add_library(sqlite3 SHARED ${SQLITE_SOURCES})
    add_executable(sqlite3_cli ${SHELL_SOURCES})
    target_link_libraries(sqlite3_cli PRIVATE sqlite3)

    # На Windows загрузчик ищет .dll сначала рядом с .exe, затем в PATH.
    # sqlite3_cli.exe и sqlite3.dll мы кладём в один каталог bin/ (см. install ниже).
endif()

# ---------------------------------------------------------------------------
# 4.  Унифицированные правила «куда ставить»
# ---------------------------------------------------------------------------
install(TARGETS sqlite3            # .so или .dll (+.lib/.exp)
        RUNTIME DESTINATION bin    # dll-загрузчик под Win
        LIBRARY DESTINATION lib    # .so
        ARCHIVE DESTINATION lib)   # .a / .lib (если захотите статику)

install(TARGETS sqlite3_cli
        RUNTIME DESTINATION bin)   # .exe / Linux-бинарь

# ---------------------------------------------------------------------------
# 5.  Памятка по сборке  (не исполняется, просто для справки)
# ---------------------------------------------------------------------------
# Linux:
#   cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=Release
#   cmake --build build --target install -j$(nproc)
#
# Windows (PowerShell):
#   cmake -S . -B build -G "Visual Studio 17 2022" -A x64 -DCMAKE_INSTALL_PREFIX=Release
#   cmake --build build --config Release --target install
#
# Готовые файлы окажутся в:
#   Release/bin/sqlite3_cli[.exe], Release/bin/sqlite3.dll, Release/lib/libsqlite3.so
