document.addEventListener('DOMContentLoaded', function() {
    const messagesContainer = document.getElementById('messages');
    const statusElement = document.getElementById('status');
    
    // Подключение к WebSocket серверу
    const socket = new WebSocket('ws://goodelivery.ru:8765');
    
    // Обработчик открытия соединения
    socket.addEventListener('open', function(event) {
        statusElement.textContent = 'Подключено';
        statusElement.style.color = 'green';
        
        // Добавляем сообщение о подключении
        addMessage('Система: Соединение установлено');
    });
    
    // Обработчик входящих сообщений
    socket.addEventListener('message', function(event) {
        addMessage(event.data);
    });
    
    // Обработчик ошибок
    socket.addEventListener('error', function(event) {
        statusElement.textContent = 'Ошибка соединения';
        statusElement.className = 'error';
        addMessage('Система: Произошла ошибка соединения');
    });
    
    // Обработчик закрытия соединения
    socket.addEventListener('close', function(event) {
        if (event.wasClean) {
            statusElement.textContent = `Соединение закрыто (код: ${event.code})`;
            addMessage(`Система: Соединение закрыто (код: ${event.code})`);
        } else {
            statusElement.textContent = 'Соединение разорвано';
            statusElement.className = 'error';
            addMessage('Система: Соединение разорвано');
        }
    });
    
    // Функция для добавления сообщения в контейнер
    function addMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = 'message';
        messageElement.textContent = message;
        messagesContainer.appendChild(messageElement);
        
        // Автоматическая прокрутка к новому сообщению
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
});