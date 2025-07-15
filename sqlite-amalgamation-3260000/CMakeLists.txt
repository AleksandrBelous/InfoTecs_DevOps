cmake_minimum_required(VERSION 3.15)
project(sqlite_from_scratch C)

# Варварно, но наглядно: кладём исходники в переменные
set(SQLITE_SOURCES sqlite3.c)
set(SHELL_SOURCES shell.c)

# === Шаг 1. Собираем разделяемую библиотеку (`libsqlite3.so`) ===
add_library(sqlite3 SHARED ${SQLITE_SOURCES})

# Флаги: PIC нужен только для .so; остальные ключи подключаем через target_link_libraries
target_compile_options(sqlite3 PRIVATE -fPIC)

# Потоковая и прочие системные либы
target_link_libraries(sqlite3 PRIVATE pthread dl m)

# === Шаг 2. Собираем утилиту `sqlite3` ===
add_executable(sqlite3_cli ${SHELL_SOURCES})

# Говорим линковщику, где лежит наша .so
target_link_libraries(sqlite3_cli PRIVATE sqlite3 pthread dl m)

# Чтобы runtime искал .so рядом с бинарём
set_target_properties(sqlite3_cli PROPERTIES INSTALL_RPATH "$ORIGIN")
