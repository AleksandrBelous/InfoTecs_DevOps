Начнём с пунктов 1-3. Во-первых, разберёмся, как компилировать .so под Linux через gcc, т.к. это наша хостовая ОС.
Для начала посмотрим, как это можно делать вручную через терминал, без CMakeLists.
1. Создаём саму динамическую библиотеку:
- нужен файл объединения sqlite3.c
- ключи -fPIC для ...
- аргумент -shared, потому что у нас shared-библиотека
- ключи -lpthread -ldl -lm как в руководстве sqlite.org (-lpthread для подключения pthread, -ldl -lm)

gcc -fPIC -shared sqlite3.c -lpthread -ldl -lm -o libsqlite3.so

Получили libsqlite3.so

2. Далее его нужно привязать к CLI-интерфейсу:
- нужен shell.c для CLI
- ключ -L ./ ищет .so файл в текущей дирректории
- ключи -lpthread -ldl -lm как в руководстве sqlite.org

gcc shell.c -L ./ -lsqlite3 -lpthread -ldl -lm -o sqlite3

3. Получили бинарник sqlite3, проверим его работу

./sqlite3 -batch <<< "select sqlite_version();"

Получили ошибку: SQLite header and source version mismatch
                 2025-06-06 14:52:32 b77dc5e0f596d2140d9ac682b2893ff65d3a4140aa86067a3efebe29dc91alt1
                 2018-12-01 12:34:55 bf8c1b2b7a5960c282e543b9c293686dccff272512d08865f4600fb58238b4f9

Оказалось, что libsqlite3.so мы собрали из локального sqlite3.c 2018-го года,
а shell.c при компиляции нашёл системный в /usr/include/ версии 2025-06-06.
Они оказались разных годов и SQLite на старте падает с сообщением о mismatch.

Добавляем ключ -I ./ чтобы принудительно взять заголовок из текущей папки, проверяем

gcc -fPIC -shared sqlite3.c -lpthread -ldl -lm -o libsqlite3.so
gcc shell.c -I ./ -L ./ -lsqlite3 -lpthread -ldl -lm -o sqlite3
./sqlite3 -batch <<< "select sqlite_version();"

Результат: SQLite header and source version mismatch
           2025-06-06 14:52:32 b77dc5e0f596d2140d9ac682b2893ff65d3a4140aa86067a3efebe29dc91alt1
           2018-12-01 12:34:55 bf8c1b2b7a5960c282e543b9c293686dccff272512d08865f4600fb58238b4f9

Выявили новую проблему: -I ./ влияет только на поиск заголовков при компиляции.
Версию, с которой программа реально работает, определяет динамический загрузчик во время запуска.

Добавим -Wl,-rpath,'$ORIGIN', что говорит динамическому загрузчику искать .so в том же каталоге, где и бинарник.
При этом $ORIGIN подставляется загрузчиком на лету.

gcc -fPIC -shared sqlite3.c -lpthread -ldl -lm -o libsqlite3.so
gcc shell.c -I ./ -L ./ -lsqlite3 -lpthread -ldl -lm -Wl,-rpath,'$ORIGIN' -o sqlite3
./sqlite3 -batch <<< 'select sqlite_version();'

Результат: 3.26.0
Получилось. Теперь ещё одним способом проверим, что на этапе запуска линкуется именно наш собранный .so

ldd ./sqlite3 | grep libsqlite3.so
Результат: libsqlite3.so => /home/USER/InfoTecs/sqlite-amalgamation-3260000/./libsqlite3.so (0x00007fc771a8d000)

Наша библиотека подгружается, отлично.
Проверим работу sqlite3

printf 'select 2+2;' | ./sqlite3 -batch
Результат: 4

Работает корректно.

Далее подберём cmake команды, а также содержимое CMakeLists, таким образом, чтобы повторить опыт ручного терминала в cmake-скрипте.
Сохраним текущую дату и время, чтобы отразить в логах

ts=$(date +'%Y-%m-%d_%H-%M-%S')

