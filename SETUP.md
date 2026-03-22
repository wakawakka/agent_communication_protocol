# Установка Agent Communication Protocol (AMB)

Межагентная коммуникация для Claude Code агентов.

## Установка

```bash
# Скопировать бинарник:
mkdir -p ~/bin
cp amb ~/bin/amb
chmod +x ~/bin/amb

# Добавить в PATH (.bashrc):
export PATH=$HOME/bin:$PATH
```

## Проверка

```bash
amb status
# Ожидаемый вывод: "AMB_PORT not set" (нормально вне сессии агента)
```

## Использование

AMB запускается автоматически каждым агентом при старте сессии:

```bash
export AMB_NAME=Архитектор
export AMB_PORT=14893
amb start
amb recv
```

Агенты и их порты:

| Агент | AMB_PORT |
|-------|:--------:|
| Архитектор | 14893 |
| Варден | 14894 |
| Исследователь | 14895 |
| Визор | 14896 |
| Коуч | 14897 |
