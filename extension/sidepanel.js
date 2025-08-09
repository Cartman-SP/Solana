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
                minAth: '',
                maxAth: '',
                minTokens: '',
                maxTokens: '',
                minMigrations: '',
                maxMigrations: ''
            }, (settings) => {
                let filteredTokens = tokens.filter(token => {
                    // Фильтр по ATH (диапазон)
                    if (settings.minAth !== '' || settings.maxAth !== '') {
                        const athValue = token.ath === 'N/A' ? 0 : parseFloat(token.ath) || 0;
                        const minAth = settings.minAth !== '' ? parseFloat(settings.minAth) : 0;
                        const maxAth = settings.maxAth !== '' ? parseFloat(settings.maxAth) : Infinity;
                        
                        if (athValue < minAth || athValue > maxAth) {
                            return false;
                        }
                    }
                    
                    // Фильтр по количеству токенов (диапазон)
                    if (settings.minTokens !== '' || settings.maxTokens !== '') {
                        const tokensValue = token.total_tokens === 'N/A' ? 0 : parseInt(token.total_tokens) || 0;
                        const minTokens = settings.minTokens !== '' ? parseInt(settings.minTokens) : 0;
                        const maxTokens = settings.maxTokens !== '' ? parseInt(settings.maxTokens) : Infinity;
                        
                        if (tokensValue < minTokens || tokensValue > maxTokens) {
                            return false;
                        }
                    }
                    
                    // Фильтр по проценту миграций (диапазон)
                    if (settings.minMigrations !== '' || settings.maxMigrations !== '') {
                        const migrationsValue = token.migrations === 'N/A' ? 0 : parseFloat(token.migrations) || 0;
                        const minMigrations = settings.minMigrations !== '' ? parseFloat(settings.minMigrations) : 0;
                        const maxMigrations = settings.maxMigrations !== '' ? parseFloat(settings.maxMigrations) : 100;
                        
                        if (migrationsValue < minMigrations || migrationsValue > maxMigrations) {
                            return false;
                        }
                    }
                    
                    return true;
                });
                
                resolve(filteredTokens);
            });
        });
    }
    
    removeToken(data) {
        const index = this.tokens.findIndex(token => 
            token.mint === data.mint && token.timestamp === data.timestamp
        );
        
        if (index !== -1) {
            this.tokens.splice(index, 1);
            this.renderTokens();
        }
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
        
        // Отображаем токены в зависимости от направления потока
        let tokensToRender = filteredTokens;
        if (this.flowDirection === 'top') {
            // От новых к старым (новые сверху)
            tokensToRender = [...filteredTokens].reverse();
        } else {
            // От старых к новым (новые снизу)
            tokensToRender = filteredTokens;
        }
        
        container.innerHTML = tokensToRender.map((token) => this.createTokenCard(token)).join('');
    }
    
    createTokenCard(token, isNew = false) {
        const shortMint = token.mint.length > 12 ? 
            token.mint.substring(0, 6) + '...' + token.mint.substring(token.mint.length - 6) : 
            token.mint;
            
        const shortUser = token.user.length > 12 ? 
            token.user.substring(0, 6) + '...' + token.user.substring(token.user.length - 6) : 
            token.user;
        
        // Функция для замены N/A на анимированный спиннер
        const formatValue = (value) => {
            if (value === 'N/A' || value === null || value === undefined) {
                return '<span class="loading-spinner"></span>';
            }
            return value;
        };
        
        // Создаем HTML для последних токенов
        let recentTokensHtml = '';
        if (token.recent_tokens && token.recent_tokens.length > 0) {
            recentTokensHtml = `
                <div class="recent-tokens">
                    <div class="recent-tokens-label">Последние токены:</div>
                    <div class="recent-tokens-list">
                        ${token.recent_tokens.map(rt => `
                            <div class="recent-token-item">
                                <span class="recent-token-name">${rt.name}</span>
                                <span class="recent-token-ath">ATH: ${rt.ath}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }
        
        // Определяем классы для токена
        let cardClasses = (isNew || token.isNew) ? 'new-token' : '';
        if (token.user_whitelisted) {
            cardClasses += ' whitelist';
        }
        
        return `
            <div class="token-card ${cardClasses}" data-mint="${token.mint}" data-timestamp="${token.timestamp}">
                <div class="token-header">
                    <div class="token-name">${formatValue(token.name)}</div>
                    <div class="token-symbol">${formatValue(token.symbol)}</div>
                    <button class="remove-token-btn" data-mint="${token.mint}" data-timestamp="${token.timestamp}">×</button>
                </div>
                
                <div class="token-info">
                    <div class="info-item">
                        <div class="info-label">Total Tokens</div>
                        <div class="info-value highlight">${formatValue(token.total_tokens)}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">ATH</div>
                        <div class="info-value highlight">${formatValue(token.ath)}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Migrations</div>
                        <div class="info-value">${formatValue(token.migrations)}%</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Source</div>
                        <div class="info-value">${formatValue(token.source)}</div>
                    </div>
                </div>
                
                ${recentTokensHtml}
                
                <div class="token-addresses">
                    <div class="address-item">
                        <div class="address-label">Token</div>
                        <div class="address-value" title="${token.mint}">${shortMint}</div>
                    </div>
                    <div class="address-item">
                        <div class="address-label">User</div>
                        <div class="address-value" title="${token.user}">${shortUser}</div>
                    </div>
                </div>
                
                <div class="token-actions">
                    <button class="action-button open" data-mint="${token.mint}">
                        Open
                    </button>
                    <button class="action-button blacklist" data-token="${token.mint}">
                        Blacklist
                    </button>
                    <button class="action-button whitelist" data-token="${token.mint}">
                        Whitelist
                    </button>
                </div>
                
                <div class="timestamp">${token.timestamp}</div>
            </div>
        `;
    }
    
    blacklistUser(tokenAddress, button) {
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
    }
    
    whitelistUser(tokenAddress, button) {
        const originalText = button.textContent;
        
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
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                button.textContent = 'Whitelisted!';
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