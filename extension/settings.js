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
    }
    
    saveSettings() {
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