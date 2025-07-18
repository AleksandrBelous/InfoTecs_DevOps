Начнём с пунктов 1-3. Во-первых, разберёмся, как компилировать .so под Linux через gcc, т.к. это наша хостовая ОС.
Для начала посмотрим, как это можно делать вручную через терминал, без CMakeList.
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
а shell.c при компиляции нашёл системный /usr/include/sqlite3.h версии 2025-06-06.
Заголовок и реализация оказались разных годов и SQLite на старте падает с сообщением о mismatch.

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
3.26.0

Получилось. Теперь ещё одним способом проверим, что на этапе запуска линкуется именно наш собранный .so

ldd ./sqlite3 | grep libsqlite3.so
libsqlite3.so => /home/USER/InfoTecs/sqlite-amalgamation-3260000/./libsqlite3.so (0x00007fc771a8d000)

Наша библиотека подгружается, отлично.
Проверим работу sqlite3

printf 'select 2+2;' | ./sqlite3 -batch
4

Работает корректно.

Теперь протестируем сборку библиотеки на Windows

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


:: (а) генерация + конфигурация
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


:: (б) сборка библиотеки
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


:: (в) сборка консольного клиента
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


C:\Users\user\source\repos\AleksandrBelous\InfoTecs_DevOps\sqlite-amalgamation-3260000>.\build\Release\sqlite3_cli.exe -version
3.26.0 2018-12-01 12:34:55 bf8c1b2b7a5960c282e543b9c293686dccff272512d08865f4600fb58238b4f9


C:\Users\user\source\repos\AleksandrBelous\InfoTecs_DevOps\sqlite-amalgamation-3260000>cmake --install build --config Release
-- Installing: C:/Users/user/source/repos/AleksandrBelous/InfoTecs_DevOps/sqlite-amalgamation-3260000/Release/lib/sqlite3.lib
-- Installing: C:/Users/user/source/repos/AleksandrBelous/InfoTecs_DevOps/sqlite-amalgamation-3260000/Release/bin/sqlite3.dll
-- Installing: C:/Users/user/source/repos/AleksandrBelous/InfoTecs_DevOps/sqlite-amalgamation-3260000/Release/bin/sqlite3_cli.exe


В одном из тестов собирали конфигурацию и либу с бинарём с разными аргументами дебаг \ релиз, получили ошибку:

C:\Users\user\source\repos\AleksandrBelous\InfoTecs_DevOps\sqlite-amalgamation-3260000>cmake --install build --config Release
CMake Error at build/cmake_install.cmake:51 (file):
  file INSTALL cannot find
  "C:/Users/user/source/repos/AleksandrBelous/InfoTecs_DevOps/sqlite-amalgamation-3260000/build/Release/sqlite3.dll":
  File exists.

потому что запустили

cmake --build build --target sqlite3
cmake --build build --target sqlite3_cli

без --config Release. В итоге собрался Debug‑вариант, поэтому библиотеки и exe легли в build\Debug\
Затем мы попытались установить Release‑конфигурацию:

cmake --install build --config Release

Скрипт cmake_install.cmake ищет файл build\Release\sqlite3.dll — его нет, поэтому CMake выдаёт

file INSTALL cannot find ".../Release/sqlite3.dll": File exists.