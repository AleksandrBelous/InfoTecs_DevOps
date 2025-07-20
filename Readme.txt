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
для автоатической сборки либы и бинаря.
При этом в .dockerignore укажем сами файлы .dockerignore и Dockerfile, а также папки логов сборки на линуксе и винде,
папки build и Release, чтобы они не тянулись внутрь контейнера.
При отладе Dockerfile возникли проблемы с потерей переменных при между запусками разных команд -
это происходит потому, что каждая команда запускается в собственной сессии.
Мы хотим хранить логи с указанием даты - поэтому в Dockerfile команды объеденены в большой однострочник
с логическим разделением через ;
Также добавили set -eux; , чтобы иметь возможность пробрасывать все команды в терминал хоста на период
построения контейнера и отлаживаться по каждой команде в составе однострочника.
В итоге Dockerfile собирает легковесный debian-образ и компилирует утилиту sqlite_cli с динамической либой.
Всё находится в /src/Release.
Для сборки докера необходимо, находясь в паке с Dockerfile, выполнить:

docker build -t my-sqlite .

Для запуска выполнить:

docker run --rm -it my-sqlite:latest

попав таким образом в bash-сессию, можно запускать sqlite_cli:

root@bdda32ffd050:/src# ./Release/bin/sqlite3_cli
SQLite version 3.26.0 2018-12-01 12:34:55
Enter ".help" for usage hints.
Connected to a transient in-memory database.
Use ".open FILENAME" to reopen on a persistent database.
sqlite> select sqlite_version();
3.26.0
sqlite> .exit
root@bdda32ffd050:/src# ldd ./Release/bin/sqlite3_cli | grep libsqlite3.so
        libsqlite3.so => /src/./Release/bin/../lib/libsqlite3.so (0x00007fb72337f000)
root@bdda32ffd050:/src#

Выполняем далее 5 пункт - через vagrant поднимем машину в среде VB.

vagrant init debian/bookworm64

создали файл Vagrantfile с базовым наполнением (закомментированным) для поднятия машины debian/bookworm64. Также указали
для начала просто размер оперативки и число cpus.
Попытались тестово поднять vagrant up --provider=virtualbox, но без указания типа сети (сетевой интерфейс vboxnet0,
как оказалось, нужно было ещё создать) пошла ошибка:

Bringing machine 'default' up with 'virtualbox' provider...
There was an error while executing `VBoxManage`, a CLI used by Vagrant
for controlling VirtualBox. The command and stderr is shown below.

Command: ["list", "hostonlyifs"]

Stderr: VBoxManage: error: Code NS_ERROR_FAILURE (0x80004005) - Operation failed (extended info not available)
VBoxManage: error: Context: "FindHostNetworkInterfacesOfType(HostNetworkInterfaceType_HostOnly, ComSafeArrayAsOutParam(hostNetworkInterfaces))" at line 148 of file VBoxManageList.cpp

Создали интерфейс sudo VBoxManage hostonlyif create
                  0%...10%...20%...30%...40%...50%...60%...70%...80%...90%...100%
                  Interface 'vboxnet0' was successfully created

Также выбрали в Vagrantfile сеть:

config.vm.network "private_network", ip: "192.168.56.10"

Наконец удалось поднять машину:

Bringing machine 'default' up with 'virtualbox' provider...
==> default: Box 'debian/bookworm64' could not be found. Attempting to find and install...
    default: Box Provider: virtualbox
    default: Box Version: >= 0
==> default: Loading metadata for box 'debian/bookworm64'
    default: URL: https://vagrantcloud.com/api/v2/vagrant/debian/bookworm64
==> default: Adding box 'debian/bookworm64' (v12.20250126.1) for provider: virtualbox (amd64)
    default: Downloading: https://vagrantcloud.com/debian/boxes/bookworm64/versions/12.20250126.1/providers/virtualbox/amd64/vagrant.box
Progress: 8% (Rate: 106k/s, Estimated time remaining: 0:44:11)

далее идут логи запуска:

Bringing machine 'default' up with 'virtualbox' provider...
==> default: Importing base box 'debian/bookworm64'...
==> default: Matching MAC address for NAT networking...
==> default: Setting the name of the VM: InfoTecs_default_1752947396575_20707
Vagrant is currently configured to create VirtualBox synced folders with
the `SharedFoldersEnableSymlinksCreate` option enabled. If the Vagrant
guest is not trusted, you may want to disable this option. For more
information on this option, please refer to the VirtualBox manual:

  https://www.virtualbox.org/manual/ch04.html#sharedfolders

This option can be disabled globally with an environment variable:

  VAGRANT_DISABLE_VBOXSYMLINKCREATE=1

or on a per folder basis within the Vagrantfile:

  config.vm.synced_folder '/host/path', '/guest/path', SharedFoldersEnableSymlinksCreate: false
==> default: Clearing any previously set network interfaces...
==> default: Preparing network interfaces based on configuration...
    default: Adapter 1: nat
    default: Adapter 2: hostonly
==> default: Forwarding ports...
    default: 22 (guest) => 2222 (host) (adapter 1)
==> default: Running 'pre-boot' VM customizations...
==> default: Booting VM...
==> default: Waiting for machine to boot. This may take a few minutes...
    default: SSH address: 127.0.0.1:2222
    default: SSH username: vagrant
    default: SSH auth method: private key
    default:
    default: Vagrant insecure key detected. Vagrant will automatically replace
    default: this with a newly generated keypair for better security.
    default:
    default: Inserting generated public key within guest...
    default: Removing insecure key from the guest if it's present...
    default: Key inserted! Disconnecting and reconnecting using new SSH key...
