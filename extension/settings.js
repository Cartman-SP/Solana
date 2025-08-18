class SettingsManager {
    constructor() {
        this.init();
    }
    
    init() {
        this.loadSettings();
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        document.getElementById('save-settings').addEventListener('click', () => {
            this.saveSettings();
        });
    }
    
    loadSettings() {
        // Старые фильтры (chrome.storage)
        chrome.storage.sync.get({
            // Фильтры пользователя
            minUserAth: '',
            maxUserAth: '',
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
            minTwitterTokens: '',
            maxTwitterTokens: '',
            minTwitterMigrations: '',
            maxTwitterMigrations: '',
            twitterWhitelisted: false,
            twitterBlacklisted: false,
            
            // Дополнительные настройки
            sourceFilter: '',
            showOnlyNew: false
        }, (items) => {
            // Загружаем фильтры пользователя
            document.getElementById('min-user-ath').value = items.minUserAth;
            document.getElementById('max-user-ath').value = items.maxUserAth;
            document.getElementById('min-user-tokens').value = items.minUserTokens;
            document.getElementById('max-user-tokens').value = items.maxUserTokens;
            document.getElementById('min-user-migrations').value = items.minUserMigrations;
            document.getElementById('max-user-migrations').value = items.maxUserMigrations;
            document.getElementById('user-whitelisted').checked = items.userWhitelisted;
            document.getElementById('user-blacklisted').checked = items.userBlacklisted;
            document.getElementById('min-followers').value = items.minFollowers;
            
            // Загружаем фильтры Twitter
            document.getElementById('min-twitter-ath').value = items.minTwitterAth;
            document.getElementById('max-twitter-ath').value = items.maxTwitterAth;
            document.getElementById('min-twitter-tokens').value = items.minTwitterTokens;
            document.getElementById('max-twitter-tokens').value = items.maxTwitterTokens;
            document.getElementById('min-twitter-migrations').value = items.minTwitterMigrations;
            document.getElementById('max-twitter-migrations').value = items.maxTwitterMigrations;
            document.getElementById('twitter-whitelisted').checked = items.twitterWhitelisted;
            document.getElementById('twitter-blacklisted').checked = items.twitterBlacklisted;
            
            // Загружаем дополнительные настройки
            document.getElementById('source-filter').value = items.sourceFilter;
            document.getElementById('show-only-new').checked = items.showOnlyNew;
        });
        // Новый блок: автобаей
        fetch('https://goodelivery.ru/api/auto_buy_settings/', { method: 'GET' })
            .then(res => res.json())
            .then(data => {
                if (data.success && data.settings) {
                    const s = data.settings;
                    document.getElementById('auto-buy-start').checked = s.start;
                    document.getElementById('auto-buy-one-token').checked = s.one_token_enabled;
                    document.getElementById('auto-buy-whitelist').checked = s.whitelist_enabled;
                    document.getElementById('auto-buy-ath-from').value = s.ath_from;
                    document.getElementById('auto-buy-buyer-pubkey').value = s.buyer_pubkey;
                    document.getElementById('auto-buy-sol-amount').value = s.sol_amount;
                    document.getElementById('auto-buy-slippage').value = s.slippage_percent;
                    document.getElementById('auto-buy-priority-fee').value = s.priority_fee_sol;
                }
            });
    }
    
    saveSettings() {
        // Старые фильтры (chrome.storage)
        const settings = {
            // Фильтры пользователя
            minUserAth: document.getElementById('min-user-ath').value,
            maxUserAth: document.getElementById('max-user-ath').value,
            minUserTokens: document.getElementById('min-user-tokens').value,
            maxUserTokens: document.getElementById('max-user-tokens').value,
            minUserMigrations: document.getElementById('min-user-migrations').value,
            maxUserMigrations: document.getElementById('max-user-migrations').value,
            userWhitelisted: document.getElementById('user-whitelisted').checked,
            userBlacklisted: document.getElementById('user-blacklisted').checked,
            minFollowers: document.getElementById('min-followers').value,
            
            // Фильтры Twitter
            minTwitterAth: document.getElementById('min-twitter-ath').value,
            maxTwitterAth: document.getElementById('max-twitter-ath').value,
            minTwitterTokens: document.getElementById('min-twitter-tokens').value,
            maxTwitterTokens: document.getElementById('max-twitter-tokens').value,
            minTwitterMigrations: document.getElementById('min-twitter-migrations').value,
            maxTwitterMigrations: document.getElementById('max-twitter-migrations').value,
            twitterWhitelisted: document.getElementById('twitter-whitelisted').checked,
            twitterBlacklisted: document.getElementById('twitter-blacklisted').checked,
            
            // Дополнительные настройки
            sourceFilter: document.getElementById('source-filter').value,
            showOnlyNew: document.getElementById('show-only-new').checked
        };
        
        chrome.storage.sync.set(settings, () => {
            this.showStatus('Настройки сохранены!', 'success');
        });
        // Новый блок: автобаей
        const autoBuy = {
            start: document.getElementById('auto-buy-start').checked,
            one_token_enabled: document.getElementById('auto-buy-one-token').checked,
            whitelist_enabled: document.getElementById('auto-buy-whitelist').checked,
            ath_from: parseInt(document.getElementById('auto-buy-ath-from').value) || 0,
            buyer_pubkey: document.getElementById('auto-buy-buyer-pubkey').value,
            sol_amount: document.getElementById('auto-buy-sol-amount').value,
            slippage_percent: document.getElementById('auto-buy-slippage').value,
            priority_fee_sol: document.getElementById('auto-buy-priority-fee').value
        };
        fetch('https://goodelivery.ru/api/auto_buy_settings/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(autoBuy)
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                this.showStatus('Настройки автобая сохранены!', 'success');
            } else {
                this.showStatus('Ошибка сохранения автобая', 'error');
            }
        })
        .catch(() => {
            this.showStatus('Ошибка соединения с сервером', 'error');
        });
    }
    
    showStatus(message, type) {
        const statusElement = document.getElementById('status-message');
        statusElement.textContent = message;
        statusElement.className = `status-message ${type}`;
        statusElement.style.display = 'block';
        
        setTimeout(() => {
            statusElement.style.display = 'none';
        }, 3000);
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    new SettingsManager();
}); 