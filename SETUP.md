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
| Исследователь | 14890 |
| Варден | 14891 |
| Визор | 14892 |
| Архитектор | 14893 |
