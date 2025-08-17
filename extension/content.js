// Content script для замены блока на страницах trade.padre.gg и загрузки связанных кошельков

let walletsData = [];
let selectedWallets = new Set();
let isBlockReplaced = false; // Флаг для предотвращения дублирования
let isTrenchesReordered = false; // Флаг для страницы trenches

function createLoadingSpinner() {
    const spinner = document.createElement('div');
    spinner.className = 'wallet-loading-spinner';
    spinner.innerHTML = `
        <div class="spinner-container">
            <div class="spinner-dot"></div>
            <div class="spinner-dot"></div>
            <div class="spinner-dot"></div>
        </div>
        <div class="spinner-text">Loading...</div>
    `;
    
    return spinner;
}

function truncateAddress(address) {
    if (address.length <= 10) return address;
    return address.substring(0, 6) + '...' + address.substring(address.length - 4);
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
                <span class="address-text" title="${wallet.account_address}">${truncateAddress(wallet.account_address)}</span>
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
                    <div class="funded-address" title="${wallet.funded_by.funded_by}">${truncateAddress(wallet.funded_by.funded_by)}</div>
                    ${wallet.funded_by.tx_hash ? `<div class="tx-hash" title="${wallet.funded_by.tx_hash}">TX: ${truncateAddress(wallet.funded_by.tx_hash)}</div>` : ''}
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
    // Проверяем, что замена еще не была выполнена
    if (isBlockReplaced) {
        return;
    }
    
    // Ищем целевой блок для замены - берем второй блок
    const targetBlocks = document.querySelectorAll('div.MuiStack-root.css-1d1x2ui');
    const targetBlock = targetBlocks[1]; // Берем второй блок
    
    if (!targetBlock) {
        // Если блок не найден, пробуем еще раз через 1 секунду
        setTimeout(replaceTargetBlock, 1000);
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
    
    // Полностью заменяем содержимое целевого блока
    targetBlock.innerHTML = '';
    targetBlock.className = 'linked-wallets-replacement';
    
    // Создаем новый блок с кнопкой по центру
    targetBlock.innerHTML = `
        <div class="linked-wallets-container">
            <div class="initial-state">
                <button class="load-wallets-btn">
                    <span class="btn-text">Load Linked Wallets</span>
                    <div class="btn-spinner" style="display: none;">
                        <div class="btn-spinner-dots">
                            <div class="btn-spinner-dot"></div>
                            <div class="btn-spinner-dot"></div>
                            <div class="btn-spinner-dot"></div>
                        </div>
                    </div>
                </button>
            </div>
        </div>
    `;
    
    // Добавляем обработчик для кнопки загрузки
    const loadButton = targetBlock.querySelector('.load-wallets-btn');
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
    
    // Устанавливаем флаг, что блок заменен
    isBlockReplaced = true;
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
            background: rgb(6, 7, 11) !important;
            border-radius: 8px;
            color: white;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            width: 100% !important;
            height: auto !important;
            min-height: 400px;
            padding: 16px;
            box-sizing: border-box;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        .linked-wallets-container {
            flex: 1;
            min-height: 350px;
            display: flex;
            flex-direction: column;
            width: 100%;
            overflow: hidden;
        }
        
        .initial-state {
            text-align: center;
            padding: 80px 20px;
            color: white;
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            width: 100%;
            box-sizing: border-box;
        }
        
        .load-wallets-btn {
            background: linear-gradient(135deg, rgb(47, 227, 172) 0%, rgb(47, 227, 172) 100%);
            color: rgb(6, 7, 11);
            border: none;
            padding: 16px 32px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 12px;
            min-width: 200px;
            justify-content: center;
            box-sizing: border-box;
        }
        
        .load-wallets-btn:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(47, 227, 172, 0.4);
        }
        
        .load-wallets-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .btn-spinner {
            width: 20px;
            height: 20px;
        }
        
        .btn-spinner-dots {
            display: flex;
            gap: 4px;
            align-items: center;
        }
        
        .btn-spinner-dot {
            width: 6px;
            height: 6px;
            background: rgb(6, 7, 11);
            border-radius: 50%;
            animation: btn-spinner-bounce 1.4s ease-in-out infinite both;
        }
        
        .btn-spinner-dot:nth-child(1) {
            animation-delay: -0.32s;
        }
        
        .btn-spinner-dot:nth-child(2) {
            animation-delay: -0.16s;
        }
        
        @keyframes btn-spinner-bounce {
            0%, 80%, 100% {
                transform: scale(0);
            }
            40% {
                transform: scale(1);
            }
        }
        
        .wallet-loading-spinner {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 80px 20px;
            flex: 1;
            width: 100%;
            box-sizing: border-box;
        }
        
        .spinner-container {
            display: flex;
            gap: 8px;
            margin-bottom: 16px;
        }
        
        .spinner-dot {
            width: 12px;
            height: 12px;
            background: rgb(47, 227, 172);
            border-radius: 50%;
            animation: spinner-bounce 1.4s ease-in-out infinite both;
        }
        
        .spinner-dot:nth-child(1) {
            animation-delay: -0.32s;
        }
        
        .spinner-dot:nth-child(2) {
            animation-delay: -0.16s;
        }
        
        @keyframes spinner-bounce {
            0%, 80%, 100% {
                transform: scale(0);
            }
            40% {
                transform: scale(1);
            }
        }
        
        .wallet-loading-spinner .spinner-text {
            color: white;
            font-size: 14px;
        }
        
        .wallets-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
            max-height: 500px;
            overflow-y: auto;
            overflow-x: hidden;
            flex: 1;
            width: 100%;
            box-sizing: border-box;
        }
        
        .wallet-card {
            background: rgb(24, 24, 26);
            border: 2px solid transparent;
            border-radius: 8px;
            padding: 16px;
            cursor: pointer;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
            box-sizing: border-box;
            width: 100%;
            max-width: 100%;
        }
        
        .wallet-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(47, 227, 172, 0.2);
            border-color: rgb(47, 227, 172);
        }
        
        .wallet-card.selected {
            border-color: rgb(47, 227, 172);
            background: linear-gradient(135deg, rgb(24, 24, 26) 0%, rgba(47, 227, 172, 0.1) 100%);
            transform: scale(1.02);
        }
        
        .wallet-card.selected::before {
            content: '✓';
            position: absolute;
            top: 8px;
            right: 8px;
            background: rgb(47, 227, 172);
            color: rgb(6, 7, 11);
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
            width: 100%;
        }
        
        .wallet-address {
            display: flex;
            justify-content: space-between;
            align-items: center;
            width: 100%;
            gap: 8px;
        }
        
        .address-text {
            font-family: 'Courier New', monospace;
            font-size: 12px;
            color: white;
            word-break: break-all;
            flex: 1;
            min-width: 0;
        }
        
        .wallet-actions {
            display: flex;
            gap: 8px;
            flex-shrink: 0;
        }
        
        .copy-btn, .open-btn {
            background: rgba(255, 255, 255, 0.1);
            border: none;
            border-radius: 4px;
            padding: 6px;
            cursor: pointer;
            transition: all 0.2s ease;
            color: white;
            flex-shrink: 0;
        }
        
        .copy-btn:hover, .open-btn:hover {
            background: rgba(255, 255, 255, 0.2);
            color: rgb(47, 227, 172);
            transform: scale(1.1);
        }
        
        .wallet-details {
            font-size: 12px;
            color: rgba(255, 255, 255, 0.8);
            width: 100%;
        }
        
        .wallet-details > div {
            margin-bottom: 8px;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }
        
        .wallet-label {
            font-weight: 600;
            color: rgb(47, 227, 172);
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
            width: 100%;
        }
        
        .tag {
            background: rgba(47, 227, 172, 0.2);
            color: rgb(47, 227, 172);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 10px;
            white-space: nowrap;
        }
        
        .wallet-type {
            color: rgba(255, 255, 255, 0.6);
        }
        
        .funded-by {
            background: rgba(255, 255, 255, 0.05);
            padding: 8px;
            border-radius: 4px;
            margin-top: 8px;
            width: 100%;
            box-sizing: border-box;
        }
        
        .funded-label {
            font-weight: 600;
            color: rgb(47, 227, 172);
            margin-bottom: 4px;
        }
        
        .funded-address {
            font-family: 'Courier New', monospace;
            color: white;
            margin-bottom: 4px;
            word-break: break-all;
        }
        
        .tx-hash, .block-time {
            font-size: 10px;
            color: rgba(255, 255, 255, 0.6);
            word-break: break-all;
        }
        
        .send-to-server-btn {
            width: 100%;
            background: linear-gradient(135deg, rgb(47, 227, 172) 0%, rgb(47, 227, 172) 100%);
            color: rgb(6, 7, 11);
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-top: auto;
            box-sizing: border-box;
        }
        
        .send-to-server-btn:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(47, 227, 172, 0.4);
        }
        
        .send-to-server-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        .error-message {
            text-align: center;
            padding: 80px 20px;
            color: white;
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            width: 100%;
            box-sizing: border-box;
        }
        
        .error-text {
            font-size: 16px;
            margin-bottom: 16px;
        }
        
        .retry-btn {
            background: rgb(47, 227, 172);
            color: rgb(6, 7, 11);
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .retry-btn:hover {
            background: rgba(47, 227, 172, 0.8);
        }
        
        .no-wallets {
            text-align: center;
            padding: 80px 20px;
            color: white;
            font-size: 16px;
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            box-sizing: border-box;
        }
        
        .toast {
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgb(6, 7, 11);
            color: rgb(47, 227, 172);
            padding: 12px 20px;
            border-radius: 6px;
            font-size: 14px;
            z-index: 10000;
            transform: translateX(100%);
            transition: transform 0.3s ease;
            border: 1px solid rgb(47, 227, 172);
            max-width: 300px;
            word-wrap: break-word;
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
            background: rgba(47, 227, 172, 0.3);
            border-radius: 4px;
        }
        
        .wallets-grid::-webkit-scrollbar-thumb:hover {
            background: rgba(47, 227, 172, 0.5);
        }
        
        /* Адаптивность */
        @media (max-width: 768px) {
            .linked-wallets-replacement {
                padding: 12px;
                min-height: 350px;
            }
            
            .linked-wallets-container {
                min-height: 300px;
            }
            
            .initial-state, .wallet-loading-spinner, .error-message, .no-wallets {
                padding: 60px 20px;
            }
            
            .wallets-grid {
                grid-template-columns: 1fr;
                max-height: 400px;
            }
            
            .load-wallets-btn {
                min-width: 160px;
                padding: 12px 24px;
            }
        }
    `;
    
    document.head.appendChild(style);
}

// Функция для сброса флагов при смене страницы
function resetFlags() {
    isBlockReplaced = false;
    isTrenchesReordered = false;
}

// Основная функция инициализации
function initializeExtension() {
    // Сбрасываем флаги при инициализации
    resetFlags();
    
    // Проверяем, что мы на правильной странице
    if (window.location.href.includes('trade.padre.gg/trade/solana/')) {
        // Добавляем стили
        addStyles();
        
        // Заменяем целевой блок
        replaceTargetBlock();
        
        // Добавляем кнопки blacklist и whitelist
        addBlacklistButton();
    } else if (window.location.href.includes('trade.padre.gg/trenches')) {
        // Для страницы trenches меняем порядок элементов
        console.log('Trenches page detected, calling reorderTrenchesElements...');
        if (typeof reorderTrenchesElements === 'function') {
            reorderTrenchesElements();
        } else {
            console.error('reorderTrenchesElements function is not defined!');
        }
    }
}

// Функция для изменения порядка элементов на странице trenches
function reorderTrenchesElements() {
    // Проверяем, что перестановка еще не была выполнена
    if (isTrenchesReordered) {
        console.log('Trenches already reordered, skipping...');
        return;
    }
    
    console.log('Starting reorderTrenchesElements function...');
    
    try {
        // Ищем родительский контейнер с классом css-12wpaax
        const parentContainer = document.querySelector('div.MuiStack-root.css-12wpaax');
        console.log('Parent container found:', !!parentContainer);
        
        if (!parentContainer) {
            // Если родительский контейнер не найден, пробуем еще раз через 1 секунду
            console.log('Parent container not found, retrying in 1 second...');
            setTimeout(reorderTrenchesElements, 1000);
            return;
        }
        
        // Ищем элементы MuiStack-root с классами css-1v21yzc и css-1shjrlc внутри родительского контейнера
        const targetElements = parentContainer.querySelectorAll('div.MuiStack-root.css-1v21yzc, div.MuiStack-root.css-1shjrlc');
        console.log('Target elements found:', targetElements.length);
        
        if (targetElements.length < 3) {
            // Если элементов меньше 3, пробуем еще раз через 1 секунду
            console.log('Not enough target elements, retrying in 1 second...');
            setTimeout(reorderTrenchesElements, 1000);
            return;
        }
        
        // Перемещаем первый элемент (New) в конец родительского блока
        const firstElement = targetElements[0];
        
        console.log('First element (New):', !!firstElement);
        
        if (firstElement) {
            // Сохраняем родительский элемент
            const parent = firstElement.parentNode;
            
            // Перемещаем первый элемент в конец
            parent.appendChild(firstElement);
            
            // Устанавливаем флаг, что элементы переставлены
            isTrenchesReordered = true;
            
            console.log('Trenches elements reordered successfully: New moved to the end');
        } else {
            console.log('First element not found');
        }
    } catch (error) {
        console.error('Error in reorderTrenchesElements:', error);
        // Пробуем еще раз через 1 секунду при ошибке
        setTimeout(reorderTrenchesElements, 1000);
    }
}

// Запускаем расширение при загрузке страницы
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeExtension);
} else {
    initializeExtension();
}

// Слушаем изменения URL для SPA
let currentUrl = window.location.href;
new MutationObserver(() => {
    const url = window.location.href;
    if (url !== currentUrl) {
        currentUrl = url;
        resetFlags();
        initializeExtension();
    }
}).observe(document, {subtree: true, childList: true});

// Также запускаем при изменениях в DOM (для SPA)
const observer = new MutationObserver(() => {
    if (window.location.href.includes('trade.padre.gg/trade/solana/') && !isBlockReplaced) {
        initializeExtension();
    } else if (window.location.href.includes('trade.padre.gg/trenches') && !isTrenchesReordered) {
        initializeExtension();
    }
});

observer.observe(document.body, {
    childList: true,
    subtree: true
});

// Делаем функции глобально доступными для обработчиков событий
window.retryLoadWallets = retryLoadWallets;
window.reorderTrenchesElements = reorderTrenchesElements; 