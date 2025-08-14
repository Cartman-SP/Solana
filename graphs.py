import sys
import requests
from collections import defaultdict
from PyQt5.QtWidgets import (QApplication, QMainWindow, QGraphicsView, QGraphicsScene, 
                            QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem,
                            QVBoxLayout, QWidget, QSlider, QLabel, QPushButton, 
                            QLineEdit, QMessageBox, QHBoxLayout, QGroupBox)
from PyQt5.QtCore import Qt, QPointF, QRectF, QTimer
from PyQt5.QtGui import QFont, QBrush, QColor, QPen, QPainter, QFontMetrics

class WalletTreeVisualizer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.zoom_level = 100
        self.wallet_data = []
        self.wallet_items = {}  # Для хранения графических элементов кошельков
        self.root_wallets = []  # Корневые кошельки (которые никого не пополнили)
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('Wallet Connection Tree')
        self.setGeometry(100, 100, 1400, 900)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Панель управления
        control_group = QGroupBox("Управление")
        control_layout = QHBoxLayout()
        
        # Поиск по Twitter админа
        self.twitter_input = QLineEdit()
        self.twitter_input.setPlaceholderText("Twitter админа")
        control_layout.addWidget(self.twitter_input)
        
        # Кнопка загрузки
        self.load_button = QPushButton("Загрузить данные")
        self.load_button.clicked.connect(self.load_admin_data)
        control_layout.addWidget(self.load_button)
        
        # Поиск по адресу кошелька
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по адресу")
        self.search_input.returnPressed.connect(self.search_wallet)
        control_layout.addWidget(self.search_input)
        
        # Кнопка поиска
        self.search_button = QPushButton("Найти")
        self.search_button.clicked.connect(self.search_wallet)
        control_layout.addWidget(self.search_button)
        
        control_group.setLayout(control_layout)
        main_layout.addWidget(control_group)
        
        # Настройки отображения
        settings_group = QGroupBox("Настройки отображения")
        settings_layout = QVBoxLayout()
        
        # Управление зумом
        zoom_layout = QHBoxLayout()
        self.zoom_label = QLabel(f'Масштаб: {self.zoom_level}%')
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(25, 400)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.update_zoom)
        
        zoom_layout.addWidget(self.zoom_label)
        zoom_layout.addWidget(self.zoom_slider)
        settings_layout.addLayout(zoom_layout)
        
        # Кнопки управления
        btn_layout = QHBoxLayout()
        self.reset_button = QPushButton('Сбросить вид')
        self.reset_button.clicked.connect(self.reset_view)
        btn_layout.addWidget(self.reset_button)
        
        self.show_roots_button = QPushButton('Показать корни')
        self.show_roots_button.clicked.connect(self.highlight_roots)
        btn_layout.addWidget(self.show_roots_button)
        
        settings_layout.addLayout(btn_layout)
        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)
        
        # Графическое отображение
        self.view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        
        main_layout.addWidget(self.view)
    
    def load_admin_data(self):
        twitter = self.twitter_input.text().strip()
        if not twitter:
            QMessageBox.warning(self, "Ошибка", "Введите Twitter админа")
            return
        
        try:
            response = requests.get(
                "https://goodelivery.ru/api/admin_data",
                params={"twitter": twitter},
                timeout=10
            )
            response.raise_for_status()
            self.wallet_data = response.json()
            self.build_wallet_graph()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки данных: {str(e)}")
    
    def build_wallet_graph(self):
        self.scene.clear()
        self.wallet_items = {}
        self.root_wallets = []
        
        if not self.wallet_data:
            return
        
        # Создаем связи между кошельками
        wallet_children = defaultdict(list)
        wallet_parents = defaultdict(list)
        
        for item in self.wallet_data:
            address = item['adress']
            funded_by = item.get('faunded_by')
            
            if funded_by:
                wallet_children[funded_by].append(address)
                wallet_parents[address].append(funded_by)
        
        # Находим корневые кошельки (которые никого не пополнили)
        all_children = set(wallet_parents.keys())
        self.root_wallets = [wallet for wallet in wallet_children if wallet not in all_children]
        
        # Если нет явных корней, берем все кошельки без родителей
        if not self.root_wallets:
            self.root_wallets = [wallet for wallet in wallet_children if not wallet_parents.get(wallet)]
        
        # Если все еще нет корней, берем первый кошелек
        if not self.root_wallets and wallet_children:
            self.root_wallets = [next(iter(wallet_children.keys()))]
        
        # Параметры отрисовки
        level_height = 150
        node_width = 200
        node_height = 60
        h_spacing = 30
        
        # Отрисовываем дерево
        start_x = 0
        for i, root in enumerate(self.root_wallets):
            self.draw_wallet_tree(
                root, start_x + i * (node_width + h_spacing), 50,
                wallet_children, wallet_parents, level_height, 
                node_width, node_height, h_spacing, is_root=True
            )
        
        # Автоматически подстраиваем вид
        QTimer.singleShot(100, self.zoom_to_fit)
    
    def draw_wallet_tree(self, wallet, x, y, wallet_children, wallet_parents, 
                        level_height, node_width, node_height, h_spacing, is_root=False):
        if wallet in self.wallet_items:
            return
        
        # Создаем прямоугольник кошелька
        rect = QGraphicsRectItem(QRectF(0, 0, node_width, node_height))
        rect.setPos(x, y)
        
        # Разные цвета для корневых, обычных и выделенных кошельков
        if is_root:
            rect.setBrush(QBrush(QColor(144, 238, 144)))  # Светло-зеленый для корней
        else:
            rect.setBrush(QBrush(QColor(173, 216, 230)))  # Светло-голубой для обычных
        
        rect.setPen(QPen(Qt.black, 2 if is_root else 1))
        self.scene.addItem(rect)
        
        # Добавляем текст с адресом
        short_address = wallet[:6] + "..." + wallet[-4:]
        text = QGraphicsTextItem(short_address)
        text.setPos(x + 5, y + 5)
        
        # Полный адрес в подсказке и дополнительной информации
        tooltip = f"Адрес: {wallet}\n"
        if wallet in wallet_parents:
            parents = ", ".join(f"{p[:6]}...{p[-4:]}" for p in wallet_parents[wallet])
            tooltip += f"Пополнен: {parents}"
        elif is_root:
            tooltip += "Корневой кошелек (не был пополнен)"
        
        text.setToolTip(tooltip)
        text.setFont(QFont('Arial', 10))
        self.scene.addItem(text)
        
        # Сохраняем элемент для поиска
        self.wallet_items[wallet] = {
            'rect': rect,
            'text': text,
            'pos': QPointF(x + node_width/2, y + node_height/2)
        }
        
        # Отрисовываем связи
        if wallet in wallet_children:
            children = wallet_children[wallet]
            num_children = len(children)
            
            # Вычисляем позиции для дочерних элементов
            total_width = num_children * node_width + (num_children - 1) * h_spacing
            start_x = x - (total_width - node_width) / 2
            
            for i, child in enumerate(children):
                child_x = start_x + i * (node_width + h_spacing)
                child_y = y + level_height
                
                # Рисуем соединительную линию
                line = QGraphicsLineItem(
                    x + node_width/2, y + node_height,
                    child_x + node_width/2, child_y
                )
                
                line.setPen(QPen(Qt.darkGray, 1.5, Qt.SolidLine))
                self.scene.addItem(line)
                
                # Рекурсивно рисуем дочерний кошелек
                self.draw_wallet_tree(
                    child, child_x, child_y, 
                    wallet_children, wallet_parents, level_height,
                    node_width, node_height, h_spacing
                )
    
    def search_wallet(self):
        search_text = self.search_input.text().strip().lower()
        if not search_text:
            return
        
        found_wallets = [
            addr for addr in self.wallet_items 
            if search_text in addr.lower()
        ]
        
        if not found_wallets:
            QMessageBox.information(self, "Поиск", "Кошелек не найден")
            return
        
        # Выделяем найденные кошельки
        for wallet, item in self.wallet_items.items():
            if wallet in found_wallets:
                item['rect'].setBrush(QBrush(QColor(255, 215, 0)))  # Золотой для выделения
                item['rect'].setPen(QPen(Qt.red, 2))
            else:
                if wallet in self.root_wallets:
                    item['rect'].setBrush(QBrush(QColor(144, 238, 144)))
                else:
                    item['rect'].setBrush(QBrush(QColor(173, 216, 230)))
                item['rect'].setPen(QPen(Qt.black, 1))
        
        # Центрируем на первом найденном кошельке
        first_wallet = found_wallets[0]
        self.center_on_wallet(first_wallet)
    
    def center_on_wallet(self, wallet):
        if wallet not in self.wallet_items:
            return
        
        pos = self.wallet_items[wallet]['pos']
        self.view.centerOn(pos)
        
        # Анимация подлета
        self.zoom_slider.setValue(150)
        QTimer.singleShot(500, lambda: self.zoom_slider.setValue(100))
    
    def highlight_roots(self):
        """Подсвечивает корневые кошельки"""
        for wallet, item in self.wallet_items.items():
            if wallet in self.root_wallets:
                item['rect'].setBrush(QBrush(QColor(144, 238, 144)))
                item['rect'].setPen(QPen(Qt.darkGreen, 2))
            else:
                item['rect'].setBrush(QBrush(QColor(173, 216, 230)))
                item['rect'].setPen(QPen(Qt.black, 1))
        
        if self.root_wallets:
            self.center_on_wallet(self.root_wallets[0])
    
    def zoom_to_fit(self):
        """Автоматически подстраивает масштаб под все дерево"""
        rect = self.scene.itemsBoundingRect()
        self.view.fitInView(rect, Qt.KeepAspectRatio)
        self.zoom_level = 100
        self.zoom_label.setText(f'Масштаб: {self.zoom_level}%')
        self.zoom_slider.setValue(100)
    
    def update_zoom(self, value):
        self.zoom_level = value
        self.zoom_label.setText(f'Масштаб: {self.zoom_level}%')
        scale = self.zoom_level / 100.0
        self.view.resetTransform()
        self.view.scale(scale, scale)
    
    def reset_view(self):
        self.zoom_slider.setValue(100)
        self.zoom_to_fit()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Современный стиль интерфейса
    
    # Увеличиваем лимит рекурсии
    import sys
    sys.setrecursionlimit(15000)
    
    visualizer = WalletTreeVisualizer()
    visualizer.show()
    sys.exit(app.exec_())