Создадим build, если её ранее жёстко удалили (чтобы в будущем утилиты не ругались на отсутствие папки build)
mkdir -p build

Также подготовим папку для логов сборки на Линукс

mkdir -p logs_lin

Очистим мусор в build и Release, если он есть:

cmake --build build --target clean

Для верности ещё будем собирать cmake конфигурацию с аргументом --fresh, чтобы точно каждая сборка была новой:

cmake -S . -B build --fresh -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=Release --log-level=VERBOSE --log-context 2>&1 | tee "logs_lin/configure_$ts.log"

Здесь указываем источники для будущей работы брать из корневой папки . , а для Debug использовать папку build.
Также используем -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=Releas, чтобы подготовить конфигурацию сборки
к тому, что в итоге мы будем собирать Release пакет (чтобы задание имело логическое завершение)
через tee "logs_lin/configure_$ts.log" как выводим логи сборки конфигурации, так и сохраняем эти логи.

В самом CMakeLists пока указываем, где будет храниться релиз нашей сборки:

if(CMAKE_INSTALL_PREFIX_INITIALIZED_TO_DEFAULT)
    # По-умолчанию кладём ./Release/ рядом с CMakeLists.txt
    set(CMAKE_INSTALL_PREFIX "${CMAKE_SOURCE_DIR}/Release" CACHE PATH "" FORCE)
endif()

Также подготовим источники для либы и для бинарника:

set(SQLITE_SOURCES sqlite3.c)   # Общий файл библиотеки SQLite
set(SHELL_SOURCES  shell.c)     # Исходник консольного клиента

Далее хотим собрать динамическую библиотеку, подобрав аналог команды gcc -fPIC -shared sqlite3.c -lpthread -ldl -lm -o libsqlite3.so
Добавляем в CMakeLists проверку ОС, а также, первым этапом сборки, объект sqlite3 типа SHARED для динамической библиотеки,
а также все необходимые опции сборки этой библиотеки:

if(CMAKE_SYSTEM_NAME STREQUAL "Linux")

    # 2.1 Динамическая библиотека libsqlite3.so
    add_library(sqlite3 SHARED ${SQLITE_SOURCES})
    target_compile_options(sqlite3 PRIVATE -fPIC)        # Position-Independent Code
    target_link_libraries(sqlite3 PRIVATE pthread dl m)  # Системные либы

На cmake используем просто --build в ранее сконфигурированной папке build, а в качестве --target указываем подготовленный
в CMakeLists объект sqlite3:

cmake --build build --target sqlite3 VERBOSE=1 2>&1 | tee "logs_lin/build_$ts.log"

И, коечно, записываем логи первого этапа сборки.
Второй этап сборки - сам бинарник. Подбираем аналог команды: gcc shell.c -I ./ -L ./ -lsqlite3 -lpthread -ldl -lm -Wl,-rpath,'$ORIGIN' -o sqlite3
Для этого в CMakeLists используем отдельный объект sqlite3_cli, а также указываем явно,
что он линкуется с первым объектом sqlite3, а также то, где искать этот объект при релизе

# 2.2 Консольная утилита sqlite3_cli
    add_executable(sqlite3_cli ${SHELL_SOURCES})
    target_link_libraries(sqlite3_cli PRIVATE sqlite3 pthread dl m)
    # RPATH: во время запуска искать .so в ../lib относительно бинарника
    set_target_properties(sqlite3_cli PROPERTIES INSTALL_RPATH "$ORIGIN/../lib")

Аналогично первому этапу пишем собрать указанный в CMakeLists объект sqlite3_cli:

cmake --build build --target sqlite3_cli VERBOSE=1 2>&1 | tee -a "logs_lin/build_$ts.log"

Но логи второго этапа уже добавляем к логам первого с ключом -a.

Наконец, собираем релиз через:

cmake --build build --target install 2>&1 | tee "logs_lin/install_$ts.log"

подготовив разделения build и Release в CMakeLists:

