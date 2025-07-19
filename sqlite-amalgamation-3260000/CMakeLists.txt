cmake_minimum_required(VERSION 3.15)
project(sqlite_from_scratch C)

# ---------------------------------------------------------------------------
# 0.  Определяем, куда складывать ./Release/
# ---------------------------------------------------------------------------
if(CMAKE_INSTALL_PREFIX_INITIALIZED_TO_DEFAULT)
    # По-умолчанию кладём ./Release/ рядом с CMakeLists.txt
    set(CMAKE_INSTALL_PREFIX "${CMAKE_SOURCE_DIR}/Release" CACHE PATH "" FORCE)
endif()

# ---------------------------------------------------------------------------
# 1.  Общие исходники из архива
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

    # RPATH: во время запуска искать .so в ../lib относительно бинарника
    set_target_properties(sqlite3_cli PROPERTIES
        INSTALL_RPATH "$ORIGIN/../lib")

# ---------------------------------------------------------------------------
# 3.  Ветка Windows + MSVC
# ---------------------------------------------------------------------------
elseif(MSVC)
    message(STATUS "MSVC detected — building sqlite3.dll")

    # Автоматически экспортировать все публичные символы (аналог __declspec(dllexport))
    set(CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS ON)

    add_library(sqlite3 SHARED ${SQLITE_SOURCES})

    add_executable(sqlite3_cli ${SHELL_SOURCES})
    target_link_libraries(sqlite3_cli PRIVATE sqlite3)

endif()

# ---------------------------------------------------------------------------
# 4.  Унифицированные правила разделения ./build/ и ./Release/
# ---------------------------------------------------------------------------
install(TARGETS sqlite3            # .so или .dll (+.lib/.exp)
        RUNTIME DESTINATION bin    # dll-загрузчик под Windows
        LIBRARY DESTINATION lib    # .so
        ARCHIVE DESTINATION lib)   # .lib/.exp

install(TARGETS sqlite3_cli
        RUNTIME DESTINATION bin)   # .exe / Linux-бинарь

# ---------------------------------------------------------------------------
# 5.  Памятка по сборке
# ---------------------------------------------------------------------------
#
# Linux:
#   ts=$(date +'%Y-%m-%d_%H-%M-%S')
#   mkdir -p build
#   mkdir -p logs_lin
#   cmake --build build --target clean
#   cmake -S . -B build --fresh -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=Release --log-level=VERBOSE --log-context 2>&1 | tee "logs_lin/configure_$ts.log"
#   cmake --build build --target sqlite3 VERBOSE=1 2>&1 | tee "logs_lin/build_$ts.log"
#   cmake --build build --target sqlite3_cli VERBOSE=1 2>&1 | tee -a "logs_lin/build_$ts.log"
#   cmake --build build --target install 2>&1 | tee "logs_lin/install_$ts.log"
#
# Windows:
#   for /f "delims=" %i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm-ss"') do set ts=%i
#   if not exist build mkdir build
#   if not exist logs_win mkdir logs_win
#   cmake --build build --target clean --config Debug
#   cmake --build build --target clean --config Release
#   cmake -S . -B build --fresh -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=Release --log-level=VERBOSE --log-context > "logs_win\configure_%ts%.log" 2>&1
#   cmake --build build --target sqlite3 --config Release --verbose > "logs_win\build_%ts%.log" 2>&1
#   cmake --build build --target sqlite3_cli --config Release --verbose >> "logs_win\build_%ts%.log" 2>&1
#   cmake --install build --config Release > "logs_win\install_%ts%.log" 2>&1
#
# Готовые файлы окажутся в:
#   Release/bin/sqlite3_cli[.exe], Release/bin/sqlite3.dll, Release/lib/libsqlite3.[so|lib]
