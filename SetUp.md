gcc -fPIC -shared sqlite3.c -lpthread -ldl -lm -o libsqlite3.so

gcc shell.c -I ./ -L ./ -lsqlite3 -lpthread -ldl -lm -Wl,-rpath,'$ORIGIN' -o sqlite3

./sqlite3 -batch <<< 'select sqlite_version();'

ldd ./sqlite3 | grep libsqlite3.so

Ниже -- «шпаргалка», которую можно дословно рассказывать проверяющему.
Я разбил объяснение на три уровня: **(1) общая идея**, **(2) что делает каждая GCC-команда**, **(3) как то же самое описывается в CMake**.

---

## 1 | Что вообще происходит

| Шаг                                                     | Цель                                                                                                                                                                                                         | Коротко                                                                                      |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------- |
| **A.** `gcc -fPIC -shared sqlite3.c … -o libsqlite3.so` | Скомпилировать *ядро* SQLite в **динамическую библиотеку** (`.so`).                                                                                                                                          | Библиотека хранит код и данные, но не запускается сама. Её могут подгружать любые программы. |
| **B.** `gcc shell.c … -lsqlite3 … -o sqlite3`           | Собрать **CLI-оболочку**. Это обычный исполняемый файл, который «под линковкой» обращается к функциям из `libsqlite3.so`.                                                                                    |                                                                                              |
| **C.** Запуск `./sqlite3`                               | Во время старта динамический загрузчик (`ld-linux.so`) ищет `libsqlite3.so`. Благодаря параметру **RPATH=\$ORIGIN** он сначала смотрит в тот же каталог, где лежит бинарь, и берёт именно *вашу* библиотеку. |                                                                                              |

**Зачем нужен .so:** проверяющий видит, что вы умеете:

1. Отличать динамическую сборку от статической.
2. Правильно выставлять флаги компилятору / линковщику.
3. Решать проблемы поиска библиотеки во время запуска (RPATH, LD\_LIBRARY\_PATH).

---

## 2 | Разбор каждой команды и флага

### 2.1 Библиотека

```bash
gcc -fPIC -shared sqlite3.c -lpthread -ldl -lm -o libsqlite3.so
```

| Аргумент           | Расшифровка                           | Зачем нужен                                                                                                     |
| ------------------ | ------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `gcc`              | GNU Compiler Collection               | Универсальный фронт-енд C/C++.                                                                                  |
| `-fPIC`            | **P**osition **I**ndependent **C**ode | Делает машинный код «релокируемым», т.е. пригодным для размещения в любом участке памяти. Требование для `.so`. |
| `-shared`          | «Собрать *shared object*»             | Вместо обычного ELF-exe компилятор сразу вызывает линковщик в режиме создания библиотеки.                       |
| `sqlite3.c`        | Исходник                              | 7 МБ «амальгамы» со всем кодом SQLite.                                                                          |
| `-lpthread`        | link **pthreads**                     | Потоки POSIX; SQLite поддерживает многопоточность.                                                              |
| `-ldl`             | link **d**ynamic **l**oader           | Функции `dlopen/dlsym` — внутри SQLite есть опциональная работа с расширениями.                                 |
| `-lm`              | link **m**ath                         | Здесь нужен всего один модуль `pow()` для внутренней функции `sqrt()`.                                          |
| `-o libsqlite3.so` | **o**utput                            | Итоговый файл библиотеки.                                                                                       |

---

### 2.2 CLI-оболочка

```bash
gcc shell.c -I. -L. -lsqlite3 -lpthread -ldl -lm \
    -Wl,-rpath,'$ORIGIN' -o sqlite3
```

