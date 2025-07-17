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