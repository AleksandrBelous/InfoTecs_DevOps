cmake_minimum_required(VERSION 3.15)
project(sqlite_from_scratch C)

# ---------------------------------------------------------------------------
# 1. Общие исходники
# ---------------------------------------------------------------------------

# Варварно, но наглядно: кладём исходники в переменные
set(SQLITE_SOURCES sqlite3.c)
set(SHELL_SOURCES shell.c)

# ---------------------------------------------------------------------------
# 2. Linux-ветка
# ---------------------------------------------------------------------------

if(CMAKE_SYSTEM_NAME STREQUAL "Linux")

    # === Шаг 1. Собираем разделяемую библиотеку (`libsqlite3.so`) ===
    add_library(sqlite3 SHARED ${SQLITE_SOURCES})

    # Флаги: PIC нужен только для .so; остальные ключи подключаем через target_link_libraries
    target_compile_options(sqlite3 PRIVATE -fPIC)

    # Потоковая и прочие системные либы
    target_link_libraries(sqlite3 PRIVATE pthread dl m)

    # === Шаг 2. Собираем утилиту `sqlite3` ===
    add_executable(sqlite3_cli ${SHELL_SOURCES})

    # Линкуем *с* библиотекой, только если она получилаcь выше.
    # target_link_libraries игнорирует отсутствующие цели, но сообщим пользователю.
    if(TARGET sqlite3)

        # Говорим линковщику, где лежит наш .so
        target_link_libraries(sqlite3_cli PRIVATE sqlite3 pthread dl m)

        # RPATH="$ORIGIN" → во время запуска искать .so рядом с бинарём
        # Чтобы runtime искал .so рядом с бинарём
        set_target_properties(sqlite3_cli PROPERTIES INSTALL_RPATH "$ORIGIN")
    else()
        message(STATUS "libsqlite3.so не собиралась (не Linux) ─ линк только с системными библиотеками.")
    endif()

# ---------------------------------------------------------------------------
# 3. Windows + MSVC — только DLL
# ---------------------------------------------------------------------------

elseif(MSVC)
    message(STATUS "MSVC detected — building sqlite3.dll only")

    # 3.1 автоматически экспортировать ВСЕ глобальные символы, если забыли __declspec(dllexport)
    set(CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS ON)

    add_library(sqlite3 SHARED ${SQLITE_SOURCES})

    # 3.2 добавляем макро, чтобы публичные API-функции точно получили dllexport
    # add_definitions(-DSQLITE_API=__declspec(dllexport))
    # target_compile_definitions(sqlite3 PRIVATE "SQLITE_API=__declspec(dllexport)")

    # 3.3 собираем DLL
    # add_library(sqlite3 SHARED ${SQLITE_SOURCES})

    # ---- тестовый CLI ----
    add_executable(sqlite3_cli ${SHELL_SOURCES})
    if(TARGET sqlite3)
    # target_compile_definitions(sqlite3_cli PRIVATE _CRT_SECURE_NO_WARNINGS)
        target_link_libraries(sqlite3_cli PRIVATE sqlite3)
    else()
        message(STATUS "sqlite3.lib не собиралась.")
    endif()
endif()