==> default: Machine booted and ready!
[default] A Virtualbox Guest Additions installation was found but no tools to rebuild or start them.
Reading package lists...
Building dependency tree...
Reading state information...
E: Unable to locate package linux-headers-6.1.0-29-amd64
E: Couldn't find any package by glob 'linux-headers-6.1.0-29-amd64'
E: Couldn't find any package by regex 'linux-headers-6.1.0-29-amd64'
E: Unable to locate package build-essential
Get:1 https://deb.debian.org/debian bookworm InRelease [151 kB]
Get:2 https://security.debian.org/debian-security bookworm-security InRelease [48.0 kB]
Get:3 https://security.debian.org/debian-security bookworm-security/main Sources [142 kB]
Get:4 https://deb.debian.org/debian bookworm-updates InRelease [55.4 kB]
Get:5 https://security.debian.org/debian-security bookworm-security/main amd64 Packages [272 kB]
Get:6 https://deb.debian.org/debian bookworm-backports InRelease [59.4 kB]
Get:7 https://deb.debian.org/debian bookworm/main Sources [9494 kB]

и т.д.

ошибки:

E: Unable to locate package linux-headers-6.1.0-29-amd64
E: Couldn't find any package by glob 'linux-headers-6.1.0-29-amd64'
E: Couldn't find any package by regex 'linux-headers-6.1.0-29-amd64'
E: Unable to locate package build-essential

пока исправили, вручную через ssh выполнив обновление и установку заголовков ядра:

vagrant ssh
sudo apt update -y
sudo apt install linux-headers-amd64 build-essential dkms -y

Далее после каждого vagrant reload машина перезапускалась без ошибок

vagrant status
Current machine states:

default                   running (virtualbox)

The VM is running. To stop this VM, you can run `vagrant halt` to
shut it down forcefully, or you can run `vagrant suspend` to simply
suspend the virtual machine. In either case, to restart it again,
simply run `vagrant up`.

При проверке оказалось, что

config.vm.synced_folder "./sqlite-amalgamation-3260000", "/home/vagrant/sqlite-amalgamation-3260000"

не смонтировалось, попробуем с аргументом type: "virtualbox"

Но тоже не вышло, т.к. была ошибка в скрипте

~/.vagrant.d/gems/3.4.4/gems/vagrant-vbguest-0.32.0/lib/vagrant-vbguest/hosts/virtualbox.rb

Необходимо было заменить старый синтаксис File.exists? на File.exist?

После этих изменений и vagrant halt, vagrant up пошло скачивание гостевого дополнения:

Downloading VirtualBox Guest Additions ISO from https://download.virtualbox.org/virtualbox/7.1.10/VBoxGuestAdditions_7.1.10.iso

Наконец после завершения установки гостевого дополнения и перезагрузки получили:

Restarting VM to apply changes...
==> default: Attempting graceful shutdown of VM...
==> default: Booting VM...
==> default: Waiting for machine to boot. This may take a few minutes...
==> default: Machine booted and ready!
==> default: Checking for guest additions in VM...
==> default: Configuring and enabling network interfaces...
==> default: Mounting shared folders...
    default: /home/nemo/Стажировка InfoTecs => /vagrant
    default: /home/nemo/Стажировка InfoTecs/sqlite-amalgamation-3260000 => /home/vagrant/sqlite-amalgamation-3260000

==> default: Machine 'default' has a post `vagrant up` message. This is a message
==> default: from the creator of the Vagrantfile, and not from Vagrant itself:
==> default:
==> default: Vanilla Debian box. See https://app.vagrantup.com/debian for help and bug reports

Общая папка с докером и исходниками примонтировалась!
Но в ней лишние папки для билда, релиза и логи. Тогда воспользуемся

type: "rsync",
rsync__exclude: ["Release", "build", "logs_lin", "logs_win"]

чтобы синхронизировать только нужные папки. Этот тип не поддерживает двунаправленную синхронизацию, но в нашем случае
можно передавать данные только из хоста в контейнер.
В итоге имеем:

vagrant up --provider=virtualbox
Bringing machine 'default' up with 'virtualbox' provider...
==> default: Clearing any previously set forwarded ports...
==> default: Clearing any previously set network interfaces...
==> default: Preparing network interfaces based on configuration...
    default: Adapter 1: nat
    default: Adapter 2: hostonly
==> default: Forwarding ports...
    default: 22 (guest) => 2222 (host) (adapter 1)
==> default: Running 'pre-boot' VM customizations...
==> default: Booting VM...
==> default: Waiting for machine to boot. This may take a few minutes...
    default: SSH address: 127.0.0.1:2222
    default: SSH username: vagrant
    default: SSH auth method: private key
==> default: Machine booted and ready!
[default] GuestAdditions 7.1.10 running --- OK.
==> default: Checking for guest additions in VM...
==> default: Configuring and enabling network interfaces...
==> default: Installing rsync to the VM...
==> default: Rsyncing folder: /home/nemo/Стажировка InfoTecs/sqlite-amalgamation-3260000/ => /home/vagrant/sqlite-amalgamation-3260000
==> default:   - Exclude: [".vagrant/", "Release", "build", "logs_lin", "logs_win"]
==> default: Mounting shared folders...
    default: /home/nemo/Стажировка InfoTecs => /vagrant
==> default: Machine already provisioned. Run `vagrant provision` or use the `--provision`
==> default: flag to force provisioning. Provisioners marked to run always will still run.

==> default: Machine 'default' has a post `vagrant up` message. This is a message
==> default: from the creator of the Vagrantfile, and not from Vagrant itself:
==> default:
==> default: Vanilla Debian box. See https://app.vagrantup.com/debian for help and bug reports

