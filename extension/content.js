// Content script для замены блока на страницах trade.padre.gg и загрузки связанных кошельков

let walletsData = [];
let selectedWallets = new Set();

function createLoadingSpinner() {
    const spinner = document.createElement('div');
    spinner.className = 'wallet-loading-spinner';
    spinner.innerHTML = `
        <div class="spinner-ring"></div>
        <div class="spinner-text">Loading...</div>
    `;
    return spinner;
}

function createWalletCard(wallet) {
    const card = document.createElement('div');
    card.className = 'wallet-card';
    card.dataset.address = wallet.account_address;
    
    const isSelected = selectedWallets.has(wallet.account_address);
    if (isSelected) {
        card.classList.add('selected');
    }
    
    card.innerHTML = `
        <div class="wallet-header">
            <div class="wallet-address">
                <span class="address-text">${wallet.account_address}</span>
                <div class="wallet-actions">
                    <button class="copy-btn" title="Copy address">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                        </svg>
                    </button>
                    <button class="open-btn" title="Open in Solscan">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                            <polyline points="15,3 21,3 21,9"></polyline>
                            <line x1="10" y1="14" x2="21" y2="3"></line>
                        </svg>
                    </button>
                </div>
            </div>
        </div>
        <div class="wallet-details">
            ${wallet.account_label ? `<div class="wallet-label">${wallet.account_label}</div>` : ''}
            ${wallet.account_icon ? `<div class="wallet-icon"><img src="${wallet.account_icon}" alt="Icon" /></div>` : ''}
            ${wallet.account_tags && wallet.account_tags.length > 0 ? 
                `<div class="wallet-tags">${wallet.account_tags.map(tag => `<span class="tag">${tag}</span>`).join('')}</div>` : ''}
            ${wallet.account_type ? `<div class="wallet-type">Type: ${wallet.account_type}</div>` : ''}
            ${wallet.funded_by ? `
                <div class="funded-by">
                    <div class="funded-label">Funded by:</div>
                    <div class="funded-address">${wallet.funded_by.funded_by}</div>
                    ${wallet.funded_by.tx_hash ? `<div class="tx-hash">TX: ${wallet.funded_by.tx_hash.substring(0, 16)}...</div>` : ''}
                    ${wallet.funded_by.block_time ? `<div class="block-time">Block: ${new Date(wallet.funded_by.block_time * 1000).toLocaleString()}</div>` : ''}
                </div>
            ` : ''}
        </div>
    `;
    
    // Добавляем обработчики событий
    card.addEventListener('click', (e) => {
        if (!e.target.closest('.wallet-actions')) {
            toggleWalletSelection(wallet.account_address, card);
        }
    });
    
    // Копирование адреса
    card.querySelector('.copy-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        navigator.clipboard.writeText(wallet.account_address);
        showToast('Address copied!');
    });
    
    // Открытие в Solscan
    card.querySelector('.open-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        window.open(`https://solscan.io/account/${wallet.account_address}`, '_blank');
    });
    
    return card;
}

function toggleWalletSelection(address, card) {
    if (selectedWallets.has(address)) {
        selectedWallets.delete(address);
        card.classList.remove('selected');
    } else {
        selectedWallets.add(address);
        card.classList.add('selected');
    }
    
    updateSendButton();
}

function updateSendButton() {
    const sendButton = document.querySelector('.send-to-server-btn');
    if (sendButton) {
        sendButton.disabled = selectedWallets.size === 0;
        sendButton.textContent = `Send to server (${selectedWallets.size})`;
    }
}

function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('show');
    }, 100);
    
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            document.body.removeChild(toast);
        }, 300);
    }, 2000);
}

async function loadLinkedWallets(tokenAddress) {
    const container = document.querySelector('.linked-wallets-container');
    if (!container) return;
    
    // Показываем спиннер загрузки
    container.innerHTML = '';
    container.appendChild(createLoadingSpinner());
    
    try {
        const response = await fetch(`https://goodelivery.ru/api/get_wallets?token_address=${tokenAddress}`);
        const data = await response.json();
        
        if (data.data && Array.isArray(data.data)) {
            walletsData = data.data;
            displayWallets(walletsData, container);
        } else {
            throw new Error('Invalid response format');
        }
    } catch (error) {
        console.error('Error loading wallets:', error);
        container.innerHTML = `
            <div class="error-message">
                <div class="error-icon">⚠️</div>
                <div class="error-text">Failed to load wallets</div>
                <button class="retry-btn" onclick="retryLoadWallets('${tokenAddress}')">Retry</button>
            </div>
        `;
    }
}

