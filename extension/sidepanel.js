class TokenMonitor {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.tokens = [];
        this.maxTokens = 50; // Увеличиваем максимальное количество токенов
        this.flowDirection = 'top'; // 'top' - новые сверху, 'bottom' - новые снизу
        this.pingInterval = null;
        this.lastPingTime = 0;
        this.pingHistory = [];
        this.autobuyOpenedMints = new Set(); // защита от повторных открытий вкладок
        
        this.init();
    }
    
    init() {
        this.connectWebSocket();
        this.updateConnectionStatus();
        this.setupEventListeners();
        this.loadFlowDirectionSetting();
    }
    
    connectWebSocket() {
        try {
            this.ws = new WebSocket('ws://goodelivery.ru:8765');
            
            this.ws.onopen = () => {
                console.log('WebSocket соединение установлено');
                this.isConnected = true;
                this.updateConnectionStatus();
                this.startPingMeasurement();
            };
            
            this.ws.onmessage = (event) => {
                console.log('Получено сообщение от WebSocket:', event.data);
                try {
                    const data = JSON.parse(event.data);
                    console.log('Данные успешно распарсены:', data);
                    
                    // Проверяем, является ли это ответом на пинг
                    if (data.type === 'pong') {
                        this.handlePong(data);
                    } else {
                        this.handleTokenData(data);
                    }
                } catch (error) {
                    console.error('Ошибка парсинга данных:', error);
                }
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket соединение закрыто');
                this.isConnected = false;
                this.updateConnectionStatus();
                this.stopPingMeasurement();
                
                // Переподключение через 5 секунд
                setTimeout(() => {
                    this.connectWebSocket();
                }, 5000);
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket ошибка:', error);
                this.isConnected = false;
                this.updateConnectionStatus();
                this.stopPingMeasurement();
            };
            
        } catch (error) {
            console.error('Ошибка подключения к WebSocket:', error);
            this.isConnected = false;
            this.updateConnectionStatus();
            this.stopPingMeasurement();
        }
    }
    
    startPingMeasurement() {
        this.stopPingMeasurement(); // Останавливаем предыдущий интервал
        
        this.pingInterval = setInterval(() => {
            if (this.isConnected && this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.sendPing();
            }
        }, 5000); // Измеряем пинг каждые 5 секунд
    }
    
    stopPingMeasurement() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    }
    
    sendPing() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.lastPingTime = Date.now();
            this.ws.send(JSON.stringify({
                type: 'ping',
                timestamp: this.lastPingTime
            }));
        }
    }
    
    handlePong(data) {
        const pingTime = Date.now() - this.lastPingTime;
        this.pingHistory.push(pingTime);
        
        // Ограничиваем историю пинга до 10 последних измерений
        if (this.pingHistory.length > 10) {
            this.pingHistory = this.pingHistory.slice(-10);
        }
        
        this.updatePingStatus();
    }
    
    updatePingStatus() {
        const pingElement = document.getElementById('ping-status');
        
        if (this.pingHistory.length === 0) {
            pingElement.textContent = '—';
            pingElement.className = 'ping-indicator';
            return;
        }
        
        // Вычисляем средний пинг
        const avgPing = Math.round(this.pingHistory.reduce((sum, ping) => sum + ping, 0) / this.pingHistory.length);
        
        pingElement.textContent = `${avgPing}ms`;
        
        // Определяем качество пинга
        if (avgPing < 100) {
            pingElement.className = 'ping-indicator good';
        } else if (avgPing < 300) {
            pingElement.className = 'ping-indicator warning';
        } else {
            pingElement.className = 'ping-indicator poor';
        }
    }
    
    updateConnectionStatus() {
        const statusElement = document.getElementById('connection-status');
        if (this.isConnected) {
            statusElement.textContent = 'Подключено';
            statusElement.className = 'status-indicator online';
        } else {
            statusElement.textContent = 'Отключено';
            statusElement.className = 'status-indicator offline';
            // Сбрасываем пинг при отключении
            const pingElement = document.getElementById('ping-status');
            pingElement.textContent = '—';
            pingElement.className = 'ping-indicator';
        }
    }
    
    handleTokenData(data) {
        // Проверяем, не добавлен ли уже этот токен
        const existingToken = this.tokens.find(token => 
            token.mint === data.mint && token.timestamp === data.timestamp
        );
        
        if (existingToken) {
            return; // Токен уже существует, не добавляем повторно
        }
        
        // Если autobuy=true — открываем новую вкладку (однократно на mint)
        //if (data.autobuy === true && data.mint && !this.autobuyOpenedMints.has(data.mint)) {
        //    this.autobuyOpenedMints.add(data.mint);
        //    this.openAutobuyTab(data.mint);
        //}
        //
        // Токены всегда добавляются в конец
        const tokenWithData = {
            ...data,
            createdAt: Date.now(),
            isNew: true // Флаг для анимации
        };
        
        this.tokens.push(tokenWithData);
        
        // Ограничиваем количество токенов
        if (this.tokens.length > this.maxTokens) {
            this.tokens = this.tokens.slice(-this.maxTokens);
        }
        
        this.renderTokens();
        
        // Убираем флаг isNew через 500ms (время анимации)
        setTimeout(() => {
            tokenWithData.isNew = false;
        }, 500);
    }
    
    applyFilters(tokens) {
        return new Promise((resolve) => {
            chrome.storage.sync.get({
                // Фильтры пользователя
                minUserAth: '',
                maxUserAth: '',
                minUserTotalTrans: '',
                maxUserTotalTrans: '',
                minUserTokens: '',
                maxUserTokens: '',
                minUserMigrations: '',
                maxUserMigrations: '',
                userWhitelisted: false,
                userBlacklisted: false,
                minFollowers: '',
                
                // Фильтры Twitter
                minTwitterAth: '',
                maxTwitterAth: '',
                minTwitterTotalTrans: '',
                maxTwitterTotalTrans: '',
                minTwitterTokens: '',
                maxTwitterTokens: '',
                minTwitterMigrations: '',
                maxTwitterMigrations: '',
                twitterWhitelisted: false,
                twitterBlacklisted: false,
                
                // Дополнительные настройки
                sourceFilter: '',
                showOnlyNew: false
            }, (settings) => {
                let filteredTokens = tokens.filter(token => {
                    // Фильтр по источнику
                    if (settings.sourceFilter && token.source !== settings.sourceFilter) {
                        return false;
                    }
                    
                    // Фильтр по времени (только новые токены)
                    if (settings.showOnlyNew) {
                        const tokenTime = new Date(`2000-01-01 ${token.timestamp}`);
                        const currentTime = new Date();
                        const timeDiff = (currentTime - tokenTime) / (1000 * 60 * 60); // разница в часах
                        if (timeDiff > 1) {
                            return false;
                        }
                    }
                    
                    // Фильтр по количеству подписчиков
                    if (settings.minFollowers && token.followers) {
                        const followers = parseInt(token.followers) || 0;
                        if (followers < parseInt(settings.minFollowers)) {
                            return false;
                        }
                    }
                    
                    // Фильтры пользователя
                    if (settings.userWhitelisted && !token.user_whitelisted) {
                        return false;
                    }
                    
                    if (settings.userBlacklisted && token.user_blacklisted) {
                        return false;
                    }
                    
                    if (settings.minUserAth !== '' || settings.maxUserAth !== '') {
                        const userAth = parseFloat(token.user_ath) || 0;
                        const minUserAth = settings.minUserAth !== '' ? parseFloat(settings.minUserAth) : 0;
                        const maxUserAth = settings.maxUserAth !== '' ? parseFloat(settings.maxUserAth) : Infinity;
                        
                        if (userAth < minUserAth || userAth > maxUserAth) {
                            return false;
                        }
                    }

                    if (settings.minUserTotalTrans !== '' || settings.maxUserTotalTrans !== '') {
                        const userTotalTrans = parseFloat(token.user_total_trans) || 0;
                        const minUserTotalTrans = settings.minUserTotalTrans !== '' ? parseFloat(settings.minUserTotalTrans) : 0;
                        const maxUserTotalTrans = settings.maxUserTotalTrans !== '' ? parseFloat(settings.maxUserTotalTrans) : Infinity;
                        if (userTotalTrans < minUserTotalTrans || userTotalTrans > maxUserTotalTrans) {
                            return false;
                        }
                    }
                    
                    if (settings.minUserTokens !== '' || settings.maxUserTokens !== '') {
                        const userTokens = parseInt(token.user_total_tokens) || 0;
                        const minUserTokens = settings.minUserTokens !== '' ? parseInt(settings.minUserTokens) : 0;
                        const maxUserTokens = settings.maxUserTokens !== '' ? parseInt(settings.maxUserTokens) : Infinity;
                        
                        if (userTokens < minUserTokens || userTokens > maxUserTokens) {
                            return false;
                        }
                    }
                    
                    if (settings.minUserMigrations !== '' || settings.maxUserMigrations !== '') {
                        const userMigrations = parseFloat(token.user_migrations) || 0;
                        const minUserMigrations = settings.minUserMigrations !== '' ? parseFloat(settings.minUserMigrations) : 0;
                        const maxUserMigrations = settings.maxUserMigrations !== '' ? parseFloat(settings.maxUserMigrations) : 100;
                        
                        if (userMigrations < minUserMigrations || userMigrations > maxUserMigrations) {
                            return false;
                        }
                    }
                    
                    // Фильтры Twitter
                    if (settings.twitterWhitelisted && !token.twitter_whitelisted) {
                        return false;
                    }
                    
                    if (settings.twitterBlacklisted && token.twitter_blacklisted) {
                        return false;
                    }
                    
                    if (settings.minTwitterAth !== '' || settings.maxTwitterAth !== '') {
                        const twitterAth = parseFloat(token.twitter_ath) || 0;
                        const minTwitterAth = settings.minTwitterAth !== '' ? parseFloat(settings.minTwitterAth) : 0;
                        const maxTwitterAth = settings.maxTwitterAth !== '' ? parseFloat(settings.maxTwitterAth) : Infinity;
                        
                        if (twitterAth < minTwitterAth || twitterAth > maxTwitterAth) {
                            return false;
                        }
                    }

                    if (settings.minTwitterTotalTrans !== '' || settings.maxTwitterTotalTrans !== '') {
                        const twitterTotalTrans = parseFloat(token.twitter_total_trans) || 0;
                        const minTwitterTotalTrans = settings.minTwitterTotalTrans !== '' ? parseFloat(settings.minTwitterTotalTrans) : 0;
                        const maxTwitterTotalTrans = settings.maxTwitterTotalTrans !== '' ? parseFloat(settings.maxTwitterTotalTrans) : Infinity;
                        if (twitterTotalTrans < minTwitterTotalTrans || twitterTotalTrans > maxTwitterTotalTrans) {
                            return false;
                        }
                    }
                    
                    if (settings.minTwitterTokens !== '' || settings.maxTwitterTokens !== '') {
                        const twitterTokens = parseInt(token.twitter_total_tokens) || 0;
                        const minTwitterTokens = settings.minTwitterTokens !== '' ? parseInt(settings.minTwitterTokens) : 0;
                        const maxTwitterTokens = settings.maxTwitterTokens !== '' ? parseInt(settings.maxTwitterTokens) : Infinity;
                        
                        if (twitterTokens < minTwitterTokens || twitterTokens > maxTwitterTokens) {
                            return false;
                        }
                    }
                    
                    if (settings.minTwitterMigrations !== '' || settings.maxTwitterMigrations !== '') {
                        const twitterMigrations = parseFloat(token.twitter_migrations) || 0;
                        const minTwitterMigrations = settings.minTwitterMigrations !== '' ? parseFloat(settings.minTwitterMigrations) : 0;
                        const maxTwitterMigrations = settings.maxTwitterMigrations !== '' ? parseFloat(settings.maxTwitterMigrations) : 100;
                        
                        if (twitterMigrations < minTwitterMigrations || twitterMigrations > maxTwitterMigrations) {
                            return false;
                        }
                    }
                    
                    return true;
                });
                
                resolve(filteredTokens);
            });
        });
    }
    
    removeToken({ mint, timestamp }) {
        // Удаляем токен из массива и перерисовываем
        this.tokens = this.tokens.filter(t => t.mint !== mint || t.timestamp !== timestamp);
        this.renderTokens();
    }
    
    clearAllTokens() {
        this.tokens = [];
        this.renderTokens();
    }
    
    toggleFlowDirection() {
        this.flowDirection = this.flowDirection === 'top' ? 'bottom' : 'top';
        this.updateFlowDirectionUI();
        
        // Перерендериваем токены с новым порядком
        this.renderTokens();
        
        // Сохраняем настройку в chrome.storage
        chrome.storage.sync.set({
            flowDirection: this.flowDirection
        });
    }
    
    updateFlowDirectionUI() {
        const flowBtn = document.getElementById('flow-direction-btn');
        const flowIcon = flowBtn.querySelector('.flow-icon');
        
        if (this.flowDirection === 'top') {
            flowBtn.classList.remove('active');
            flowBtn.title = 'От новых к старым (нажмите для переключения)';
        } else {
            flowBtn.classList.add('active');
            flowBtn.title = 'От старых к новым (нажмите для переключения)';
        }
    }
    
    loadFlowDirectionSetting() {
        chrome.storage.sync.get({
            flowDirection: 'top' // значение по умолчанию
        }, (settings) => {
            this.flowDirection = settings.flowDirection;
            this.updateFlowDirectionUI();
            
            // Перерендериваем токены с сохраненным направлением
            this.renderTokens();
        });
    }
    
    async renderTokens() {
        const container = document.getElementById('tokens-container');
        const noData = document.getElementById('no-data');
        
        if (this.tokens.length === 0) {
            container.innerHTML = '';
            noData.style.display = 'flex';
            return;
        }
        
        // Применяем фильтры
        const filteredTokens = await this.applyFilters(this.tokens);
        
        if (filteredTokens.length === 0) {
            container.innerHTML = '';
            noData.style.display = 'flex';
            noData.querySelector('p').textContent = 'Нет токенов, соответствующих фильтрам';
            return;
        }
        
        noData.style.display = 'none';
        
        // Очищаем контейнер
        container.innerHTML = '';
        
        // Сортируем токены по направлению потока
        const sortedTokens = [...filteredTokens];
        if (this.flowDirection === 'top') {
            sortedTokens.reverse(); // Новые сверху
        }
        
        // Рендерим каждый токен
        sortedTokens.forEach(token => {
            const tokenElement = this.createTokenElement(token);
            container.appendChild(tokenElement);
        });
    }
    
    createTokenElement(token) {
        const template = document.getElementById('token-template');
        const tokenElement = template.content.cloneNode(true);
        const card = tokenElement.querySelector('.token-card');
        // Визуальное выделение для autobuy
        if (token.autobuy === true) {
            card.classList.add('autobuy-token');
        }
        
        // Заполняем основную информацию
        tokenElement.querySelector('.token-symbol').textContent = token.symbol || 'N/A';
        tokenElement.querySelector('.token-source').textContent = token.source || 'Unknown';
        tokenElement.querySelector('.token-time').textContent = token.timestamp || 'N/A';
        tokenElement.querySelector('.token-name').textContent = token.user_name || 'N/A';
        
        // Вставляем маркер AUTOBUY слева от source на одной линии
        const source = tokenElement.querySelector('.token-source');
        if (token.autobuy === true && source) {
            // Создаем flex-контейнер
            const flexWrap = document.createElement('div');
            flexWrap.style.display = 'flex';
            flexWrap.style.alignItems = 'center';
            // Создаем label
            const autobuyMark = document.createElement('span');
            autobuyMark.className = 'autobuy-label';
            autobuyMark.textContent = '🚀 AUTOBUY';
            autobuyMark.style = 'background:#ff8c00;color:white;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700;margin-right:8px;vertical-align:middle;';
            flexWrap.appendChild(autobuyMark);
            flexWrap.appendChild(source.cloneNode(true));
            source.replaceWith(flexWrap);
        }
        
        // Заполняем данные пользователя
        tokenElement.querySelector('.user-ath').textContent = this.formatNumber(token.user_ath);
        tokenElement.querySelector('.user-total-trans').textContent = this.formatNumber(token.user_total_trans);
        tokenElement.querySelector('.user-tokens').textContent = this.formatNumber(token.user_total_tokens);
        tokenElement.querySelector('.user-migrations').textContent = `${this.formatNumber(token.user_migrations)}%`;
        
        // Показываем/скрываем бейджи списков пользователя
        if (token.user_whitelisted) {
            tokenElement.querySelector('.user-lists .whitelist').style.display = 'inline-block';
        }
        if (token.user_blacklisted) {
            tokenElement.querySelector('.user-lists .blacklist').style.display = 'inline-block';
        }
        
        // Заполняем данные Twitter
        tokenElement.querySelector('.twitter-ath').textContent = this.formatNumber(token.twitter_ath);
        tokenElement.querySelector('.twitter-total-trans').textContent = this.formatNumber(token.twitter_total_trans);
        tokenElement.querySelector('.twitter-tokens').textContent = this.formatNumber(token.twitter_total_tokens);
        tokenElement.querySelector('.twitter-migrations').textContent = `${this.formatNumber(token.twitter_migrations)}%`;
        
        // Показываем/скрываем бейджи списков Twitter
        if (token.twitter_whitelisted) {
            tokenElement.querySelector('.twitter-lists .whitelist').style.display = 'inline-block';
        }
        if (token.twitter_blacklisted) {
            tokenElement.querySelector('.twitter-lists .blacklist').style.display = 'inline-block';
        }
        
        // Заполняем адреса
        tokenElement.querySelector('.token-mint').textContent = token.mint ? `${token.mint.slice(0, 8)}...` : 'N/A';
        tokenElement.querySelector('.user-address').textContent = token.user ? `${token.user.slice(0, 8)}...` : 'N/A';
        
        // Заполняем Twitter информацию
        tokenElement.querySelector('.twitter-name').textContent = token.twitter_name || 'N/A';
        tokenElement.querySelector('.twitter-followers').textContent = token.followers ? `${this.formatNumber(token.followers)}` : 'N/A';
        
        // Заполняем Recent Tokens
        this.populateRecentTokens(tokenElement, '.user-recent-tokens', token.user_recent_tokens);
        this.populateRecentTokens(tokenElement, '.twitter-recent-tokens', token.twitter_recent_tokens);
        
        // Настраиваем кнопки действий
        this.setupTokenActions(tokenElement, token);
        
        // Добавляем анимацию для новых токенов
        if (token.isNew) {
            tokenElement.querySelector('.token-card').classList.add('new-token');
        }
        
        // Настраиваем remove-token-btn
        const removeBtn = tokenElement.querySelector('.remove-token-btn');
        if (removeBtn) {
            removeBtn.setAttribute('data-mint', token.mint || '');
            removeBtn.setAttribute('data-timestamp', token.timestamp || '');
            removeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.removeToken({ mint: token.mint, timestamp: token.timestamp });
                // Удаляем из DOM
                const card = e.target.closest('.token-card');
                if (card) card.remove();
            });
        }
        
        return tokenElement;
    }
    
    populateRecentTokens(tokenElement, selector, recentTokens) {
        const container = tokenElement.querySelector(selector);
        if (!container) return;
        
        container.innerHTML = '';
        
        if (recentTokens && recentTokens.length > 0) {
            recentTokens.forEach(token => {
                const tokenItem = document.createElement('div');
                tokenItem.className = 'recent-token-item';
                tokenItem.innerHTML = `
                    <span class="recent-token-name">${token.name}</span>
                    <span class="recent-token-ath">ATH: ${this.formatNumber(token.ath)}</span>
                    <span class="recent-token-trans">TT: ${this.formatNumber(token.total_trans)}</span>
                `;
                container.appendChild(tokenItem);
            });
        } else {
            const noTokens = document.createElement('div');
            noTokens.className = 'recent-token-item';
            noTokens.innerHTML = '<span class="recent-token-name">Нет токенов</span>';
            container.appendChild(noTokens);
        }
    }
    
    setupTokenActions(tokenElement, token) {
        // Кнопка Open
        tokenElement.querySelector('.open').addEventListener('click', () => {
            window.open(`https://trade.padre.gg/trade/solana/${token.mint}`, '_blank');
        });
        
        // Кнопка Blacklist
        tokenElement.querySelector('.blacklist').addEventListener('click', () => {
            this.blacklistUser(token.mint, tokenElement.querySelector('.blacklist'));
        });
        
        // Кнопка Whitelist
        tokenElement.querySelector('.whitelist').addEventListener('click', () => {
            this.whitelistUser(token.mint, tokenElement.querySelector('.whitelist'));
        });
    }
    
    formatNumber(value) {
        if (value === null || value === undefined || value === '') {
            return 'N/A';
        }
        
        const num = parseFloat(value);
        if (isNaN(num)) {
            return 'N/A';
        }
        
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        } else {
            return Math.round(num).toString();
        }
    }
    
    showToast(message) {
        // Создаем временное уведомление
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 3000);
    }
    
    setupEventListeners() {
        // Обработчики для кнопок в токенах
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('action-button')) {
                if (e.target.classList.contains('open')) {
                    const mint = e.target.dataset.mint;
                    window.open(`https://trade.padre.gg/trade/solana/${mint}`, '_blank');
                } else if (e.target.classList.contains('blacklist')) {
                    const token = e.target.dataset.token;
                    this.blacklistUser(token, e.target);
                } else if (e.target.classList.contains('whitelist')) {
                    const token = e.target.dataset.token;
                    this.whitelistUser(token, e.target);
                }
            }
            
            // Обработчик для кнопки удаления токена
            if (e.target.classList.contains('remove-token-btn')) {
                const mint = e.target.dataset.mint;
                const timestamp = e.target.dataset.timestamp;
                this.removeToken({ mint, timestamp });
            }
            
            // Обработчик для кнопки очистки всех токенов
            if (e.target.id === 'clear-all-btn') {
                this.clearAllTokens();
            }
            
            // Обработчик для кнопки направления потока
            if (e.target.id === 'flow-direction-btn' || e.target.closest('#flow-direction-btn')) {
                this.toggleFlowDirection();
            }
        });
        
        // Обработчик для кнопки переподключения
        document.addEventListener('click', (e) => {
            if (e.target.id === 'reconnect-btn') {
                this.reconnect();
            }
        });
    }
    
    reconnect() {
        if (this.ws) {
            this.ws.close();
        }
        this.connectWebSocket();
    }
    
    blacklistUser(tokenAddress, button) {
        const originalText = button.textContent;
        
        console.log('Blacklisting token:', tokenAddress);
        
        // Отключаем кнопку и показываем загрузку
        button.disabled = true;
        button.textContent = 'Loading...';
        
        fetch('https://goodelivery.ru/api/blacklist/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            mode: 'cors',
            credentials: 'omit',
            body: JSON.stringify({
                token_address: tokenAddress
            })
        })
        .then(response => {
            console.log('Blacklist response status:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('Blacklist response data:', data);
            if (data.success) {
                button.textContent = 'Blacklisted!';
                button.style.background = 'linear-gradient(90deg, #28a745 0%, #20c997 100%)';
                this.showToast('Токен добавлен в blacklist!');
                setTimeout(() => {
                    button.textContent = originalText;
                    button.disabled = false;
                    button.style.background = '';
                }, 2000);
            } else {
                button.textContent = 'Error!';
                button.style.background = 'linear-gradient(90deg, #dc3545 0%, #c82333 100%)';
                this.showToast(`Ошибка: ${data.error || 'Неизвестная ошибка'}`);
                setTimeout(() => {
                    button.textContent = originalText;
                    button.disabled = false;
                    button.style.background = '';
                }, 2000);
            }
        })
        .catch(error => {
            console.error('Blacklist error:', error);
            button.textContent = 'Error!';
            button.style.background = 'linear-gradient(90deg, #dc3545 0%, #c82333 100%)';
            this.showToast('Ошибка сети при добавлении в blacklist');
            setTimeout(() => {
                button.textContent = originalText;
                button.disabled = false;
                button.style.background = '';
            }, 2000);
        });
    }
    
    whitelistUser(tokenAddress, button) {
        const originalText = button.textContent;
        
        console.log('Whitelisting token:', tokenAddress);
        
        // Отключаем кнопку и показываем загрузку
        button.disabled = true;
        button.textContent = 'Loading...';
        
        fetch('https://goodelivery.ru/api/whitelist/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            mode: 'cors',
            credentials: 'omit',
            body: JSON.stringify({
                token_address: tokenAddress
            })
        })
        .then(response => {
            console.log('Whitelist response status:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('Whitelist response data:', data);
            if (data.success) {
                button.textContent = 'Whitelisted!';
                button.style.background = 'linear-gradient(90deg, #28a745 0%, #20c997 100%)';
                this.showToast('Токен добавлен в whitelist!');
                setTimeout(() => {
                    button.textContent = originalText;
                    button.disabled = false;
                    button.style.background = '';
                }, 2000);
            } else {
                button.textContent = 'Error!';
                button.style.background = 'linear-gradient(90deg, #dc3545 0%, #c82333 100%)';
                this.showToast(`Ошибка: ${data.error || 'Неизвестная ошибка'}`);
                setTimeout(() => {
                    button.textContent = originalText;
                    button.disabled = false;
                    button.style.background = '';
                }, 2000);
            }
        })
        .catch(error => {
            console.error('Whitelist error:', error);
            button.textContent = 'Error!';
            button.style.background = 'linear-gradient(90deg, #dc3545 0%, #c82333 100%)';
            this.showToast('Ошибка сети при добавлении в whitelist');
            setTimeout(() => {
                button.textContent = originalText;
                button.disabled = false;
                button.style.background = '';
            }, 2000);
        });
    }
    
    redirectMainWindow(mint) {
        console.log(`Попытка редиректа основного окна для токена: ${mint}`);
        
        // Получаем все вкладки и находим основное окно (не боковую панель)
        chrome.tabs.query({}, (tabs) => {
            console.log(`Найдено вкладок: ${tabs.length}`);
            
            // Ищем вкладку с основным окном (не боковой панелью)
            const mainTab = tabs.find(tab => 
                tab.url && 
                tab.url.includes('trade.padre.gg') && 
                !tab.url.includes('chrome-extension://')
            );
            
            if (mainTab) {
                console.log(`Найдена основная вкладка: ${mainTab.url}`);
                // Редиректим основное окно на страницу торговли
                const tradeUrl = `https://trade.padre.gg/trade/solana/${mint}`;
                chrome.tabs.update(mainTab.id, { url: tradeUrl }, (updatedTab) => {
                    if (chrome.runtime.lastError) {
                        console.error('Ошибка при обновлении вкладки:', chrome.runtime.lastError);
                    } else {
                        console.log(`Редирект основного окна на: ${tradeUrl}`);
                    }
                });
            } else {
                console.log('Основная вкладка не найдена, открываем новую');
                // Если основное окно не найдено, открываем новую вкладку
                chrome.tabs.create({ url: `https://trade.padre.gg/trade/solana/${mint}` }, (newTab) => {
                    if (chrome.runtime.lastError) {
                        console.error('Ошибка при создании новой вкладки:', chrome.runtime.lastError);
                    } else {
                        console.log(`Открыта новая вкладка с: https://trade.padre.gg/trade/solana/${mint}`);
                    }
                });
            }
        });
    }

    openAutobuyTab(mint) {
        const url = `https://trade.padre.gg/trade/solana/${mint}`;
        console.log(`Открываем новую вкладку для автобая: ${url}`);
        chrome.tabs.create({ url }, (newTab) => {
            if (chrome.runtime.lastError) {
                console.error('Ошибка при создании новой вкладки:', chrome.runtime.lastError);
            } else {
                console.log(`Открыта новая вкладка: ${url}`);
            }
        });
    }
}

