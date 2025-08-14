import sys
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QGraphicsView, QGraphicsScene, 
                             QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem,
                             QVBoxLayout, QWidget, QSlider, QLabel, QPushButton, 
                             QLineEdit, QMessageBox)
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
        
        # Twitter input
        self.twitter_input = QLineEdit()
        self.twitter_input.setPlaceholderText("Enter admin Twitter handle")
        layout.addWidget(self.twitter_input)
        
        # Load button
        self.load_button = QPushButton("Load Data")
        self.load_button.clicked.connect(self.load_admin_data)
        layout.addWidget(self.load_button)
        
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
        
        # Graphics view
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
                params={"twitter": twitter}
            )
            response.raise_for_status()
            self.wallet_data = response.json()
            self.build_wallet_graph()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load data: {str(e)}")
    
    def build_wallet_graph(self):
        self.scene.clear()
        
        if not self.wallet_data:
            return
        
        # Create mapping between wallets
        wallet_map = {}
        for item in self.wallet_data:
            main = item['adress']
            found = item.get('faunded_by')
            if found:
                if found not in wallet_map:
                    wallet_map[found] = []
                wallet_map[found].append(main)
        
        # Find root wallets (those that are not found in any 'faunded_by')
        all_children = set()
        for children in wallet_map.values():
            all_children.update(children)
        
        root_wallets = [wallet for wallet in wallet_map if wallet not in all_children]
        
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
            
            # Calculate starting x position for children
            total_width = num_found * node_width + (num_found - 1) * h_spacing
            start_x = x - (total_width - node_width) / 2
            
            for i, found in enumerate(found_wallets):
                child_x = start_x + i * (node_width + h_spacing)
                child_y = y + level_height
                
                # Draw line before drawing child
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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    visualizer = WalletTreeVisualizer()
    visualizer.show()
    sys.exit(app.exec_())