| Аргумент               | Что делает                                         | Почему это важно                                                                         |
| ---------------------- | -------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `shell.c`              | отдельный источник, реализующий команду `sqlite3>` |                                                                                          |
| `-I.`                  | **I**nclude path «текущий каталог»                 | Заставляем компилятор брать **наш** `sqlite3.h`, а не системный.                         |
| `-L.`                  | **L**ibrary path «текущий каталог»                 | На этапе *линковки* ищем `libsqlite3.so` рядом.                                          |
| `-lsqlite3`            | link with **libsqlite3.so**                        | Подключаем функции ядра.                                                                 |
| `… -lpthread -ldl -lm` | те же системные библиотеки, что и у ядра           |                                                                                          |
| `-Wl,`…                | «передай опцию линковщику»                         | Всё, что после запятой уходит напрямую в `ld`.                                           |
| `-rpath,'$ORIGIN'`     | embed **runtime search path**                      | `$ORIGIN` подставится загрузчиком ⇒ при запуске сначала смотрим `.so` в каталоге бинаря. |
| `-o sqlite3`           | Имя исполняемого файла                             |                                                                                          |

👉 **Проверить, что используется именно ваша библиотека**
`ldd ./sqlite3 | grep libsqlite3` → путь должен быть `./libsqlite3.so`.

---

## 3 | Как то же самое описывается в CMake (минимальный скрипт)

```cmake
cmake_minimum_required(VERSION 3.15)
project(sqlite3 C)

add_library(sqlite3 SHARED sqlite3.c)          # аналог gcc -shared …
target_include_directories(sqlite3 PUBLIC .)   # эквивалент -I.
# (MSVC) экспорт символов без .def
if(MSVC)
    set_target_properties(sqlite3 PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS ON)
endif()

if(UNIX AND NOT APPLE)                         # только Linux/*BSD
    add_executable(sqlite3_cli shell.c)
    target_link_libraries(sqlite3_cli           # = -lsqlite3 -lpthread -ldl -lm
        PRIVATE sqlite3 pthread dl m)
    target_link_options(sqlite3_cli
        PRIVATE -Wl,-rpath,'$ORIGIN')           # = -Wl,-rpath,'$ORIGIN'
endif()
```

* **`add_library … SHARED`** автоматически добавляет `-fPIC -shared` и создаёт `libsqlite3.so` (или `sqlite3.dll` под MSVC).
* **`target_include_directories PUBLIC .`** решает проблему «видеть локальный заголовок».
* **`target_link_libraries`** аккуратно добавляет системные библиотеки с учётом платформы.
* **`target_link_options`** вшивает RPATH.

Получаем **один кросс-платформенный скрипт** вместо двух длинных ручных команд.

---

## 4 | Разница «Static vs Shared» (если спросят)

| Критерий                    | Статическая (`.a`)                                | Динамическая (`.so/.dll`)                                        |
| --------------------------- | ------------------------------------------------- | ---------------------------------------------------------------- |
| **Сборка**                  | `ar rcs libsqlite3.a …`                           | `gcc -shared … -o libsqlite3.so`                                 |
| **Как подключается**        | Код копируется в каждый exe (увеличивает размер). | exe хранит только «ссылки» (меньше размер, одна копия в памяти). |
| **Обновление/патч**         | Надо пересобрать все программы.                   | Достаточно заменить `.so`.                                       |
| **RPATH/LD\_LIBRARY\_PATH** | Не нужен.                                         | Нужен, иначе загрузчик не найдёт библиотеку.                     |
| **Windows-эквивалент**      | `.lib` + объект                                   | `.dll` + `.lib`-стаб (импорт-библиотека)                         |

---

## 5 | Три типичные проверки, которые сделает ревьюер

1. **Собирается ли проект под Linux и под MSVC**

   ```bash
   mkdir build && cd build && cmake .. && cmake --build .
   ```
2. **ldd показывает локальную .so**

   ```bash
   ldd sqlite3_cli | grep libsqlite3
   ```
3. **CLI отвечает корректно**

   ```bash
   printf 'select 2+2;' | ./sqlite3_cli -batch
   # → 4
   ```

Если все три пункта проходят, задание зачтено.

---

### Короткий ответ, если времени мало

> «.so нужен, чтобы показать, что я умею собирать динамические библиотеки: ставлю `-fPIC -shared`, задаю RPATH = \$ORIGIN, проверяю `ldd`. CLI компилирую отдельно и линкую против этой библиотеки. В CMake всё это описывается `add_library(SHARED)` + `target_link_options(-Wl,-rpath,'$ORIGIN')`. Таким образом демонстрирую владение и компилятором, и линковщиком, и CMake.»