function displayWallets(wallets, container) {
    container.innerHTML = '';
    
    if (wallets.length === 0) {
        container.innerHTML = '<div class="no-wallets">No linked wallets found</div>';
        return;
    }
    
    // Создаем контейнер для кошельков
    const walletsGrid = document.createElement('div');
    walletsGrid.className = 'wallets-grid';
    
    wallets.forEach(wallet => {
        walletsGrid.appendChild(createWalletCard(wallet));
    });
    
    // Создаем кнопку отправки
    const sendButton = document.createElement('button');
    sendButton.className = 'send-to-server-btn';
    sendButton.textContent = 'Send to server (0)';
    sendButton.disabled = true;
    
    sendButton.addEventListener('click', async () => {
        await sendSelectedWallets();
    });
    
    container.appendChild(walletsGrid);
    container.appendChild(sendButton);
    
    updateSendButton();
}

async function sendSelectedWallets() {
    if (selectedWallets.size === 0) return;
    
    const sendButton = document.querySelector('.send-to-server-btn');
    const originalText = sendButton.textContent;
    
    sendButton.disabled = true;
    sendButton.textContent = 'Sending...';
    
    try {
        const selectedAddresses = Array.from(selectedWallets);
        const response = await fetch('https://goodelivery.ru/api/add_adresses/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            mode: 'cors',
            credentials: 'omit',
            body: JSON.stringify({
                addresses: selectedAddresses
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Addresses sent successfully!');
            selectedWallets.clear();
            // Обновляем отображение
            const container = document.querySelector('.linked-wallets-container');
            if (container) {
                displayWallets(walletsData, container);
            }
        } else {
            throw new Error(data.error || 'Unknown error');
        }
    } catch (error) {
        console.error('Error sending addresses:', error);
        showToast('Failed to send addresses');
    } finally {
        sendButton.disabled = false;
        sendButton.textContent = originalText;
    }
}

function retryLoadWallets(tokenAddress) {
    loadLinkedWallets(tokenAddress);
}

function replaceTargetBlock() {
    // Ищем целевой блок для замены
    const targetBlock = document.querySelector('div.MuiStack-root.css-1d1x2ui div.MuiPaper-root.MuiPaper-elevation.MuiPaper-elevation1.MuiAccordion-root.Mui-expanded.css-rt5zsn div.MuiButtonBase-root.MuiAccordionSummary-root.Mui-expanded.css-1ctbyhu');
    
    if (!targetBlock) {
        // Если блок не найден, пробуем еще раз через 1 секунду
        setTimeout(replaceTargetBlock, 1000);
        return;
    }
    
    // Проверяем, что замена еще не была выполнена
    if (targetBlock.querySelector('.linked-wallets-replacement')) {
        return;
    }
    
    // Получаем адрес токена из ссылки на Solscan
    const solscanLink = document.querySelector('a[href*="solscan.io/token/"]');
    if (!solscanLink) {
        setTimeout(replaceTargetBlock, 1000);
        return;
    }
    
    const tokenAddress = solscanLink.href.split('/token/')[1];
    if (!tokenAddress) {
        setTimeout(replaceTargetBlock, 1000);
        return;
    }
    
    // Создаем новый блок
    const replacementBlock = document.createElement('div');
    replacementBlock.className = 'linked-wallets-replacement';
    replacementBlock.innerHTML = `
        <div class="replacement-header">
            <div class="header-title">Linked Wallets</div>
            <button class="load-wallets-btn">
                <span class="btn-text">Load Linked Wallets</span>
                <div class="btn-spinner" style="display: none;">
                    <div class="spinner-ring"></div>
                </div>
            </button>
        </div>
        <div class="linked-wallets-container">
            <div class="initial-state">
                <div class="initial-icon">🔍</div>
                <div class="initial-text">Click "Load Linked Wallets" to find connected addresses</div>
            </div>
        </div>
    `;
    
    // Заменяем содержимое целевого блока
    targetBlock.innerHTML = '';
    targetBlock.appendChild(replacementBlock);
    
    // Добавляем обработчик для кнопки загрузки
    const loadButton = replacementBlock.querySelector('.load-wallets-btn');
    loadButton.addEventListener('click', async () => {
        const btnText = loadButton.querySelector('.btn-text');
        const btnSpinner = loadButton.querySelector('.btn-spinner');
        
        btnText.style.display = 'none';
        btnSpinner.style.display = 'block';
        loadButton.disabled = true;
        
        await loadLinkedWallets(tokenAddress);
        
        btnText.style.display = 'block';
        btnSpinner.style.display = 'none';
        loadButton.disabled = false;
    });
}

// Функция для добавления кнопок blacklist и whitelist
function addBlacklistButton() {
    // Проверяем, что мы на правильной странице
    if (!window.location.href.includes('trade.padre.gg/trade/solana/')) {
        return;
    }
    
    // Получаем адрес токена из URL
    const urlParts = window.location.href.split('/');
    const tokenAddress = urlParts[urlParts.length - 1];
    
    // Ищем элемент token-info
    const tokenInfoElement = document.querySelector('div[data-testid="token-info"]');
    
    if (!tokenInfoElement) {
        // Если элемент не найден, пробуем еще раз через 1 секунду
        setTimeout(addBlacklistButton, 1000);
        return;
    }
    
    // Проверяем, что кнопки еще не добавлены
    if (tokenInfoElement.querySelector('.extension-blacklist-btn')) {
        return;
    }
    
    // Создаем кнопку blacklist
    const blacklistButton = document.createElement('button');
    blacklistButton.className = 'extension-blacklist-btn';
    blacklistButton.textContent = 'BLACKLIST USER';
    
    // Создаем кнопку whitelist
    const whitelistButton = document.createElement('button');
    whitelistButton.className = 'extension-whitelist-btn';
    whitelistButton.textContent = 'WHITELIST USER';
    whitelistButton.style.cssText = `
        width: 33%;
        padding: 4px 8px;
        margin-top: 8px;
        margin-left: 8px;
        background: linear-gradient(90deg, #17a2b8 0%, #138496 100%);
        color: white;
        border: none;
        border-radius: 4px;
        font-size: 10px;
        font-weight: 600;
        text-transform: uppercase;
        cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 2px 6px rgba(23, 162, 184, 0.3);
    `;
    blacklistButton.style.cssText = `
        width: 33%;
        padding: 4px 8px;
        margin-top: 8px;
        background: linear-gradient(90deg, #dc3545 0%, #c82333 100%);
        color: white;
        border: none;
        border-radius: 4px;
        font-size: 10px;
        font-weight: 600;
        text-transform: uppercase;
        cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 2px 6px rgba(220, 53, 69, 0.3);
    `;
    
    // Добавляем hover эффект для blacklist кнопки
    blacklistButton.addEventListener('mouseenter', () => {
        blacklistButton.style.transform = 'translateY(-2px)';
        blacklistButton.style.boxShadow = '0 6px 16px rgba(220, 53, 69, 0.4)';
    });
    
    blacklistButton.addEventListener('mouseleave', () => {
        blacklistButton.style.transform = 'translateY(0)';
        blacklistButton.style.boxShadow = '0 4px 12px rgba(220, 53, 69, 0.3)';
    });
    
    // Добавляем hover эффект для whitelist кнопки
    whitelistButton.addEventListener('mouseenter', () => {
        whitelistButton.style.transform = 'translateY(-2px)';
        whitelistButton.style.boxShadow = '0 6px 16px rgba(23, 162, 184, 0.4)';
    });
    
    whitelistButton.addEventListener('mouseleave', () => {
        whitelistButton.style.transform = 'translateY(0)';
        whitelistButton.style.boxShadow = '0 4px 12px rgba(23, 162, 184, 0.3)';
    });
    
    // Добавляем обработчик клика для blacklist
    blacklistButton.addEventListener('click', async () => {
        const originalText = blacklistButton.textContent;
        
        // Отключаем кнопку и показываем загрузку
        blacklistButton.disabled = true;
        blacklistButton.textContent = 'Loading...';
        blacklistButton.style.background = 'linear-gradient(90deg, #6c757d 0%, #5a6268 100%)';
        
        try {
            // Получаем адрес токена из URL
            const urlParts = window.location.href.split('/');
            const tokenAddress = urlParts[urlParts.length - 1];
            
            if (!tokenAddress) {
                throw new Error('Token address not found in URL');
            }
            
            const response = await fetch('https://goodelivery.ru/api/blacklist/', {
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
            });
            
            const data = await response.json();
            
            if (data.success) {
                blacklistButton.textContent = 'Blacklisted!';
                blacklistButton.style.background = 'linear-gradient(90deg, #28a745 0%, #20c997 100%)';
                setTimeout(() => {
                    blacklistButton.textContent = originalText;
                    blacklistButton.disabled = false;
                    blacklistButton.style.background = 'linear-gradient(90deg, #dc3545 0%, #c82333 100%)';
                }, 2000);
            } else {
                throw new Error(data.error || 'Unknown error');
            }
            
        } catch (error) {
            console.error('Error:', error);
            blacklistButton.textContent = 'Error!';
            blacklistButton.style.background = 'linear-gradient(90deg, #dc3545 0%, #c82333 100%)';
            setTimeout(() => {
                blacklistButton.textContent = originalText;
                blacklistButton.disabled = false;
                blacklistButton.style.background = 'linear-gradient(90deg, #dc3545 0%, #c82333 100%)';
            }, 2000);
        }
    });
    
    // Добавляем обработчик клика для whitelist
    whitelistButton.addEventListener('click', async () => {
        const originalText = whitelistButton.textContent;
        
        // Отключаем кнопку и показываем загрузку
        whitelistButton.disabled = true;
        whitelistButton.textContent = 'Loading...';
        whitelistButton.style.background = 'linear-gradient(90deg, #6c757d 0%, #5a6268 100%)';
        
        try {
            // Получаем адрес токена из URL
            const urlParts = window.location.href.split('/');
            const tokenAddress = urlParts[urlParts.length - 1];
            
            if (!tokenAddress) {
                throw new Error('Token address not found in URL');
            }
            
            const response = await fetch('https://goodelivery.ru/api/whitelist/', {
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
            });
            
            const data = await response.json();
            
            if (data.success) {
                whitelistButton.textContent = 'Whitelisted!';
                whitelistButton.style.background = 'linear-gradient(90deg, #28a745 0%, #20c997 100%)';
                setTimeout(() => {
                    whitelistButton.textContent = originalText;
                    whitelistButton.disabled = false;
                    whitelistButton.style.background = 'linear-gradient(90deg, #17a2b8 0%, #138496 100%)';
                }, 2000);
            } else {
                throw new Error(data.error || 'Unknown error');
            }
            
        } catch (error) {
            console.error('Error:', error);
            whitelistButton.textContent = 'Error!';
            whitelistButton.style.background = 'linear-gradient(90deg, #dc3545 0%, #c82333 100%)';
            setTimeout(() => {
                whitelistButton.textContent = originalText;
                whitelistButton.disabled = false;
                whitelistButton.style.background = 'linear-gradient(90deg, #17a2b8 0%, #138496 100%)';
            }, 2000);
        }
    });
    
    // Добавляем кнопки в конец элемента token-info
    tokenInfoElement.appendChild(blacklistButton);
    tokenInfoElement.appendChild(whitelistButton);
}

// Добавляем стили
function addStyles() {
    if (document.querySelector('#extension-wallet-styles')) return;
    
    const style = document.createElement('style');
    style.id = 'extension-wallet-styles';
    style.textContent = `
        .linked-wallets-replacement {
            padding: 16px;
            background: #1a1a1a;
            border-radius: 8px;
            color: white;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        
        .replacement-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }
        
        .header-title {
            font-size: 18px;
            font-weight: 600;
            color: #ffffff;
        }
        
        .load-wallets-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .load-wallets-btn:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
        }
        
        .load-wallets-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .btn-spinner {
            width: 16px;
            height: 16px;
        }
        
        .spinner-ring {
            width: 16px;
            height: 16px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-top: 2px solid white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .linked-wallets-container {
            min-height: 200px;
        }
        
        .initial-state {
            text-align: center;
            padding: 40px 20px;
            color: #888;
        }
        
        .initial-icon {
            font-size: 48px;
            margin-bottom: 16px;
        }
        
        .initial-text {
            font-size: 16px;
        }
        
        .wallet-loading-spinner {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 40px 20px;
        }
        
        .wallet-loading-spinner .spinner-ring {
            width: 40px;
            height: 40px;
            border: 3px solid rgba(255, 255, 255, 0.1);
            border-top: 3px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-bottom: 16px;
        }
        
        .wallet-loading-spinner .spinner-text {
            color: #888;
            font-size: 14px;
        }
        
        .wallets-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
            max-height: 400px;
            overflow-y: auto;
        }
        
        .wallet-card {
            background: #2a2a2a;
            border: 2px solid transparent;
            border-radius: 8px;
            padding: 16px;
            cursor: pointer;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .wallet-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
            border-color: #667eea;
        }
        
        .wallet-card.selected {
            border-color: #4CAF50;
            background: linear-gradient(135deg, #2a2a2a 0%, #1e3a1e 100%);
            transform: scale(1.02);
        }
        
        .wallet-card.selected::before {
            content: '✓';
            position: absolute;
            top: 8px;
            right: 8px;
            background: #4CAF50;
            color: white;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: bold;
        }
        
        .wallet-header {
            margin-bottom: 12px;
        }
        
        .wallet-address {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .address-text {
            font-family: 'Courier New', monospace;
            font-size: 12px;
            color: #ddd;
            word-break: break-all;
        }
        
        .wallet-actions {
            display: flex;
            gap: 8px;
        }
        
        .copy-btn, .open-btn {
            background: rgba(255, 255, 255, 0.1);
            border: none;
            border-radius: 4px;
            padding: 6px;
            cursor: pointer;
            transition: all 0.2s ease;
            color: #ccc;
        }
        
        .copy-btn:hover, .open-btn:hover {
            background: rgba(255, 255, 255, 0.2);
            color: white;
            transform: scale(1.1);
        }
        
        .wallet-details {
            font-size: 12px;
            color: #bbb;
        }
        
        .wallet-details > div {
            margin-bottom: 8px;
        }
        
        .wallet-label {
            font-weight: 600;
            color: #4CAF50;
        }
        
        .wallet-icon img {
            width: 24px;
            height: 24px;
            border-radius: 4px;
            margin-right: 8px;
        }
        
        .wallet-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
        }
        
        .tag {
            background: rgba(102, 126, 234, 0.2);
            color: #667eea;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 10px;
        }
        
        .wallet-type {
            color: #888;
        }
        
        .funded-by {
            background: rgba(255, 255, 255, 0.05);
            padding: 8px;
            border-radius: 4px;
            margin-top: 8px;
        }
        
        .funded-label {
            font-weight: 600;
            color: #ff9800;
            margin-bottom: 4px;
        }
        
        .funded-address {
            font-family: 'Courier New', monospace;
            color: #ddd;
            margin-bottom: 4px;
        }
        
        .tx-hash, .block-time {
            font-size: 10px;
            color: #888;
        }
        
        .send-to-server-btn {
            width: 100%;
            background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .send-to-server-btn:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(76, 175, 80, 0.4);
        }
        
        .send-to-server-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        .error-message {
            text-align: center;
            padding: 40px 20px;
            color: #f44336;
        }
        
        .error-icon {
            font-size: 48px;
            margin-bottom: 16px;
        }
        
        .error-text {
            font-size: 16px;
            margin-bottom: 16px;
        }
        
        .retry-btn {
            background: #f44336;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .retry-btn:hover {
            background: #d32f2f;
        }
        
        .no-wallets {
            text-align: center;
            padding: 40px 20px;
            color: #888;
            font-size: 16px;
        }
        
        .toast {
            position: fixed;
            top: 20px;
            right: 20px;
            background: #333;
            color: white;
            padding: 12px 20px;
            border-radius: 6px;
            font-size: 14px;
            z-index: 10000;
            transform: translateX(100%);
            transition: transform 0.3s ease;
        }
        
        .toast.show {
            transform: translateX(0);
        }
        
        /* Скроллбар для контейнера кошельков */
        .wallets-grid::-webkit-scrollbar {
            width: 8px;
        }
        
        .wallets-grid::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
        }
        
        .wallets-grid::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.3);
            border-radius: 4px;
        }
        
        .wallets-grid::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.5);
        }
    `;
    
    document.head.appendChild(style);
}

// Основная функция инициализации
function initializeExtension() {
    // Проверяем, что мы на правильной странице
    if (!window.location.href.includes('trade.padre.gg/trade/solana/')) {
        return;
    }
    
    // Добавляем стили
    addStyles();
    
    // Заменяем целевой блок
    replaceTargetBlock();
    
    // Добавляем кнопки blacklist и whitelist
    addBlacklistButton();
}

// Запускаем расширение при загрузке страницы
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeExtension);
} else {
    initializeExtension();
}

// Также запускаем при изменениях в DOM (для SPA)
const observer = new MutationObserver(() => {
    initializeExtension();
});

observer.observe(document.body, {
    childList: true,
    subtree: true
});

// Делаем функции глобально доступными для обработчиков событий
window.retryLoadWallets = retryLoadWallets; 