Таким образом мы выполнили 5 пункт, автоматизировав сборку ВМ через vagrant в среде VB.
Перейдём к 6 пункту - настройке docker-технологии на машине через плейбук.

Посде добавления файлов можно перезапустить машину с командой на provisioning:

vagrant reload --provision

Пришлось переписать inventory.ini, содержащий идентификатор bookworm (а у нас машина осталась default):

[dev_vm]
default
ansible_host=192.168.56.10
ansible_user=vagrant
ansible_ssh_private_key_file=./.vagrant/machines/bookworm/virtualbox/private_key
ansible_python_interpreter=/usr/bin/python3

на новый вариант, с парвильным идентификатором default:

[dev_vm]
default ansible_host=192.168.56.10
[dev_vm:vars]
ansible_user=vagrant
ansible_ssh_private_key_file=./.vagrant/machines/default/virtualbox/private_key
ansible_python_interpreter=/usr/bin/python3

И наконец получаем рабочий плейбук для 6 задания: vagrant reload --provision

==> default: Attempting graceful shutdown of VM...
==> default: Forcing shutdown of VM...
==> default: Clearing any previously set forwarded ports...
==> default: Clearing any previously set network interfaces...
==> default: Preparing network interfaces based on configuration...
    default: Adapter 1: nat
    default: Adapter 2: hostonly
==> default: Forwarding ports...
    default: 22 (guest) => 2222 (host) (adapter 1)
==> default: Running 'pre-boot' VM customizations...
==> default: Booting VM...
==> default: Waiting for machine to boot. This may take a few minutes...
    default: SSH address: 127.0.0.1:2222
    default: SSH username: vagrant
    default: SSH auth method: private key
==> default: Machine booted and ready!
[default] GuestAdditions 7.1.10 running --- OK.
==> default: Checking for guest additions in VM...
==> default: Configuring and enabling network interfaces...
==> default: Rsyncing folder: /home/nemo/Стажировка_InfoTecs/sqlite-amalgamation-3260000/ => /home/vagrant/sqlite-amalgamation-3260000
==> default:   - Exclude: [".vagrant/", "Release", "build", "logs_lin", "logs_win"]
==> default: Mounting shared folders...
    default: /home/nemo/Стажировка_InfoTecs => /vagrant
==> default: Running provisioner: ansible...
    default: Running ansible-playbook...

PLAY [Install Docker Engine on Debian Bookworm] ********************************

TASK [Gathering Facts] *********************************************************
ok: [default]

TASK [Install required dependencies] *******************************************
changed: [default]

TASK [Create keyrings directory] ***********************************************
ok: [default]

TASK [Download Docker GPG key] *************************************************
changed: [default]

TASK [Make GPG key readable] ***************************************************
ok: [default]

TASK [Get system architecture] *************************************************
ok: [default]

TASK [Get Debian version codename] *********************************************
ok: [default]

TASK [Add Docker repository to sources.list.d] *********************************
changed: [default]

TASK [Update apt package index] ************************************************
changed: [default]

TASK [Install Docker and plugins] **********************************************
changed: [default]

TASK [Enable and start Docker] *************************************************
ok: [default]

TASK [Add current user to docker group] ****************************************
changed: [default]

TASK [Set Docker daemon config] ************************************************
changed: [default]

TASK [Run hello-world container] ***********************************************
ok: [default]

TASK [Show test output] ********************************************************
ok: [default] => {
    "hello.stdout": "\nHello from Docker!\nThis message shows that your installation appears to be working correctly.\n\nTo generate this message, Docker took the following steps:\n 1. The Docker client contacted the Docker daemon.\n 2. The Docker daemon pulled the \"hello-world\" image from the Docker Hub.\n    (amd64)\n 3. The Docker daemon created a new container from that image which runs the\n    executable that produces the output you are currently reading.\n 4. The Docker daemon streamed that output to the Docker client, which sent it\n    to your terminal.\n\nTo try something more ambitious, you can run an Ubuntu container with:\n $ docker run -it ubuntu bash\n\nShare images, automate workflows, and more with a free Docker ID:\n https://hub.docker.com/\n\nFor more examples and ideas, visit:\n https://docs.docker.com/get-started/"
}

RUNNING HANDLER [Restart Docker] ***********************************************
changed: [default]

PLAY RECAP *********************************************************************
default                    : ok=16   changed=8    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0


==> default: Machine 'default' has a post `vagrant up` message. This is a message
==> default: from the creator of the Vagrantfile, and not from Vagrant itself:
==> default:
==> default: Vanilla Debian box. See https://app.vagrantup.com/debian for help and bug reports

Попробуем сделать так, чтобы Vagrant-идентификатор ВМ поменялся с default на bookworm, и везде это было корректно.
Для этого в Vagrantfile обернём атрибуты ВМ в config.vm.define "bookworm" do |bookworm|.

После удаления машины default и создания новой bookworm во время её запуска она, также, как и default,
запускается, но не может установить автоматически нужные заголовки ядра через гостевое дополнение.
Мы ранее это делали вручную через vagrant ssh, но хочется автоматизации после vagrant up, поэтому просто внесём в Vagrantfile:

config.vbguest.auto_update = false   # не проверять обновления гостевого дополнения
config.vbguest.no_install  = true    # и вовсе не пытаться устанавливать дополнение

Теперь попробуем заново собрать ВМ, запустив provisioning сразу после запуска

vagrant destroy -f
vagrant up --provider=virtualbox --provision