install(TARGETS sqlite3            # .so
        LIBRARY DESTINATION lib    # .so

install(TARGETS sqlite3_cli
        RUNTIME DESTINATION bin)   # линукс-бинарь

Таким образом, мы проверили, как вручную собирать динамическую библиотеку на Линукс через gcc,
как линковать её с бинарником (в нашем случае это интерфейс CLI), ну и релиз собрали, чтобы как-то осмыслено было.
Далее подобрали cmake-команды, реализующие тот же результат, подготовив CMakeLists. Пока это только для линукс.

Теперь протестируем сборку динамической библиотеки на Windows

cl sqlite3.c -link -dll -out:sqlite3.dll

PS C:\Users\user\source\repos\AleksandrBelous\InfoTecs_DevOps\sqlite-amalgamation-3260000> cl sqlite3.c -link -dll -out:sqlite3.dll
Оптимизирующий компилятор Microsoft (R) C/C++ версии 19.44.35213 для x86
(C) Корпорация Майкрософт (Microsoft Corporation).  Все права защищены.

sqlite3.c
Microsoft (R) Incremental Linker Version 14.44.35213.0
Copyright (C) Microsoft Corporation.  All rights reserved.

/out:sqlite3.exe
-dll
-out:sqlite3.dll
sqlite3.obj

Получилось создать .dll, далее добавим .lib для будущей линковки с бинарником

cl /LD sqlite3.c /link /OUT:sqlite3.dll /IMPLIB:sqlite3.lib

C:\Users\user\source\repos\AleksandrBelous\InfoTecs_DevOps\sqlite-amalgamation-3260000>cl /LD sqlite3.c /link /OUT:sqlite3.dll /IMPLIB:sqlite3.lib
Оптимизирующий компилятор Microsoft (R) C/C++ версии 19.44.35213 для x86
(C) Корпорация Майкрософт (Microsoft Corporation).  Все права защищены.

sqlite3.c
Microsoft (R) Incremental Linker Version 14.44.35213.0
Copyright (C) Microsoft Corporation.  All rights reserved.

/out:sqlite3.dll
/dll
/implib:sqlite3.lib
/OUT:sqlite3.dll
/IMPLIB:sqlite3.lib
sqlite3.obj

Получилось создать .dll и .obj, но нет .lib
Попробуем так скомпилировать:

cl shell.c sqlite3.lib /Fe:sqlite3.exe

C:\Users\user\source\repos\AleksandrBelous\InfoTecs_DevOps\sqlite-amalgamation-3260000>cl shell.c sqlite3.lib /Fe:sqlite3.exe
Оптимизирующий компилятор Microsoft (R) C/C++ версии 19.44.35213 для x86
(C) Корпорация Майкрософт (Microsoft Corporation).  Все права защищены.

shell.c
Microsoft (R) Incremental Linker Version 14.44.35213.0
Copyright (C) Microsoft Corporation.  All rights reserved.

/out:sqlite3.exe
shell.obj
sqlite3.lib
LINK : fatal error LNK1181: не удается открыть входной файл "sqlite3.lib"

Не вышло. Пробуем:

cl /c sqlite3.c /DSQLITE_API=__declspec(dllexport)

C:\Users\user\source\repos\AleksandrBelous\InfoTecs_DevOps\sqlite-amalgamation-3260000>cl /c sqlite3.c /DSQLITE_API=__declspec(dllexport)
Оптимизирующий компилятор Microsoft (R) C/C++ версии 19.44.35213 для x86
(C) Корпорация Майкрософт (Microsoft Corporation).  Все права защищены.

sqlite3.c

link /DLL sqlite3.obj /OUT:sqlite3.dll /IMPLIB:sqlite3.lib

C:\Users\user\source\repos\AleksandrBelous\InfoTecs_DevOps\sqlite-amalgamation-3260000>link /DLL sqlite3.obj /OUT:sqlite3.dll /IMPLIB:sqlite3.lib
Microsoft (R) Incremental Linker Version 14.44.35213.0
Copyright (C) Microsoft Corporation.  All rights reserved.

   Создается библиотека sqlite3.lib и объект sqlite3.exp

Проверка

C:\Users\user\source\repos\AleksandrBelous\InfoTecs_DevOps\sqlite-amalgamation-3260000>dumpbin /exports sqlite3.dll | find "sqlite3_open"
        125   7C 00002EC0 sqlite3_open
        126   7D 00002EE0 sqlite3_open16
        127   7E 00002FD0 sqlite3_open_v2

Создадим бинарь:

C:\Users\user\source\repos\AleksandrBelous\InfoTecs_DevOps\sqlite-amalgamation-3260000>cl shell.c sqlite3.lib /Fe:sqlite3.exe
Оптимизирующий компилятор Microsoft (R) C/C++ версии 19.44.35213 для x86
(C) Корпорация Майкрософт (Microsoft Corporation).  Все права защищены.

shell.c
Microsoft (R) Incremental Linker Version 14.44.35213.0
Copyright (C) Microsoft Corporation.  All rights reserved.

/out:sqlite3.exe
shell.obj
sqlite3.lib

Проверка:

C:\Users\user\source\repos\AleksandrBelous\InfoTecs_DevOps\sqlite-amalgamation-3260000>sqlite3.exe -version
3.26.0 2018-12-01 12:34:55 bf8c1b2b7a5960c282e543b9c293686dccff272512d08865f4600fb58238b4f9

Теперь пробуем с CMakeLists

(а) генерация + конфигурация

файл CMakeLists уже содержит строки для подготовки конфигурации под линукс, написано в обощёном виде и подойдёт под винду

if(CMAKE_INSTALL_PREFIX_INITIALIZED_TO_DEFAULT)
    # По-умолчанию кладём ./Release/ рядом с CMakeLists.txt
    set(CMAKE_INSTALL_PREFIX "${CMAKE_SOURCE_DIR}/Release" CACHE PATH "" FORCE)
endif()
set(SQLITE_SOURCES sqlite3.c)   # Общий файл библиотеки SQLite
set(SHELL_SOURCES  shell.c)     # Исходник консольного клиента

Команду cmake пробуем ту, что ранее для Линукс работала

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=Release

C:\Users\user\source\repos\AleksandrBelous\InfoTecs_DevOps\sqlite-amalgamation-3260000>cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=Release
-- Building for: Visual Studio 17 2022
-- Selecting Windows SDK version 10.0.26100.0 to target Windows 10.0.19045.
-- The C compiler identification is MSVC 19.44.35213.0
-- Detecting C compiler ABI info
-- Detecting C compiler ABI info - done
-- Check for working C compiler: C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC/14.44.35207/bin/Hostx64/x64/cl.exe - skipped
-- Detecting C compile features
-- Detecting C compile features - done
-- MSVC detected — building sqlite3.dll only
-- Configuring done (2.9s)
-- Generating done (0.1s)
CMake Warning:
  Manually-specified variables were not used by the project:

    CMAKE_BUILD_TYPE


-- Build files have been written to: C:/Users/user/source/repos/AleksandrBelous/InfoTecs_DevOps/sqlite-amalgamation-3260000/build

(б) сборка библиотеки, чтобы в итоге чистая либа оказалась в Release.
Аналоги подбираем для: cl /c sqlite3.c /DSQLITE_API=__declspec(dllexport) и link /DLL sqlite3.obj /OUT:sqlite3.dll /IMPLIB:sqlite3.lib

elseif(MSVC)
    message(STATUS "MSVC detected — building sqlite3.dll")

    # Автоматически экспортировать все публичные символы (аналог __declspec(dllexport))
    set(CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS ON)

    add_library(sqlite3 SHARED ${SQLITE_SOURCES})

endif()

cmake --build build --target sqlite3 --config Release

C:\Users\user\source\repos\AleksandrBelous\InfoTecs_DevOps\sqlite-amalgamation-3260000>cmake --build build --target sqlite3 --config Release
CMake is re-running because C:/Users/user/source/repos/AleksandrBelous/InfoTecs_DevOps/sqlite-amalgamation-3260000/build/CMakeFiles/generate.stamp is out-of-date.
  the file 'C:/Users/user/source/repos/AleksandrBelous/InfoTecs_DevOps/sqlite-amalgamation-3260000/CMakeLists.txt'
  is newer than 'C:/Users/user/source/repos/AleksandrBelous/InfoTecs_DevOps/sqlite-amalgamation-3260000/build/CMakeFiles/generate.stamp.depend'
  result='-1'
-- Selecting Windows SDK version 10.0.26100.0 to target Windows 10.0.19045.
-- MSVC detected — building sqlite3.dll only
-- Configuring done (0.0s)
-- Generating done (0.2s)
-- Build files have been written to: C:/Users/user/source/repos/AleksandrBelous/InfoTecs_DevOps/sqlite-amalgamation-3260000/build
Версия MSBuild 17.14.14+a129329f1 для .NET Framework

  sqlite3.c
  Auto build dll exports
     Создается библиотека C:/Users/user/source/repos/AleksandrBelous/InfoTecs_DevOps/sqlite-amalgamation-3260000/build/Debug/sqlite3.lib и объект C:/Users/user/source/repos/AleksandrBelous/InfoTecs_DevOps/sqlite-amal
  gamation-3260000/build/Debug/sqlite3.exp
  sqlite3.vcxproj -> C:\Users\user\source\repos\AleksandrBelous\InfoTecs_DevOps\sqlite-amalgamation-3260000\build\Debug\sqlite3.dll

(в) сборка консольного клиента, чтобы тоже .exe в итоге оказался в Release
Аналог для: cl shell.c sqlite3.lib /Fe:sqlite3.exe

elseif(MSVC)
    message(STATUS "MSVC detected — building sqlite3.dll")

    # Автоматически экспортировать все публичные символы (аналог __declspec(dllexport))
    set(CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS ON)

    add_library(sqlite3 SHARED ${SQLITE_SOURCES})

    add_executable(sqlite3_cli ${SHELL_SOURCES})
    target_link_libraries(sqlite3_cli PRIVATE sqlite3)

endif()

cmake --build build --target sqlite3_cli --config Release

C:\Users\user\source\repos\AleksandrBelous\InfoTecs_DevOps\sqlite-amalgamation-3260000>cmake --build build --target sqlite3_cli --config Release
CMake is re-running because C:/Users/user/source/repos/AleksandrBelous/InfoTecs_DevOps/sqlite-amalgamation-3260000/build/CMakeFiles/generate.stamp is out-of-date.
  the file 'C:/Users/user/source/repos/AleksandrBelous/InfoTecs_DevOps/sqlite-amalgamation-3260000/CMakeLists.txt'
  is newer than 'C:/Users/user/source/repos/AleksandrBelous/InfoTecs_DevOps/sqlite-amalgamation-3260000/build/CMakeFiles/generate.stamp.depend'
  result='-1'
-- Selecting Windows SDK version 10.0.26100.0 to target Windows 10.0.19045.
-- MSVC detected — building sqlite3.dll only
-- Configuring done (0.1s)
-- Generating done (0.8s)
-- Build files have been written to: C:/Users/user/source/repos/AleksandrBelous/InfoTecs_DevOps/sqlite-amalgamation-3260000/build
Версия MSBuild 17.14.14+a129329f1 для .NET Framework

  sqlite3.c
  Auto build dll exports
     Создается библиотека C:/Users/user/source/repos/AleksandrBelous/InfoTecs_DevOps/sqlite-amalgamation-3260000/build/Debug/sqlite3.lib и объект C:/Users/user/source/repos/AleksandrBelous/InfoTecs_DevOps/sqlite-amal
  gamation-3260000/build/Debug/sqlite3.exp
  sqlite3.vcxproj -> C:\Users\user\source\repos\AleksandrBelous\InfoTecs_DevOps\sqlite-amalgamation-3260000\build\Debug\sqlite3.dll
  Building Custom Rule C:/Users/user/source/repos/AleksandrBelous/InfoTecs_DevOps/sqlite-amalgamation-3260000/CMakeLists.txt
  shell.c
  sqlite3_cli.vcxproj -> C:\Users\user\source\repos\AleksandrBelous\InfoTecs_DevOps\sqlite-amalgamation-3260000\build\Debug\sqlite3_cli.exe

Проверяем, что собралось:

C:\Users\user\source\repos\AleksandrBelous\InfoTecs_DevOps\sqlite-amalgamation-3260000>.\build\Release\sqlite3_cli.exe -version
3.26.0 2018-12-01 12:34:55 bf8c1b2b7a5960c282e543b9c293686dccff272512d08865f4600fb58238b4f9

Отлично, для CMakeLists, для сборки, вроде отшлифовали команды, но отдельной папки Release с бинарником и либой в одном месте по прежнему нет.
Для этого нужно выбрать режим --install после тестирования всех сборок. Запустим:

(г) cmake --install build --config Release

C:\Users\user\source\repos\AleksandrBelous\InfoTecs_DevOps\sqlite-amalgamation-3260000>cmake --install build --config Release
-- Installing: C:/Users/user/source/repos/AleksandrBelous/InfoTecs_DevOps/sqlite-amalgamation-3260000/Release/lib/sqlite3.lib
-- Installing: C:/Users/user/source/repos/AleksandrBelous/InfoTecs_DevOps/sqlite-amalgamation-3260000/Release/bin/sqlite3.dll
-- Installing: C:/Users/user/source/repos/AleksandrBelous/InfoTecs_DevOps/sqlite-amalgamation-3260000/Release/bin/sqlite3_cli.exe

В одном из тестов собирали конфигурацию и либу с бинарём с разными аргументами Debug \ Release, получили ошибку:

C:\Users\user\source\repos\AleksandrBelous\InfoTecs_DevOps\sqlite-amalgamation-3260000>cmake --install build --config Release
CMake Error at build/cmake_install.cmake:51 (file):
  file INSTALL cannot find
  "C:/Users/user/source/repos/AleksandrBelous/InfoTecs_DevOps/sqlite-amalgamation-3260000/build/Release/sqlite3.dll":
  File exists.

потому что запускали до этого

cmake --build build --target sqlite3
cmake --build build --target sqlite3_cli

без --config Release. В итоге собрался Debug‑вариант, поэтому библиотеки и exe легли в build\Debug\
Затем мы попытались установить Release‑конфигурацию:

cmake --install build --config Release

Скрипт cmake_install.cmake ищет файл build\Release\sqlite3.dll — его нет, поэтому CMake выдавал ошибку:

file INSTALL cannot find ".../Release/sqlite3.dll": File exists.

Но мы это исправили, как можно видеть выше.
Добавим в CMakeLists строки для билда и релиза на винде:

install(TARGETS sqlite3            # .so или .dll (+.lib/.exp)
        RUNTIME DESTINATION bin    # dll-загрузчик под Windows
        LIBRARY DESTINATION lib    # .so
        ARCHIVE DESTINATION lib)   # .lib/.exp

install(TARGETS sqlite3_cli
        RUNTIME DESTINATION bin)   # .exe / Linux-бинарь

Таким образом, протестировали, как на Windows через MSVC собрать динамическую библиотеку, а потом
привязать её к бинарному файлу. Далее подобрали аналогичные cmake команды, а также подготовили CMakeLists
для аккуратной сборки проекта в build и отдельного релиза библиотеки и исполняемого файла в Release.

Следующая задача - завернуть отработанный функционал (только линукс) в docker-контейнер.
Создадим Dockerfile и .dockerignore. В Dockerfile нам нужно скачать легковесный образ Linux, установить нужные утилиты,
далее скопировать внутрь контейнера исходники для сборки динамической библиотеки и бинарника CLI, а также CMakeLists
для автоатической сборки либы и бинаря. При этом в .dockerignore укажем сами файлы .dockerignore и Dockerfile, а также
папки логов сборки на линуксе и винде, папки build и Release, чтобы они не тянулись внутрь контейнера.