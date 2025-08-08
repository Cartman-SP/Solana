// Content script для добавления кнопки blacklist на страницах trade.padre.gg

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
    
    // Проверяем, что кнопка еще не добавлена
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
    
    // Добавляем обработчик клика
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
    
    // Добавляем обработчик клика для whitelist кнопки
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

// Запускаем функцию при загрузке страницы
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', addBlacklistButton);
} else {
    addBlacklistButton();
}

// Также запускаем при изменениях в DOM (для SPA)
const observer = new MutationObserver(() => {
    addBlacklistButton();
});

observer.observe(document.body, {
    childList: true,
    subtree: true
}); 