Bringing machine 'bookworm' up with 'virtualbox' provider...
==> bookworm: Importing base box 'debian/bookworm64'...
==> bookworm: Matching MAC address for NAT networking...
==> bookworm: Checking if box 'debian/bookworm64' version '12.20250126.1' is up to date...
==> bookworm: Setting the name of the VM: _InfoTecs_bookworm_1753006451475_16063
==> bookworm: Clearing any previously set network interfaces...
==> bookworm: Preparing network interfaces based on configuration...
    bookworm: Adapter 1: nat
    bookworm: Adapter 2: hostonly
==> bookworm: Forwarding ports...
    bookworm: 22 (guest) => 2222 (host) (adapter 1)
==> bookworm: Running 'pre-boot' VM customizations...
==> bookworm: Booting VM...
==> bookworm: Waiting for machine to boot. This may take a few minutes...
    bookworm: SSH address: 127.0.0.1:2222
    bookworm: SSH username: vagrant
    bookworm: SSH auth method: private key
    bookworm:
    bookworm: Vagrant insecure key detected. Vagrant will automatically replace
    bookworm: this with a newly generated keypair for better security.
    bookworm:
    bookworm: Inserting generated public key within guest...
    bookworm: Removing insecure key from the guest if it's present...
    bookworm: Key inserted! Disconnecting and reconnecting using new SSH key...
==> bookworm: Machine booted and ready!
==> bookworm: Checking for guest additions in VM...
    bookworm: The guest additions on this VM do not match the installed version of
    bookworm: VirtualBox! In most cases this is fine, but in rare cases it can
    bookworm: prevent things such as shared folders from working properly. If you see
    bookworm: shared folder errors, please make sure the guest additions within the
    bookworm: virtual machine match the version of VirtualBox you have installed on
    bookworm: your host and reload your VM.
    bookworm:
    bookworm: Guest Additions Version: 6.0.0 r127566
    bookworm: VirtualBox Version: 7.1
==> bookworm: Setting hostname...
==> bookworm: Configuring and enabling network interfaces...
==> bookworm: Installing rsync to the VM...
==> bookworm: Rsyncing folder: /home/nemo/Стажировка_InfoTecs/sqlite-amalgamation-3260000/ => /home/vagrant/sqlite-amalgamation-3260000
==> bookworm:   - Exclude: [".vagrant/", "Release", "build", "logs_lin", "logs_win"]
==> bookworm: Mounting shared folders...
    bookworm: /home/nemo/Стажировка_InfoTecs => /vagrant
==> bookworm: Running provisioner: ansible...
    bookworm: Running ansible-playbook...

PLAY [Install Docker Engine on Debian Bookworm] ********************************

TASK [Gathering Facts] *********************************************************
ok: [bookworm]

TASK [Install required dependencies] *******************************************
changed: [bookworm]

TASK [Create keyrings directory] ***********************************************
ok: [bookworm]

TASK [Download Docker GPG key] *************************************************
changed: [bookworm]

TASK [Make GPG key readable] ***************************************************
ok: [bookworm]

TASK [Get system architecture] *************************************************
ok: [bookworm]

TASK [Get Debian version codename] *********************************************
ok: [bookworm]

TASK [Add Docker repository to sources.list.d] *********************************
changed: [bookworm]

TASK [Update apt package index] ************************************************
changed: [bookworm]

TASK [Install Docker and plugins] **********************************************
changed: [bookworm]

TASK [Enable and start Docker] *************************************************
ok: [bookworm]

TASK [Add current user to docker group] ****************************************
changed: [bookworm]

TASK [Set Docker daemon config] ************************************************
changed: [bookworm]

TASK [Run hello-world container] ***********************************************
ok: [bookworm]

TASK [Show test output] ********************************************************
ok: [bookworm] => {
    "hello.stdout": "\nHello from Docker!\nThis message shows that your installation appears to be working correctly.\n\nTo generate this message, Docker took the following steps:\n 1. The Docker client contacted the Docker daemon.\n 2. The Docker daemon pulled the \"hello-world\" image from the Docker Hub.\n    (amd64)\n 3. The Docker daemon created a new container from that image which runs the\n    executable that produces the output you are currently reading.\n 4. The Docker daemon streamed that output to the Docker client, which sent it\n    to your terminal.\n\nTo try something more ambitious, you can run an Ubuntu container with:\n $ docker run -it ubuntu bash\n\nShare images, automate workflows, and more with a free Docker ID:\n https://hub.docker.com/\n\nFor more examples and ideas, visit:\n https://docs.docker.com/get-started/"
}

RUNNING HANDLER [Restart Docker] ***********************************************
changed: [bookworm]

PLAY RECAP *********************************************************************
bookworm                   : ok=16   changed=8    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0


==> bookworm: Machine 'bookworm' has a post `vagrant up` message. This is a message
==> bookworm: from the creator of the Vagrantfile, and not from Vagrant itself:
==> bookworm:
==> bookworm: Vanilla Debian box. See https://app.vagrantup.com/debian for help and bug reports

Супер. Перейдём к 7 пункту - создадим ещё один .yml, через который автоматизируем на Vagrant-машине
скачивание исходников, построение докер-контейнера для sqlite, а также запуск sqlite с линковкой к libsqlite.so,
запуск контейнера и проверку корректности работы бинарника.
Для этого создали sqlite_build.yml, где добавили шаги по скачиванию архива и построению контейнера.
Главное - не запутаться в относительных путях рабочих папок виртуальной среды внутри виртуальной среды...
Наконец, тестируем:

vagrant destroy -f
vagrant up --provider=virtualbox --provision

