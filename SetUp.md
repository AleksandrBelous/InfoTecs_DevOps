gcc -fPIC -shared sqlite3.c -lpthread -ldl -lm -o libsqlite3.so

gcc shell.c -I ./ -L ./ -lsqlite3 -lpthread -ldl -lm -Wl,-rpath,'$ORIGIN' -o sqlite3

./sqlite3 -batch <<< 'select sqlite_version();'

ldd ./sqlite3 | grep libsqlite3.so