// Глобальная функция для blacklist
window.blacklistUser = function(tokenAddress) {
    const button = event.target;
    const originalText = button.textContent;
    
    // Отключаем кнопку и показываем загрузку
    button.disabled = true;
    button.textContent = 'Loading...';
    
    fetch('https://goodelivery.ru/api/blacklist/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        },
        mode: 'cors',
        credentials: 'omit',
        body: JSON.stringify({
            token_address: tokenAddress
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            button.textContent = 'Blacklisted!';
            button.style.background = 'linear-gradient(90deg, #28a745 0%, #20c997 100%)';
            setTimeout(() => {
                button.textContent = originalText;
                button.disabled = false;
                button.style.background = '';
            }, 2000);
        } else {
            button.textContent = 'Error!';
            button.style.background = 'linear-gradient(90deg, #dc3545 0%, #c82333 100%)';
            setTimeout(() => {
                button.textContent = originalText;
                button.disabled = false;
                button.style.background = '';
            }, 2000);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        button.textContent = 'Error!';
        button.style.background = 'linear-gradient(90deg, #dc3545 0%, #c82333 100%)';
        setTimeout(() => {
            button.textContent = originalText;
            button.disabled = false;
            button.style.background = '';
        }, 2000);
    });
};


// Инициализация приложения
document.addEventListener('DOMContentLoaded', () => {
    new TokenMonitor();
}); 