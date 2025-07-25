# Документация PenaltyControlAssist

Эта директория содержит документацию для проекта PenaltyControlAssist, организованную в формате [mdBook](https://rust-lang.github.io/mdBook/).

## Структура документации

- `src/` - исходные файлы Markdown
  - `SUMMARY.md` - оглавление документации
  - `index.md` - документация для пользователей
  - `code.md` - документация для разработчиков
  - `images/` - изображения, используемые в документации
- `book.toml` - конфигурационный файл mdBook

## Локальная сборка документации

Для локальной сборки документации необходимо установить mdBook:

```bash
# Установка через Cargo (требуется Rust)
cargo install mdbook

# Или скачать бинарный файл с GitHub:
# https://github.com/rust-lang/mdBook/releases
```

После установки mdBook выполните следующие команды:

```bash
# Перейдите в директорию docs
cd docs

# Соберите документацию
mdbook build

# Для запуска локального сервера с документацией
mdbook serve --open
```

Собранная документация будет доступна в директории `docs/book/`.

## Интеграция с CI

Для автоматической сборки документации в CI можно использовать GitHub Actions. Пример конфигурации:

```yaml
name: Build and Deploy Documentation

on:
  push:
    branches: [ main ]
    paths:
      - 'docs/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup mdBook
        uses: peaceiris/actions-mdbook@v1
        with:
          mdbook-version: 'latest'
      
      - name: Build Documentation
        run: |
          cd docs
          mdbook build
      
      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./docs/book
```

## Настройка документации

Настройки mdBook находятся в файле `book.toml`. Подробнее о возможных настройках можно узнать в [официальной документации mdBook](https://rust-lang.github.io/mdBook/format/configuration/index.html).