Bringing machine 'bookworm' up with 'virtualbox' provider...
==> bookworm: Importing base box 'debian/bookworm64'...
==> bookworm: Matching MAC address for NAT networking...
==> bookworm: Checking if box 'debian/bookworm64' version '12.20250126.1' is up to date...
==> bookworm: Setting the name of the VM: _InfoTecs_bookworm_1753013867414_63385
==> bookworm: Clearing any previously set network interfaces...
==> bookworm: Preparing network interfaces based on configuration...
    bookworm: Adapter 1: nat
    bookworm: Adapter 2: hostonly
==> bookworm: Forwarding ports...
    bookworm: 22 (guest) => 2222 (host) (adapter 1)
==> bookworm: Running 'pre-boot' VM customizations...
==> bookworm: Booting VM...
==> bookworm: Waiting for machine to boot. This may take a few minutes...
    bookworm: SSH address: 127.0.0.1:2222
    bookworm: SSH username: vagrant
    bookworm: SSH auth method: private key
    bookworm:
    bookworm: Vagrant insecure key detected. Vagrant will automatically replace
    bookworm: this with a newly generated keypair for better security.
    bookworm:
    bookworm: Inserting generated public key within guest...
    bookworm: Removing insecure key from the guest if it's present...
    bookworm: Key inserted! Disconnecting and reconnecting using new SSH key...
==> bookworm: Machine booted and ready!
==> bookworm: Checking for guest additions in VM...
    bookworm: The guest additions on this VM do not match the installed version of
    bookworm: VirtualBox! In most cases this is fine, but in rare cases it can
    bookworm: prevent things such as shared folders from working properly. If you see
    bookworm: shared folder errors, please make sure the guest additions within the
    bookworm: virtual machine match the version of VirtualBox you have installed on
    bookworm: your host and reload your VM.
    bookworm:
    bookworm: Guest Additions Version: 6.0.0 r127566
    bookworm: VirtualBox Version: 7.1
==> bookworm: Setting hostname...
==> bookworm: Configuring and enabling network interfaces...
==> bookworm: Installing rsync to the VM...
==> bookworm: Rsyncing folder: /home/nemo/Стажировка_InfoTecs/sqlite-amalgamation-3260000/ => /home/vagrant/sqlite-amalgamation-3260000
==> bookworm:   - Exclude: [".vagrant/", "Release", "build", "logs_lin", "logs_win", "*.c", "*.h"]
==> bookworm: Mounting shared folders...
    bookworm: /home/nemo/Стажировка_InfoTecs => /vagrant
==> bookworm: Running provisioner: ansible...
    bookworm: Running ansible-playbook...

PLAY [Install Docker Engine on Debian Bookworm] ********************************

TASK [Gathering Facts] *********************************************************
ok: [bookworm]

TASK [Install required dependencies] *******************************************
changed: [bookworm]

TASK [Create keyrings directory] ***********************************************
ok: [bookworm]

TASK [Download Docker GPG key] *************************************************
changed: [bookworm]

TASK [Make GPG key readable] ***************************************************
ok: [bookworm]

TASK [Get system architecture] *************************************************
ok: [bookworm]

TASK [Get Debian version codename] *********************************************
ok: [bookworm]

TASK [Add Docker repository to sources.list.d] *********************************
changed: [bookworm]

TASK [Update apt package index] ************************************************
changed: [bookworm]

TASK [Install Docker and plugins] **********************************************
changed: [bookworm]

TASK [Enable and start Docker] *************************************************
ok: [bookworm]

TASK [Add current user to docker group] ****************************************
changed: [bookworm]

TASK [Set Docker daemon config] ************************************************
changed: [bookworm]

TASK [Run hello-world container] ***********************************************
ok: [bookworm]

TASK [Show test output] ********************************************************
ok: [bookworm] => {
    "hello.stdout": "\nHello from Docker!\nThis message shows that your installation appears to be working correctly.\n\nTo generate this message, Docker took the following steps:\n 1. The Docker client contacted the Docker daemon.\n 2. The Docker daemon pulled the \"hello-world\" image from the Docker Hub.\n    (amd64)\n 3. The Docker daemon created a new container from that image which runs the\n    executable that produces the output you are currently reading.\n 4. The Docker daemon streamed that output to the Docker client, which sent it\n    to your terminal.\n\nTo try something more ambitious, you can run an Ubuntu container with:\n $ docker run -it ubuntu bash\n\nShare images, automate workflows, and more with a free Docker ID:\n https://hub.docker.com/\n\nFor more examples and ideas, visit:\n https://docs.docker.com/get-started/"
}

RUNNING HANDLER [Restart Docker] ***********************************************
changed: [bookworm]

PLAY RECAP *********************************************************************
bookworm                   : ok=16   changed=8    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0

==> bookworm: Running provisioner: ansible...
    bookworm: Running ansible-playbook...

PLAY [Build SQLite inside Docker] **********************************************

TASK [Gathering Facts] *********************************************************
ok: [bookworm]

TASK [Ensure unzip is installed] ***********************************************
changed: [bookworm]

TASK [Download SQLite source archive] ******************************************
changed: [bookworm]

TASK [Create temp dir for unzip] ***********************************************
changed: [bookworm]

TASK [Unpack SQLite archive] ***************************************************
changed: [bookworm]

TASK [Remove sqlite.zip directory] *********************************************
changed: [bookworm]

TASK [Move extracted files from tmp folder to main project_dir] ****************
changed: [bookworm]

TASK [Remove temp unzip directory] *********************************************
changed: [bookworm]

TASK [Build Docker image for SQLite] *******************************************
changed: [bookworm]

TASK [Run built container and check SQLite version] ****************************
ok: [bookworm]

