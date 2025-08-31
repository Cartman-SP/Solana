# 🚀 IPFS Настройка для Solana Token Tracker

## 📋 Обзор

Этот проект использует IPFS для загрузки метаданных токенов. IPFS (InterPlanetary File System) - это распределенная файловая система, которая позволяет получать данные быстрее и надежнее, чем через обычные HTTP gateways.

## 🔧 Установка IPFS

### 1. Установка IPFS CLI

**macOS:**
```bash
brew install ipfs
```

**Ubuntu/Debian:**
```bash
wget https://dist.ipfs.io/go-ipfs/v0.20.0/go-ipfs_v0.20.0_linux-amd64.tar.gz
tar -xvzf go-ipfs_v0.20.0_linux-amd64.tar.gz
cd go-ipfs
sudo bash install.sh
```

**Windows:**
Скачайте с [ipfs.io](https://ipfs.io/docs/install/)

### 2. Инициализация IPFS

```bash
# Инициализируем IPFS node
ipfs init

# Запускаем IPFS daemon
ipfs daemon
```

### 3. Настройка API

```bash
# Проверяем текущие настройки API
ipfs config Addresses.API

# Устанавливаем API на стандартный порт (если нужно)
ipfs config Addresses.API /ip4/127.0.0.1/tcp/5001

# Устанавливаем Gateway (если нужно)
ipfs config Addresses.Gateway /ip4/127.0.0.1/tcp/8080
```

## 🧪 Тестирование подключения

Запустите тестовый скрипт:

```bash
cd backend/flip
python test_ipfs.py
```

Этот скрипт проверит:
- ✅ Подключение к IPFS API
- ✅ Версию IPFS
- ✅ Количество подключенных пиров
- ✅ Работу IPFS gateways

## 🚀 Запуск приложения

### 1. Убедитесь, что IPFS daemon запущен

```bash
# В отдельном терминале
ipfs daemon
```

### 2. Запустите основное приложение

```bash
cd backend/flip
python pumpfun_create.py
```

## 🔍 Отладка проблем

### Проблема: "IPFS API недоступен"

**Решение:**
1. Проверьте, запущен ли IPFS daemon:
   ```bash
   ps aux | grep ipfs
   ```

2. Проверьте порт API:
   ```bash
   ipfs config Addresses.API
   ```

3. Проверьте firewall:
   ```bash
   # Ubuntu/Debian
   sudo ufw status
   
   # macOS
   sudo pfctl -s rules
   ```

### Проблема: "Все методы IPFS не сработали"

**Решение:**
1. Проверьте подключение к IPFS сети:
   ```bash
   ipfs swarm peers
   ```

2. Проверьте статус node:
   ```bash
   ipfs id
   ```

3. Попробуйте добавить bootstrap nodes:
   ```bash
   ipfs bootstrap add /dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN
   ```

## 📊 Мониторинг

### Проверка статуса IPFS

```bash
# Статус daemon
ipfs stats repo

# Подключенные пиры
ipfs swarm peers

# Размер репозитория
ipfs repo stat
```

### Логи приложения

Приложение выводит детальные логи:
- 🚀 Попытки подключения к IPFS API
- ✅ Успешные подключения
- ❌ Ошибки подключения
- 📦 Размер полученных данных
- 🌐 Использование gateways

## 🔄 Fallback стратегия

Если IPFS API недоступен, система автоматически использует HTTP gateways:

1. **Локальный gateway** (http://127.0.0.1:8180)
2. **ipfs.io** (https://ipfs.io)
3. **Pinata** (https://gateway.pinata.cloud)
4. **Cloudflare** (https://cloudflare-ipfs.com)

## 📈 Производительность

- **IPFS API**: ~100-500ms (самый быстрый)
- **Локальный gateway**: ~200-1000ms
- **Внешние gateways**: ~500-3000ms

## 🆘 Поддержка

Если проблемы продолжаются:

1. Проверьте логи приложения
2. Запустите `test_ipfs.py`
3. Проверьте статус IPFS daemon
4. Убедитесь, что порты не заблокированы

## 🔗 Полезные ссылки

- [IPFS Documentation](https://docs.ipfs.io/)
- [IPFS Configuration](https://docs.ipfs.io/reference/cli/#ipfs-config)
- [IPFS Troubleshooting](https://docs.ipfs.io/how-to/troubleshoot/) 