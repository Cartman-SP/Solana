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
            minAth: '',
            maxAth: '',
            minTokens: '',
            maxTokens: '',
            minMigrations: '',
            maxMigrations: ''
        }, (items) => {
            document.getElementById('min-ath').value = items.minAth;
            document.getElementById('max-ath').value = items.maxAth;
            document.getElementById('min-tokens').value = items.minTokens;
            document.getElementById('max-tokens').value = items.maxTokens;
            document.getElementById('min-migrations').value = items.minMigrations;
            document.getElementById('max-migrations').value = items.maxMigrations;
        });
    }
    
    saveSettings() {
        const settings = {
            minAth: document.getElementById('min-ath').value,
            maxAth: document.getElementById('max-ath').value,
            minTokens: document.getElementById('min-tokens').value,
            maxTokens: document.getElementById('max-tokens').value,
            minMigrations: document.getElementById('min-migrations').value,
            maxMigrations: document.getElementById('max-migrations').value
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