┌─[ nemo on nautilus ] at [ ~/Стажировка InfoTecs/sqlite-amalgamation-3260000/build ]-( Tue Jul 15, 20:33 )
└─< git: master>-[ $ ] cmake ..
-- The C compiler identification is GNU 15.1.1
-- Detecting C compiler ABI info
-- Detecting C compiler ABI info - done
-- Check for working C compiler: /usr/bin/cc - skipped
-- Detecting C compile features
-- Detecting C compile features - done
-- Configuring done (0.2s)
-- Generating done (0.0s)
-- Build files have been written to: /home/nemo/Стажировка InfoTecs/sqlite-amalgamation-3260000/build

┌─[ nemo on nautilus ] at [ ~/Стажировка InfoTecs/sqlite-amalgamation-3260000/build ]-( Tue Jul 15, 20:34 )
└─< git: master>-[ $ ] ll
6586382 drwxr-xr-x nemo users 4.0 KB Tue Jul 15 20:34:03 2025  ./
6424564 drwxr-xr-x nemo users 4.0 KB Tue Jul 15 20:33:57 2025  ../
6586537 .rw-r--r-- nemo users 2.2 KB Tue Jul 15 20:34:03 2025  cmake_install.cmake
6586502 .rw-r--r-- nemo users  12 KB Tue Jul 15 20:34:03 2025  CMakeCache.txt
6586390 drwxr-xr-x nemo users 4.0 KB Tue Jul 15 20:34:03 2025  CMakeFiles/
6586534 .rw-r--r-- nemo users 6.4 KB Tue Jul 15 20:34:03 2025  Makefile

┌─[ nemo on nautilus ] at [ ~/Стажировка InfoTecs/sqlite-amalgamation-3260000/build ]-( Tue Jul 15, 20:34 )
└─< git: master>-[ $ ] cmake --build . --target sqlite3                      
[ 50%] Building C object CMakeFiles/sqlite3.dir/sqlite3.c.o
[100%] Linking C shared library libsqlite3.so
[100%] Built target sqlite3

┌─[ nemo on nautilus ] at [ ~/Стажировка InfoTecs/sqlite-amalgamation-3260000/build ]-( Tue Jul 15, 20:56 )
└─< git: master>-[ $ ] cmake --build . --target sqlite3_cli
[ 50%] Built target sqlite3
[ 75%] Building C object CMakeFiles/sqlite3_cli.dir/shell.c.o
[100%] Linking C executable sqlite3_cli
[100%] Built target sqlite3_cli

┌─[ nemo on nautilus ] at [ ~/Стажировка InfoTecs/sqlite-amalgamation-3260000/build ]-( Tue Jul 15, 20:57 )
└─< git: master>-[ $ ] ./sqlite3_cli -batch <<< 'select 2+2;'
# → 4
ldd ./sqlite3_cli | grep libsqlite3
# → …/build/libsqlite3.so
4
libsqlite3.so => /home/nemo/Стажировка InfoTecs/sqlite-amalgamation-3260000/build/libsqlite3.so (0x00007f45e63f8000)

┌─[ nemo on nautilus ] at [ ~/Стажировка InfoTecs/sqlite-amalgamation-3260000/build ]-( Tue Jul 15, 20:57 )
└─< git: master>-[ $ ] ./sqlite3_cli                         
SQLite version 3.26.0 2018-12-01 12:34:55
Enter ".help" for usage hints.
Connected to a transient in-memory database.
Use ".open FILENAME" to reopen on a persistent database.
sqlite> .exit

┌─[ nemo on nautilus ] at [ ~/Стажировка InfoTecs/sqlite-amalgamation-3260000/build ]-( Tue Jul 15, 20:58 )
└─< git: master>-[ $ ] 





