# ------------------ Docker-образ на стажировку ------------------
FROM debian:bookworm-slim
LABEL maintainer="Aleksandr Belous"

# 1. Инструменты
RUN apt-get update -y; \
    apt-get install -y --no-install-recommends build-essential cmake moreutils apt-utils; \
    rm -rf /var/lib/apt/lists/*

# 2. Копируем проект
WORKDIR /src
COPY . .

# 3. Сборка и установка
RUN set -eux; \
    ts=$(date +'%Y-%m-%d_%H-%M-%S'); \
    mkdir -p build; \
    cmake -S . -B build --fresh -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=Release --log-level=VERBOSE --log-context 2>&1 | tee "build/configure_$ts.log"; \
    cmake --build build --target sqlite3 VERBOSE=1 2>&1 | tee "build/build_$ts.log"; \
    cmake --build build --target sqlite3_cli VERBOSE=1 2>&1 | tee -a "build/build_$ts.log"; \
    cmake --build build --target install 2>&1 | tee "build/install_$ts.log"

# 4. Точка входа
CMD ["/bin/bash"]
