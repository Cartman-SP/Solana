import sys
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
                            QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem,
                            QVBoxLayout, QWidget, QSlider, QLabel, QPushButton,
                            QLineEdit, QMessageBox, QHBoxLayout)
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QFont, QBrush, QColor, QPen, QPainter

class WalletTreeVisualizer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.zoom_level = 100
        self.wallet_data = []
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('Wallet Connection Tree')
        self.setGeometry(100, 100, 1200, 800)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Input controls
        control_layout = QHBoxLayout()
        
        self.twitter_input = QLineEdit()
        self.twitter_input.setPlaceholderText("Enter admin Twitter")
        control_layout.addWidget(self.twitter_input)
        
        self.load_button = QPushButton("Load Data")
        self.load_button.clicked.connect(self.load_admin_data)
        control_layout.addWidget(self.load_button)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search wallet")
        control_layout.addWidget(self.search_input)
        
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.search_wallet)
        control_layout.addWidget(self.search_button)
        
        layout.addLayout(control_layout)
        
        # Zoom controls
        zoom_layout = QVBoxLayout()
        self.zoom_label = QLabel(f'Zoom: {self.zoom_level}%')
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(25, 400)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.update_zoom)
        
        zoom_layout.addWidget(self.zoom_label)
        zoom_layout.addWidget(self.zoom_slider)
        
        # Reset view button
        self.reset_button = QPushButton('Reset View')
        self.reset_button.clicked.connect(self.reset_view)
        zoom_layout.addWidget(self.reset_button)
        
        layout.addLayout(zoom_layout)
        
        # Graphics view for the tree
        self.view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        
        layout.addWidget(self.view)
    
    def load_admin_data(self):
        twitter = self.twitter_input.text().strip()
        if not twitter:
            QMessageBox.warning(self, "Error", "Please enter Twitter handle")
            return
        
        try:
            response = requests.get(
                "https://goodelivery.ru/api/admin_data",
                params={"twitter": twitter},
                timeout=10
            )
            response.raise_for_status()
            
            # Convert API response to the original format
            api_data = response.json()
            self.wallet_data = [{"main": item['faunded_by'], "faund": item['adress']} 
                              for item in api_data if item.get('faunded_by')]
            
            self.build_wallet_graph()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load data: {str(e)}")
    
    def build_wallet_graph(self):
        self.scene.clear()
        
        if not self.wallet_data:
            return
        
        # Create mapping between wallets (original algorithm)
        wallet_map = {}
        for item in self.wallet_data:
            main = item['main']
            found = item['faund']
            if main not in wallet_map:
                wallet_map[main] = []
            wallet_map[main].append(found)
        
        # Find root wallets (those that are not found in any 'faund' list)
        all_found = set()
        for found_list in wallet_map.values():
            all_found.update(found_list)
        
        root_wallets = [wallet for wallet in wallet_map if wallet not in all_found]
        
        # If no roots found, just take the first wallet as root
        if not root_wallets and wallet_map:
            root_wallets = [next(iter(wallet_map.keys()))]
        
        # Original layout parameters
        level_height = 150
        node_width = 180
        node_height = 50
        h_spacing = 50
        
        # Track positions and visited wallets
        self.wallet_positions = {}
        self.visited_wallets = set()
        self.wallet_items = {}  # For search functionality
        
        # Start drawing from root wallets (original drawing method)
        start_x = 0
        for i, root in enumerate(root_wallets):
            self.draw_wallet_tree(root, start_x + i * (node_width + h_spacing), 50, 
                                wallet_map, level_height, node_width, node_height, h_spacing)
    
    def draw_wallet_tree(self, wallet, x, y, wallet_map, level_height, node_width, node_height, h_spacing):
        if wallet in self.visited_wallets:
            return
        
        self.visited_wallets.add(wallet)
        
        # Original rectangle drawing
        rect = QGraphicsRectItem(QRectF(0, 0, node_width, node_height))
        rect.setPos(x, y)
        rect.setBrush(QBrush(QColor(173, 216, 230)))  # Original light blue color
        rect.setPen(QPen(Qt.black, 1))
        self.scene.addItem(rect)
        
        # Original text display
        short_address = wallet[:8] + "..." + wallet[-8:]
        text = QGraphicsTextItem(short_address)
        text.setPos(x + 5, y + 5)
        text.setToolTip(wallet)  # Show full address on hover
        text.setFont(QFont('Arial', 8))
        self.scene.addItem(text)
        
        # Store for search
        self.wallet_items[wallet] = (rect, text)
        
        # Original position tracking
        self.wallet_positions[wallet] = QPointF(x + node_width/2, y + node_height)
        
        # Original connection drawing
        if wallet in wallet_map:
            found_wallets = wallet_map[wallet]
            num_found = len(found_wallets)
            
            # Original centering calculation
            total_width = num_found * node_width + (num_found - 1) * h_spacing
            start_x = x - (total_width - node_width) / 2
            
            for i, found in enumerate(found_wallets):
                child_x = start_x + i * (node_width + h_spacing)
                child_y = y + level_height
                
                # Original line drawing
                if found in self.wallet_positions:
                    existing_pos = self.wallet_positions[found]
                    line = QGraphicsLineItem(
                        x + node_width/2, y + node_height,
                        existing_pos.x(), existing_pos.y() - node_height
                    )
                else:
                    line = QGraphicsLineItem(
                        x + node_width/2, y + node_height,
                        child_x + node_width/2, child_y
                    )
                
                line.setPen(QPen(Qt.darkGray, 1, Qt.DashLine))  # Original dashed line
                self.scene.addItem(line)
                
                # Original recursive drawing
                if found not in self.visited_wallets:
                    self.draw_wallet_tree(found, child_x, child_y, wallet_map, 
                                        level_height, node_width, node_height, h_spacing)
    
    def search_wallet(self):
        search_text = self.search_input.text().strip()
        if not search_text:
            return
        
        found = False
        for wallet, (rect, text) in self.wallet_items.items():
            if search_text.lower() in wallet.lower():
                rect.setBrush(QBrush(QColor(255, 215, 0)))  # Highlight color
                self.view.centerOn(rect)
                found = True
            else:
                rect.setBrush(QBrush(QColor(173, 216, 230)))  # Restore original color
        
        if not found:
            QMessageBox.information(self, "Search", "Wallet not found")
    
    def update_zoom(self, value):
        self.zoom_level = value
        self.zoom_label.setText(f'Zoom: {self.zoom_level}%')
        scale = self.zoom_level / 100.0
        self.view.resetTransform()
        self.view.scale(scale, scale)
    
    def reset_view(self):
        self.zoom_slider.setValue(100)
        self.view.centerOn(self.scene.itemsBoundingRect().center())

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Increase recursion limit as in original
    import sys
    sys.setrecursionlimit(15000)
    
    visualizer = WalletTreeVisualizer()
    visualizer.show()
    sys.exit(app.exec_())