┌─[ nemo on nautilus ] at [ ~/Стажировка InfoTecs/sqlite-amalgamation-3260000 ]-( Thu Jul 17, 10:16 )
└─< git: master>-[ $ ] ll
6424564 drwxr-xr-x nemo users 4.0 KB Thu Jul 17 09:59:46 2025  ./
6423502 drwxr-xr-x nemo users 4.0 KB Thu Jul 17 10:10:07 2025  ../
6586382 drwxr-xr-x nemo users 4.0 KB Thu Jul 17 10:08:15 2025  build/
6423630 .rw-r--r-- nemo users 1.7 KB Thu Jul 17 09:59:46 2025  CMakeLists.txt
6481503 .rwxr-xr-x nemo users 1.0 MB Mon Jul 14 21:27:54 2025  libsqlite3.so*
6424684 .rw-r--r-- nemo users 493 KB Sat Dec  1 20:38:26 2018  shell.c
6481523 .rwxr-xr-x nemo users 218 KB Mon Jul 14 21:28:07 2025  sqlite3*
6424658 .rw-r--r-- nemo users 7.4 MB Sat Dec  1 20:38:26 2018  sqlite3.c
6424686 .rw-r--r-- nemo users 543 KB Sat Dec  1 20:38:26 2018  sqlite3.h
6424685 .rw-r--r-- nemo users  33 KB Sat Dec  1 20:38:26 2018  sqlite3ext.h

┌─[ nemo on nautilus ] at [ ~/Стажировка InfoTecs/sqlite-amalgamation-3260000 ]-( Thu Jul 17, 10:16 )
└─< git: master>-[ $ ] cmake -S . -B build --fresh
-- The C compiler identification is GNU 15.1.1
-- Detecting C compiler ABI info
-- Detecting C compiler ABI info - done
-- Check for working C compiler: /usr/bin/cc - skipped
-- Detecting C compile features
-- Detecting C compile features - done
-- Configuring done (0.2s)
-- Generating done (0.0s)
-- Build files have been written to: /home/nemo/Стажировка InfoTecs/sqlite-amalgamation-3260000/build

┌─[ nemo on nautilus ] at [ ~/Стажировка InfoTecs/sqlite-amalgamation-3260000 ]-( Thu Jul 17, 10:18 )
└─< git: master>-[ $ ] cmake -S . -B build --fresh
-- The C compiler identification is GNU 15.1.1
-- Detecting C compiler ABI info
-- Detecting C compiler ABI info - done
-- Check for working C compiler: /usr/bin/cc - skipped
-- Detecting C compile features
-- Detecting C compile features - done
-- Configuring done (0.2s)
-- Generating done (0.0s)
-- Build files have been written to: /home/nemo/Стажировка InfoTecs/sqlite-amalgamation-3260000/build

┌─[ nemo on nautilus ] at [ ~/Стажировка InfoTecs/sqlite-amalgamation-3260000 ]-( Thu Jul 17, 10:18 )
└─< git: master>-[ $ ] cmake --build build --target sqlite3    
[ 50%] Building C object CMakeFiles/sqlite3.dir/sqlite3.c.o
[100%] Linking C shared library libsqlite3.so
[100%] Built target sqlite3

┌─[ nemo on nautilus ] at [ ~/Стажировка InfoTecs/sqlite-amalgamation-3260000 ]-( Thu Jul 17, 10:19 )
└─< git: master>-[ $ ] cmake --build build --target sqlite3_cli
[ 50%] Built target sqlite3
[ 75%] Building C object CMakeFiles/sqlite3_cli.dir/shell.c.o
[100%] Linking C executable sqlite3_cli
[100%] Built target sqlite3_cli

┌─[ nemo on nautilus ] at [ ~/Стажировка InfoTecs/sqlite-amalgamation-3260000 ]-( Thu Jul 17, 10:19 )
└─< git: master>-[ $ ] ./build/sqlite3_cli
SQLite version 3.26.0 2018-12-01 12:34:55
Enter ".help" for usage hints.
Connected to a transient in-memory database.
Use ".open FILENAME" to reopen on a persistent database.
sqlite> .exit

┌─[ nemo on nautilus ] at [ ~/Стажировка InfoTecs/sqlite-amalgamation-3260000 ]-( Thu Jul 17, 10:19 )
└─< git: master>-[ $ ] 
