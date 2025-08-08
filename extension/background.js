// Background script для браузерного расширения
chrome.runtime.onInstalled.addListener(() => {
    console.log('Solana Token Monitor установлено');
});

// Обработка сообщений от content script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'openSidePanel') {
        chrome.sidePanel.open({ windowId: sender.tab.windowId });
    }
    sendResponse({ success: true });
});

// Обработка клика по иконке расширения
chrome.action.onClicked.addListener((tab) => {
    chrome.runtime.openOptionsPage();
}); 