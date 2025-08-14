import sys
sys.setrecursionlimit(15000)  # Устанавливаем лимит рекурсии до 15000
import json
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QGraphicsView, QGraphicsScene, 
                             QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem,
                             QVBoxLayout, QWidget, QSlider, QLabel, QPushButton)
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QFont, QBrush, QColor, QPen, QPainter

class WalletTreeVisualizer(QMainWindow):
    def __init__(self, wallet_data):
        super().__init__()
        self.wallet_data = wallet_data
        self.zoom_level = 100
        self.initUI()
        self.build_wallet_graph()
        
    def initUI(self):
        self.setWindowTitle('Wallet Connection Tree')
        self.setGeometry(100, 100, 1200, 800)
        
        # Central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
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
        self.view.setRenderHint(QPainter.Antialiasing)  # Исправленная строка
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        
        layout.addWidget(self.view)
        
    def build_wallet_graph(self):
        # Create a mapping between wallets
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
        
        # Layout parameters
        level_height = 150
        node_width = 180
        node_height = 50
        h_spacing = 50
        
        # Track positions and visited wallets
        self.wallet_positions = {}
        self.visited_wallets = set()
        
        # Start drawing from root wallets
        start_x = 0
        for i, root in enumerate(root_wallets):
            self.draw_wallet_tree(root, start_x + i * (node_width + h_spacing), 50, 
                                wallet_map, level_height, node_width, node_height, h_spacing)
    
    def draw_wallet_tree(self, wallet, x, y, wallet_map, level_height, node_width, node_height, h_spacing):
        if wallet in self.visited_wallets:
            return
        
        self.visited_wallets.add(wallet)
        
        # Draw wallet rectangle
        rect = QGraphicsRectItem(QRectF(0, 0, node_width, node_height))
        rect.setPos(x, y)
        rect.setBrush(QBrush(QColor(173, 216, 230)))  # Light blue
        rect.setPen(QPen(Qt.black, 1))
        self.scene.addItem(rect)
        
        # Add wallet address text (shortened)
        short_address = wallet[:8] + "..." + wallet[-8:]
        text = QGraphicsTextItem(short_address)
        text.setPos(x + 5, y + 5)
        text.setToolTip(wallet)  # Show full address on hover
        text.setFont(QFont('Arial', 8))
        self.scene.addItem(text)
        
        # Store position for connection lines
        self.wallet_positions[wallet] = QPointF(x + node_width/2, y + node_height)
        
        # Draw connections to found wallets
        if wallet in wallet_map:
            found_wallets = wallet_map[wallet]
            num_found = len(found_wallets)
            
            # Calculate starting x position for children to center them
            total_width = num_found * node_width + (num_found - 1) * h_spacing
            start_x = x - (total_width - node_width) / 2
            
            for i, found in enumerate(found_wallets):
                child_x = start_x + i * (node_width + h_spacing)
                child_y = y + level_height
                
                # Draw line before drawing child
                if found in self.wallet_positions:
                    # If wallet already drawn, connect to existing position
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
                
                line.setPen(QPen(Qt.darkGray, 1, Qt.DashLine))
                self.scene.addItem(line)
                
                # Draw child wallet
                if found not in self.visited_wallets:
                    self.draw_wallet_tree(found, child_x, child_y, wallet_map, 
                                        level_height, node_width, node_height, h_spacing)
    
    def update_zoom(self, value):
        self.zoom_level = value
        self.zoom_label.setText(f'Zoom: {self.zoom_level}%')
        scale = self.zoom_level / 100.0
        self.view.resetTransform()
        self.view.scale(scale, scale)
    
    def reset_view(self):
        self.zoom_slider.setValue(100)
        self.view.centerOn(self.scene.itemsBoundingRect().center())

def load_wallet_data(filename):
    with open(filename, 'r') as f:
        data = json.load(f)
    return data['data']

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Load wallet data
    try:
        wallet_data = load_wallet_data('results.json')
    except Exception as e:
        print(f"Error loading wallet data: {e}")
        sys.exit(1)
    
    # Create and show visualizer
    visualizer = WalletTreeVisualizer(wallet_data)
    visualizer.show()
    
    sys.exit(app.exec_())