TASK [Show SQLite version] *****************************************************
ok: [bookworm] => {
    "sqlite_version_output.stdout": "3.26.0 2018-12-01 12:34:55 bf8c1b2b7a5960c282e543b9c293686dccff272512d08865f4600fb58238b4f9"
}

PLAY RECAP *********************************************************************
bookworm                   : ok=11   changed=8    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0


==> bookworm: Machine 'bookworm' has a post `vagrant up` message. This is a message
==> bookworm: from the creator of the Vagrantfile, and not from Vagrant itself:
==> bookworm:
==> bookworm: Vanilla Debian box. See https://app.vagrantup.com/debian for help and bug reports

Отлично. Пункт 7 мы выполнили.
Перейдём к п. 8. Подготовим простую Hello, World! программу на C++, которая использует стороннюю библиотеку fmt.
Далее соберём бинарный файл этой программы с использованием conanfile.py, а также CMake и gcc в ОС Linux.

conan --version
Conan version 2.18.0

Будем готовить CMakeLists к Conan версии 2.х.

cmake_minimum_required(VERSION 3.15)
project(ConanExample)
# Conan 2.x автоматически найдёт зависимости через find_package()
find_package(fmt REQUIRED)
add_executable(main ../main.cpp)
target_link_libraries(main fmt::fmt)

Пробуем conan install .. --build=missing
ERROR: The default build profile '/home/nemo/.conan2/profiles/default' doesn't exist.
You need to create a default profile (type 'conan profile detect' command)
or specify your own profile with '--profile:build=<myprofile>'

нужно сначала создать профиль с gcc, сделаем это: conan profile detect
detect_api: Found cc=gcc-15.1.1
detect_api: gcc>=5, using the major as version
detect_api: gcc C++ standard library: libstdc++11

Detected profile:
[settings]
arch=x86_64
build_type=Release
compiler=gcc
compiler.cppstd=gnu17
compiler.libcxx=libstdc++11
compiler.version=15
os=Linux

WARN: This profile is a guess of your environment, please check it.
WARN: The output of this command is not guaranteed to be stable and can change in future Conan versions.
WARN: Use your own profile files for stability.
Saving detected profile to /home/nemo/.conan2/profiles/default

Далее устанавливаем зависимсоти черех Conan: conan install .. --build=missing

======== Input profiles ========
Profile host:
[settings]
arch=x86_64
build_type=Release
compiler=gcc
compiler.cppstd=gnu17
compiler.libcxx=libstdc++11
compiler.version=15
os=Linux

Profile build:
[settings]
arch=x86_64
build_type=Release
compiler=gcc
compiler.cppstd=gnu17
compiler.libcxx=libstdc++11
compiler.version=15
os=Linux

======== Computing dependency graph ========
fmt/10.2.1: Not found in local cache, looking in remotes...
fmt/10.2.1: Checking remote: conancenter
Connecting to remote 'conancenter' anonymously
fmt/10.2.1: Downloaded recipe revision 658771bb858b77f380be2ebb22c338e9
Graph root
    conanfile.py (example/0.1): /home/nemo/Стажировка_InfoTecs/task-8_cpp-conan/conanfile.py
Requirements
    fmt/10.2.1#658771bb858b77f380be2ebb22c338e9 - Downloaded (conancenter)

======== Computing necessary packages ========
fmt/10.2.1: Main binary package '64947a41c7caa014aadbeaa53f1602ad0d30673d' missing
fmt/10.2.1: Checking 11 compatible configurations
fmt/10.2.1: Compatible configurations not found in cache, checking servers
fmt/10.2.1: '1746764b22461b97152c44a466f8880da78596af': compiler.cppstd=11
fmt/10.2.1: 'a75c163fca6c43b56555004d4e598ecebf1b61bc': compiler.cppstd=gnu11
fmt/10.2.1: '4bdc48bcef47853185b2b542b1b07cc40a825d4e': compiler.cppstd=14
fmt/10.2.1: 'ab5de0a28845cfe70c4220a4404978334a81bbec': compiler.cppstd=gnu14
fmt/10.2.1: '0364e7f8fc1c021fe93b04ad01169c39bb69a007': compiler.cppstd=17
fmt/10.2.1: '206c484e1c46c66d8bbeb62b2b76a229b17405be': compiler.cppstd=20
fmt/10.2.1: '41ff7e43e206751914e2a03f64f9235533be81d7': compiler.cppstd=gnu20
fmt/10.2.1: 'f679fbaf71726502d3ee047968670c713d088ed0': compiler.cppstd=23
fmt/10.2.1: '8b2f5bde089ee1b2f7efa90c14e5045983e3bee8': compiler.cppstd=gnu23
fmt/10.2.1: 'f3e8a9c90ac4f8313361cbf0add1c47531ac9290': compiler.cppstd=26
fmt/10.2.1: 'c7d145c3e80c4c9ec23f5e5103a7d19e7a803a58': compiler.cppstd=gnu26
Requirements
    fmt/10.2.1#658771bb858b77f380be2ebb22c338e9:64947a41c7caa014aadbeaa53f1602ad0d30673d - Build

======== Installing packages ========
fmt/10.2.1: Sources downloaded from 'conancenter'
fmt/10.2.1: Calling source() in /home/nemo/.conan2/p/fmtfd0fc8a6cd618/s/src
fmt/10.2.1: Uncompressing fmt-10.2.1.zip to .
fmt/10.2.1: Unzipping 4.6MB, this can take a while

-------- Installing package fmt/10.2.1 (1 of 1) --------
fmt/10.2.1: Building from source
fmt/10.2.1: Package fmt/10.2.1:64947a41c7caa014aadbeaa53f1602ad0d30673d
fmt/10.2.1: settings: os=Linux arch=x86_64 compiler=gcc compiler.cppstd=gnu17 compiler.libcxx=libstdc++11 compiler.version=15 build_type=Release
fmt/10.2.1: options: fPIC=True header_only=False shared=False with_os_api=True
fmt/10.2.1: Copying sources to build folder
fmt/10.2.1: Building your package in /home/nemo/.conan2/p/b/fmt35611ed019e18/b
fmt/10.2.1: Calling generate()
fmt/10.2.1: Generators folder: /home/nemo/.conan2/p/b/fmt35611ed019e18/b/build/Release/generators
fmt/10.2.1: CMakeToolchain generated: conan_toolchain.cmake
fmt/10.2.1: CMakeToolchain generated: /home/nemo/.conan2/p/b/fmt35611ed019e18/b/build/Release/generators/CMakePresets.json
fmt/10.2.1: CMakeToolchain generated: /home/nemo/.conan2/p/b/fmt35611ed019e18/b/src/CMakeUserPresets.json
fmt/10.2.1: Generating aggregated env files
fmt/10.2.1: Generated aggregated env files: ['conanbuild.sh', 'conanrun.sh']
fmt/10.2.1: Calling build()
fmt/10.2.1: apply_conandata_patches(): No patches defined in conandata
fmt/10.2.1: Running CMake.configure()
fmt/10.2.1: RUN: cmake -G "Unix Makefiles" -DCMAKE_TOOLCHAIN_FILE="generators/conan_toolchain.cmake" -DCMAKE_INSTALL_PREFIX="/home/nemo/.conan2/p/b/fmt35611ed019e18/p" -DFMT_DOC="OFF" -DFMT_TEST="OFF" -DFMT_INSTALL="ON" -DFMT_LIB_DIR="lib" -DFMT_OS="ON" -DCMAKE_POLICY_DEFAULT_CMP0091="NEW" -DCMAKE_BUILD_TYPE="Release" "/home/nemo/.conan2/p/b/fmt35611ed019e18/b/src"
-- CMake version: 4.0.3-dirty
-- Using Conan toolchain: /home/nemo/.conan2/p/b/fmt35611ed019e18/b/build/Release/generators/conan_toolchain.cmake
-- Conan toolchain: Setting CMAKE_POSITION_INDEPENDENT_CODE=ON (options.fPIC)
-- Conan toolchain: Defining architecture flag: -m64
-- Conan toolchain: C++ Standard 17 with extensions ON
-- Conan toolchain: Setting BUILD_SHARED_LIBS = OFF
-- The CXX compiler identification is GNU 15.1.1
-- Detecting CXX compiler ABI info
-- Detecting CXX compiler ABI info - done
-- Check for working CXX compiler: /usr/bin/c++ - skipped
-- Detecting CXX compile features
-- Detecting CXX compile features - done
-- Version: 10.2.1
-- Build type: Release
-- Configuring done (0.4s)
-- Generating done (0.0s)
-- Build files have been written to: /home/nemo/.conan2/p/b/fmt35611ed019e18/b/build/Release

fmt/10.2.1: Running CMake.build()
fmt/10.2.1: RUN: cmake --build "/home/nemo/.conan2/p/b/fmt35611ed019e18/b/build/Release" -- -j16
[ 33%] Building CXX object CMakeFiles/fmt.dir/src/format.cc.o
[ 66%] Building CXX object CMakeFiles/fmt.dir/src/os.cc.o
[100%] Linking CXX static library libfmt.a
[100%] Built target fmt

fmt/10.2.1: Package '64947a41c7caa014aadbeaa53f1602ad0d30673d' built
fmt/10.2.1: Build folder /home/nemo/.conan2/p/b/fmt35611ed019e18/b/build/Release
fmt/10.2.1: Generating the package
fmt/10.2.1: Packaging in folder /home/nemo/.conan2/p/b/fmt35611ed019e18/p
fmt/10.2.1: Calling package()
fmt/10.2.1: Running CMake.install()
fmt/10.2.1: RUN: cmake --install "/home/nemo/.conan2/p/b/fmt35611ed019e18/b/build/Release" --prefix "/home/nemo/.conan2/p/b/fmt35611ed019e18/p"
-- Install configuration: "Release"
-- Installing: /home/nemo/.conan2/p/b/fmt35611ed019e18/p/lib/libfmt.a
-- Installing: /home/nemo/.conan2/p/b/fmt35611ed019e18/p/include/fmt/args.h
-- Installing: /home/nemo/.conan2/p/b/fmt35611ed019e18/p/include/fmt/chrono.h
-- Installing: /home/nemo/.conan2/p/b/fmt35611ed019e18/p/include/fmt/color.h
-- Installing: /home/nemo/.conan2/p/b/fmt35611ed019e18/p/include/fmt/compile.h
-- Installing: /home/nemo/.conan2/p/b/fmt35611ed019e18/p/include/fmt/core.h
-- Installing: /home/nemo/.conan2/p/b/fmt35611ed019e18/p/include/fmt/format.h
-- Installing: /home/nemo/.conan2/p/b/fmt35611ed019e18/p/include/fmt/format-inl.h
-- Installing: /home/nemo/.conan2/p/b/fmt35611ed019e18/p/include/fmt/os.h
-- Installing: /home/nemo/.conan2/p/b/fmt35611ed019e18/p/include/fmt/ostream.h
-- Installing: /home/nemo/.conan2/p/b/fmt35611ed019e18/p/include/fmt/printf.h
-- Installing: /home/nemo/.conan2/p/b/fmt35611ed019e18/p/include/fmt/ranges.h
-- Installing: /home/nemo/.conan2/p/b/fmt35611ed019e18/p/include/fmt/std.h
-- Installing: /home/nemo/.conan2/p/b/fmt35611ed019e18/p/include/fmt/xchar.h
-- Installing: /home/nemo/.conan2/p/b/fmt35611ed019e18/p/lib/cmake/fmt/fmt-config.cmake
-- Installing: /home/nemo/.conan2/p/b/fmt35611ed019e18/p/lib/cmake/fmt/fmt-config-version.cmake
-- Installing: /home/nemo/.conan2/p/b/fmt35611ed019e18/p/lib/cmake/fmt/fmt-targets.cmake
-- Installing: /home/nemo/.conan2/p/b/fmt35611ed019e18/p/lib/cmake/fmt/fmt-targets-release.cmake
-- Installing: /home/nemo/.conan2/p/b/fmt35611ed019e18/p/lib/pkgconfig/fmt.pc

fmt/10.2.1: package(): Packaged 1 '.a' file: libfmt.a
fmt/10.2.1: package(): Packaged 1 file: LICENSE
fmt/10.2.1: package(): Packaged 13 '.h' files
fmt/10.2.1: Created package revision a7889d70ef4690019fe2d1ca16abad6c
fmt/10.2.1: Package '64947a41c7caa014aadbeaa53f1602ad0d30673d' created
fmt/10.2.1: Full package reference: fmt/10.2.1#658771bb858b77f380be2ebb22c338e9:64947a41c7caa014aadbeaa53f1602ad0d30673d#a7889d70ef4690019fe2d1ca16abad6c
fmt/10.2.1: Package folder /home/nemo/.conan2/p/b/fmt35611ed019e18/p

======== Finalizing install (deploy, generators) ========
conanfile.py (example/0.1): Writing generators to /home/nemo/Стажировка_InfoTecs/task-8_cpp-conan/build/Release/generators
conanfile.py (example/0.1): Generator 'CMakeDeps' calling 'generate()'
conanfile.py (example/0.1): CMakeDeps necessary find_package() and targets for your CMakeLists.txt
    find_package(fmt)
    target_link_libraries(... fmt::fmt)
conanfile.py (example/0.1): Generator 'CMakeToolchain' calling 'generate()'
conanfile.py (example/0.1): CMakeToolchain generated: conan_toolchain.cmake
conanfile.py (example/0.1): CMakeToolchain: Preset 'conan-release' added to CMakePresets.json.
    (cmake>=3.23) cmake --preset conan-release
    (cmake<3.23) cmake <path> -G "Unix Makefiles" -DCMAKE_TOOLCHAIN_FILE=generators/conan_toolchain.cmake  -DCMAKE_POLICY_DEFAULT_CMP0091=NEW -DCMAKE_BUILD_TYPE=Release
conanfile.py (example/0.1): CMakeToolchain generated: /home/nemo/Стажировка_InfoTecs/task-8_cpp-conan/build/Release/generators/CMakePresets.json
conanfile.py (example/0.1): CMakeToolchain generated: /home/nemo/Стажировка_InfoTecs/task-8_cpp-conan/CMakeUserPresets.json
conanfile.py (example/0.1): Generating aggregated env files
conanfile.py (example/0.1): Generated aggregated env files: ['conanbuild.sh', 'conanrun.sh']
Install finished successfully

Далее конфигурируем проект:  cmake .. -DCMAKE_TOOLCHAIN_FILE=Release/generators/conan_toolchain.cmake
-- Using Conan toolchain: /home/nemo/Стажировка_InfoTecs/task-8_cpp-conan/build/Release/generators/conan_toolchain.cmake
-- Conan toolchain: Defining architecture flag: -m64
-- Conan toolchain: C++ Standard 17 with extensions ON
-- Conan: Component target declared 'fmt::fmt'
CMake Error at build/Release/generators/cmakedeps_macros.cmake:98 (message):
  Please, set the CMAKE_BUILD_TYPE variable when calling to CMake adding the
  '-DCMAKE_BUILD_TYPE=<build_type>' argument.
Call Stack (most recent call first):
  build/Release/generators/fmt-config.cmake:19 (check_build_type_defined)
  CMakeLists.txt:5 (find_package)

Получили ошибку: необходимо указать переменную CMAKE_BUILD_TYPE=Release, т.к.
Conan сгенерировал зависимости для режима Release (у нас так ранее профиль Conan собрался)

Запускаем конфигурацию опять: cmake .. \
        -DCMAKE_TOOLCHAIN_FILE=Release/generators/conan_toolchain.cmake \
        -DCMAKE_BUILD_TYPE=Release

-- Using Conan toolchain: /home/nemo/Стажировка_InfoTecs/task-8_cpp-conan/build/Release/generators/conan_toolchain.cmake
-- Conan toolchain: Defining architecture flag: -m64
-- Conan toolchain: C++ Standard 17 with extensions ON
-- Conan: Component target declared 'fmt::fmt'
-- Configuring done (0.0s)
-- Generating done (0.0s)
-- Build files have been written to: /home/nemo/Стажировка_InfoTecs/task-8_cpp-conan/build

Наконец билдим проект: cmake --build .

[ 50%] Building CXX object CMakeFiles/main.dir/main.cpp.o
[100%] Linking CXX executable main
[100%] Built target main

Запускаем: ./main

Hello, World!

Историю выполнения задания можно отследить, воспользовавшись репозиторием:

https://github.com/AleksandrBelous/InfoTecs_DevOps