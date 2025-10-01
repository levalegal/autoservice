import sys
import os
import sqlite3
from PyQt5.QtCore import QSize
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from contextlib import contextmanager
from dataclasses import dataclass
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
import shutil
import unittest
import uuid
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QTableWidget, QTableWidgetItem, QPushButton, QComboBox,
                             QLineEdit, QLabel, QMessageBox, QHeaderView, QAction,
                             QToolBar, QStatusBar, QFrame, QCheckBox, QDialog,
                             QFormLayout, QTextEdit, QListWidget, QListWidgetItem, QFileDialog,
                             QGroupBox, QSpinBox, QDialogButtonBox, QTabWidget)
from PyQt5.QtGui import QIcon, QPixmap, QColor

# Папка для изображений
IMAGE_DIR = "images"
os.makedirs(IMAGE_DIR, exist_ok=True)

# ==================== DATABASE MODULE ====================
class DatabaseManager:
    def __init__(self, db_name="autoservice.db"):
        self.db_name = db_name
        self.init_database()
        sqlite3.register_adapter(Decimal, lambda d: float(d))

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def init_database(self):
        with self.get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS manufacturers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    price DECIMAL(10,2) NOT NULL CHECK(price >= 0),
                    description TEXT,
                    image_path TEXT,
                    manufacturer_id INTEGER,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (manufacturer_id) REFERENCES manufacturers (id)
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS product_relations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    main_product_id INTEGER NOT NULL,
                    related_product_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (main_product_id) REFERENCES products (id),
                    FOREIGN KEY (related_product_id) REFERENCES products (id),
                    UNIQUE(main_product_id, related_product_id),
                    CHECK(main_product_id != related_product_id)
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sales_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL CHECK(quantity > 0),
                    sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_amount DECIMAL(10,2) NOT NULL,
                    customer_info TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products (id)
                )
            ''')
            self._insert_sample_data(conn)

    def _insert_sample_data(self, conn):
        cursor = conn.execute("SELECT COUNT(*) FROM products")
        if cursor.fetchone()[0] > 0:
            return

        manufacturers = [
            'Toyota', 'Honda', 'Ford', 'BMW', 'Mercedes',
            'Audi', 'Volkswagen', 'Nissan', 'Hyundai', 'Kia'
        ]
        for manufacturer in manufacturers:
            conn.execute('INSERT OR IGNORE INTO manufacturers (name) VALUES (?)', (manufacturer,))

        products = [
            ('Масло моторное 5W-30', 2500.00, 'Синтетическое моторное масло', '', 1, True),
            ('Воздушный фильтр', 1200.00, 'Воздушный фильтр салона', '', 1, True),
            ('Тормозные колодки', 4500.00, 'Передние тормозные колодки', '', 2, True),
            ('Аккумулятор 60Ah', 8500.00, 'Свинцово-кислотный аккумулятор', '', 3, True),
            ('Свечи зажигания', 1800.00, 'Иридиевые свечи зажигания', '', 1, True),
            ('Шины 205/55 R16', 12000.00, 'Летние шины', '', 4, True),
            ('Амортизаторы', 7500.00, 'Передние амортизаторы', '', 2, True),
            ('Ремень ГРМ', 3200.00, 'Ремень газораспределительного механизма', '', 1, True),
            ('Тормозная жидкость', 800.00, 'DOT 4 тормозная жидкость', '', 3, True),
            ('Охлаждающая жидкость', 1500.00, 'Антифриз -40°C', '', 1, True)
        ]
        for product in products:
            conn.execute('''
                INSERT OR IGNORE INTO products 
                (name, price, description, image_path, manufacturer_id, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', product)

        relations = [(1, 2), (1, 5), (1, 10), (3, 9), (3, 4), (6, 7), (6, 3), (8, 1), (8, 5)]
        for main, rel in relations:
            conn.execute('''
                INSERT OR IGNORE INTO product_relations 
                (main_product_id, related_product_id) VALUES (?, ?)
            ''', (main, rel))

        cursor = conn.execute("SELECT COUNT(*) FROM sales_history")
        if cursor.fetchone()[0] == 0:
            import random
            for i in range(50):
                product_id = random.randint(1, 10)
                quantity = random.randint(1, 5)
                price = conn.execute('SELECT price FROM products WHERE id = ?', (product_id,)).fetchone()[0]
                total_amount = price * quantity
                sale_date = datetime.now() - timedelta(days=random.randint(0, 365))
                conn.execute('''
                    INSERT INTO sales_history 
                    (product_id, quantity, sale_date, total_amount, customer_info)
                    VALUES (?, ?, ?, ?, ?)
                ''', (product_id, quantity, sale_date, total_amount, f'Клиент {i + 1}'))


# ==================== MODELS MODULE ====================
@dataclass
class Manufacturer:
    id: int
    name: str
    created_at: datetime = None

@dataclass
class Product:
    id: int
    name: str
    price: Decimal
    description: str
    image_path: str
    manufacturer_id: int
    manufacturer_name: str = None
    is_active: bool = True
    created_at: datetime = None
    updated_at: datetime = None
    related_products_count: int = 0

@dataclass
class ProductRelation:
    id: int
    main_product_id: int
    related_product_id: int
    created_at: datetime = None
    related_product: Product = None

@dataclass
class SalesHistory:
    id: int
    product_id: int
    quantity: int
    sale_date: datetime
    total_amount: Decimal
    customer_info: str
    created_at: datetime = None
    product_name: str = None


class ProductManager:
    def __init__(self, db_manager):
        self.db = db_manager

    def get_all_products(self, manufacturer_id=None, sort_by=None, sort_order='ASC'):
        with self.db.get_connection() as conn:
            query = '''
                SELECT p.*, m.name as manufacturer_name,
                (SELECT COUNT(*) FROM product_relations pr WHERE pr.main_product_id = p.id) as related_products_count
                FROM products p
                LEFT JOIN manufacturers m ON p.manufacturer_id = m.id
                WHERE 1=1
            '''
            params = []
            if manufacturer_id:
                query += ' AND p.manufacturer_id = ?'
                params.append(manufacturer_id)
            if sort_by == 'price':
                query += f' ORDER BY p.price {sort_order}'
            else:
                query += ' ORDER BY p.name ASC'
            cursor = conn.execute(query, params)
            return [Product(**dict(row)) for row in cursor]

    def get_product_by_id(self, product_id):
        with self.db.get_connection() as conn:
            cursor = conn.execute('''
                SELECT p.*, m.name as manufacturer_name,
                (SELECT COUNT(*) FROM product_relations pr WHERE pr.main_product_id = p.id) as related_products_count
                FROM products p
                LEFT JOIN manufacturers m ON p.manufacturer_id = m.id
                WHERE p.id = ?
            ''', (product_id,))
            row = cursor.fetchone()
            return Product(**dict(row)) if row else None

    def save_product(self, product):
        with self.db.get_connection() as conn:
            if product.id:
                conn.execute('''
                    UPDATE products 
                    SET name=?, price=?, description=?, image_path=?, 
                        manufacturer_id=?, is_active=?, updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                ''', (product.name, float(product.price), product.description,
                      product.image_path, product.manufacturer_id, product.is_active, product.id))
                return product.id
            else:
                cursor = conn.execute('''
                    INSERT INTO products 
                    (name, price, description, image_path, manufacturer_id, is_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (product.name, float(product.price), product.description,
                      product.image_path, product.manufacturer_id, product.is_active))
                return cursor.lastrowid

    def delete_product(self, product_id):
        with self.db.get_connection() as conn:
            conn.execute('DELETE FROM product_relations WHERE main_product_id = ? OR related_product_id = ?',
                         (product_id, product_id))
            conn.execute('DELETE FROM products WHERE id = ?', (product_id,))

    def get_all_manufacturers(self):
        with self.db.get_connection() as conn:
            cursor = conn.execute('SELECT * FROM manufacturers ORDER BY name')
            return [Manufacturer(**dict(row)) for row in cursor]

    def get_related_products(self, product_id):
        with self.db.get_connection() as conn:
            cursor = conn.execute('''
                SELECT pr.*, p.name, p.price, p.image_path, p.is_active
                FROM product_relations pr
                JOIN products p ON pr.related_product_id = p.id
                WHERE pr.main_product_id = ? AND p.is_active = TRUE
            ''', (product_id,))
            return [ProductRelation(
                id=row['id'],
                main_product_id=row['main_product_id'],
                related_product_id=row['related_product_id'],
                created_at=row['created_at'],
                related_product=Product(
                    id=row['related_product_id'],
                    name=row['name'],
                    price=row['price'],
                    description='',
                    image_path=row['image_path'],
                    manufacturer_id=0,
                    is_active=row['is_active']
                )
            ) for row in cursor]

    def add_related_product(self, main_product_id, related_product_id):
        with self.db.get_connection() as conn:
            try:
                cursor = conn.execute('''
                    INSERT INTO product_relations (main_product_id, related_product_id)
                    VALUES (?, ?)
                ''', (main_product_id, related_product_id))
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                return None

    def remove_related_product(self, relation_id):
        with self.db.get_connection() as conn:
            conn.execute('DELETE FROM product_relations WHERE id = ?', (relation_id,))

    def get_available_products_for_relation(self, product_id):
        with self.db.get_connection() as conn:
            cursor = conn.execute('''
                SELECT p.*, m.name as manufacturer_name
                FROM products p
                LEFT JOIN manufacturers m ON p.manufacturer_id = m.id
                WHERE p.id != ? AND p.is_active = TRUE
                AND p.id NOT IN (
                    SELECT related_product_id 
                    FROM product_relations 
                    WHERE main_product_id = ?
                )
                ORDER BY p.name
            ''', (product_id, product_id))
            return [Product(**dict(row)) for row in cursor]

    def get_sales_history(self, product_id=None):
        with self.db.get_connection() as conn:
            query = '''
                SELECT sh.*, p.name as product_name
                FROM sales_history sh
                JOIN products p ON sh.product_id = p.id
            '''
            params = []
            if product_id:
                query += ' WHERE sh.product_id = ?'
                params.append(product_id)
            query += ' ORDER BY sh.sale_date DESC'
            cursor = conn.execute(query, params)
            return [SalesHistory(**dict(row)) for row in cursor]

    def add_sale(self, product_id, quantity, customer_info=""):
        with self.db.get_connection() as conn:
            product = self.get_product_by_id(product_id)
            if not product:
                raise ValueError("Товар не найден")
            total_amount = product.price * quantity
            cursor = conn.execute('''
                INSERT INTO sales_history 
                (product_id, quantity, total_amount, customer_info)
                VALUES (?, ?, ?, ?)
            ''', (product_id, quantity, float(total_amount), customer_info))
            return cursor.lastrowid


# ==================== UI COMPONENTS ====================
class ImageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setText("Изображение не выбрано")
        self.setStyleSheet("border: 1px dashed #ccc; padding: 10px;")
        self.setMinimumSize(200, 150)


class RelatedProductsWidget(QListWidget):
    related_product_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setIconSize(QSize(64, 64))
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.itemClicked.connect(self.on_item_clicked)

    def add_related_product(self, product, relation_id):
        item = QListWidgetItem()
        item.setText(f"{product.name}\n{product.price:.2f} ₽")
        item.setToolTip(f"{product.name}\nЦена: {product.price:.2f} ₽")
        pixmap = QPixmap(product.image_path) if product.image_path and os.path.exists(product.image_path) else QPixmap(64, 64)
        if pixmap.isNull():
            pixmap = QPixmap(64, 64)
            pixmap.fill(Qt.lightGray)
        item.setIcon(QIcon(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
        item.setData(Qt.UserRole, relation_id)
        item.setData(Qt.UserRole + 1, product.id)
        self.addItem(item)

    def on_item_clicked(self, item):
        product_id = item.data(Qt.UserRole + 1)
        if product_id:
            self.related_product_clicked.emit(product_id)


class ProductsTableWidget(QTableWidget):
    product_double_clicked = pyqtSignal(int)
    show_sales_history = pyqtSignal(int)
    delete_product_request = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_table()

    def setup_table(self):
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels([
            'ID', 'Название', 'Стоимость', 'Производитель',
            'Активен', 'Связанные товары', 'Действия'
        ])
        header = self.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)

    def populate_table(self, products):
        self.setRowCount(len(products))
        for row, product in enumerate(products):
            self.setItem(row, 0, QTableWidgetItem(str(product.id)))
            name_item = QTableWidgetItem(product.name)
            if not product.is_active:
                name_item.setForeground(QColor(128, 128, 128))
                name_item.setToolTip("Товар неактивен")
            self.setItem(row, 1, name_item)
            self.setItem(row, 2, QTableWidgetItem(f"{product.price:.2f} ₽"))
            self.setItem(row, 3, QTableWidgetItem(product.manufacturer_name or "Не указан"))
            active_item = QTableWidgetItem()
            active_item.setCheckState(Qt.Checked if product.is_active else Qt.Unchecked)
            active_item.setFlags(active_item.flags() & ~Qt.ItemIsEditable)
            self.setItem(row, 4, active_item)
            related_item = QTableWidgetItem(str(product.related_products_count))
            related_item.setTextAlignment(Qt.AlignCenter)
            self.setItem(row, 5, related_item)

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 4, 4, 4)
            sales_btn = QPushButton("📊")
            sales_btn.setToolTip("История продаж")
            sales_btn.clicked.connect(lambda checked, pid=product.id: self.show_sales_history.emit(pid))
            sales_btn.setMaximumWidth(30)
            edit_btn = QPushButton("✏️")
            edit_btn.setToolTip("Редактировать")
            edit_btn.clicked.connect(lambda checked, pid=product.id: self.product_double_clicked.emit(pid))
            edit_btn.setMaximumWidth(30)
            delete_btn = QPushButton("🗑️")
            delete_btn.setToolTip("Удалить")
            delete_btn.clicked.connect(lambda checked, pid=product.id: self.delete_product_request.emit(pid))
            delete_btn.setMaximumWidth(30)
            actions_layout.addWidget(sales_btn)
            actions_layout.addWidget(edit_btn)
            actions_layout.addWidget(delete_btn)
            actions_layout.setAlignment(Qt.AlignCenter)
            self.setCellWidget(row, 6, actions_widget)
        self.resizeColumnsToContents()


# ==================== PRODUCT FORM ====================
class ProductForm(QDialog):
    def __init__(self, product_manager, product_id=None, parent=None):
        super().__init__(parent)
        self.product_manager = product_manager
        self.product_id = product_id
        self.is_editing = product_id is not None
        self.setWindowTitle("Редактировать товар" if self.is_editing else "Добавить товар")
        self.setModal(True)
        self.setMinimumSize(900, 700)
        self.current_image_path = ""
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        tab_widget = QTabWidget()
        self.setup_basic_info_tab(tab_widget)
        self.setup_related_products_tab(tab_widget)
        layout.addWidget(tab_widget)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.validate_and_save)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def setup_basic_info_tab(self, tab_widget):
        basic_widget = QWidget()
        layout = QFormLayout(basic_widget)
        if self.is_editing:
            self.id_edit = QLineEdit()
            self.id_edit.setReadOnly(True)
            layout.addRow("ID:", self.id_edit)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Введите название товара")
        layout.addRow("Название*:", self.name_edit)
        self.price_edit = QLineEdit()
        self.price_edit.setPlaceholderText("0.00")
        layout.addRow("Стоимость*:", self.price_edit)
        self.manufacturer_combo = QComboBox()
        layout.addRow("Производитель:", self.manufacturer_combo)
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(100)
        self.description_edit.setPlaceholderText("Введите описание товара...")
        layout.addRow("Описание:", self.description_edit)
        image_layout = QHBoxLayout()
        self.image_label = ImageLabel()
        self.select_image_btn = QPushButton("Выбрать изображение")
        self.select_image_btn.clicked.connect(self.select_image)
        image_layout.addWidget(self.image_label)
        image_layout.addWidget(self.select_image_btn)
        layout.addRow("Изображение:", image_layout)
        self.active_check = QCheckBox("Товар активен")
        self.active_check.setChecked(True)
        layout.addRow("Статус:", self.active_check)
        tab_widget.addTab(basic_widget, "Основная информация")

    def setup_related_products_tab(self, tab_widget):
        related_widget = QWidget()
        layout = QVBoxLayout(related_widget)
        layout.addWidget(QLabel("Связанные товары:"))
        self.related_list = RelatedProductsWidget()
        self.related_list.related_product_clicked.connect(self.open_related_product)
        layout.addWidget(self.related_list)
        control_layout = QHBoxLayout()
        self.add_related_combo = QComboBox()
        self.add_related_combo.setMinimumWidth(200)
        control_layout.addWidget(self.add_related_combo)
        self.add_related_btn = QPushButton("Добавить")
        self.add_related_btn.clicked.connect(self.add_related_product)
        control_layout.addWidget(self.add_related_btn)
        self.remove_related_btn = QPushButton("Удалить выбранное")
        self.remove_related_btn.clicked.connect(self.remove_related_product)
        control_layout.addWidget(self.remove_related_btn)
        control_layout.addStretch()
        layout.addLayout(control_layout)
        tab_widget.addTab(related_widget, "Связанные товары")

    def open_related_product(self, product_id):
        dialog = ProductForm(self.product_manager, product_id=product_id, parent=self.parent())
        dialog.exec_()

    def load_data(self):
        try:
            manufacturers = self.product_manager.get_all_manufacturers()
            self.manufacturer_combo.clear()
            self.manufacturer_combo.addItem("Не выбран", None)
            for manufacturer in manufacturers:
                self.manufacturer_combo.addItem(manufacturer.name, manufacturer.id)
            if self.is_editing:
                product = self.product_manager.get_product_by_id(self.product_id)
                if product:
                    if hasattr(self, 'id_edit'):
                        self.id_edit.setText(str(product.id))
                    self.name_edit.setText(product.name)
                    self.price_edit.setText(str(product.price))
                    self.description_edit.setText(product.description or "")
                    self.active_check.setChecked(product.is_active)
                    self.current_image_path = product.image_path or ""
                    if self.current_image_path and os.path.exists(self.current_image_path):
                        pixmap = QPixmap(self.current_image_path)
                        self.image_label.setPixmap(pixmap.scaled(200, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    else:
                        self.image_label.setText("Изображение не найдено")
                    index = self.manufacturer_combo.findData(product.manufacturer_id)
                    if index >= 0:
                        self.manufacturer_combo.setCurrentIndex(index)
            self.load_related_products()
            self.load_available_related_products()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные: {str(e)}")

    def load_related_products(self):
        if not self.is_editing:
            return
        self.related_list.clear()
        related_products = self.product_manager.get_related_products(self.product_id)
        for relation in related_products:
            self.related_list.add_related_product(relation.related_product, relation.id)

    def load_available_related_products(self):
        if not self.is_editing:
            self.add_related_combo.setEnabled(False)
            self.add_related_btn.setEnabled(False)
            return
        self.add_related_combo.clear()
        available_products = self.product_manager.get_available_products_for_relation(self.product_id)
        if not available_products:
            self.add_related_combo.addItem("Нет доступных товаров", None)
            self.add_related_btn.setEnabled(False)
        else:
            self.add_related_combo.addItem("Выберите товар...", None)
            for product in available_products:
                self.add_related_combo.addItem(f"{product.name} ({product.price:.2f} ₽)", product.id)
            self.add_related_btn.setEnabled(True)

    def select_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите изображение", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_path:
            filename = f"{uuid.uuid4().hex}{os.path.splitext(file_path)[1]}"
            dest_path = os.path.join(IMAGE_DIR, filename)
            shutil.copy(file_path, dest_path)
            self.current_image_path = dest_path
            pixmap = QPixmap(dest_path)
            self.image_label.setPixmap(pixmap.scaled(200, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def add_related_product(self):
        product_id = self.add_related_combo.currentData()
        if not product_id:
            return
        relation_id = self.product_manager.add_related_product(self.product_id, product_id)
        if relation_id:
            product = self.product_manager.get_product_by_id(product_id)
            self.related_list.add_related_product(product, relation_id)
            self.load_available_related_products()
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось добавить связанный товар")

    def remove_related_product(self):
        current_item = self.related_list.currentItem()
        if not current_item:
            return
        relation_id = current_item.data(Qt.UserRole)
        if relation_id:
            self.product_manager.remove_related_product(relation_id)
            self.related_list.takeItem(self.related_list.row(current_item))
            self.load_available_related_products()

    def validate_and_save(self):
        try:
            name = self.name_edit.text().strip()
            if not name:
                QMessageBox.warning(self, "Ошибка", "Название товара обязательно для заполнения")
                self.name_edit.setFocus()
                return
            try:
                price = Decimal(self.price_edit.text().strip())
                if price < 0:
                    raise ValueError("Цена не может быть отрицательной")
            except (InvalidOperation, ValueError):
                QMessageBox.warning(self, "Ошибка", "Некорректная стоимость товара")
                self.price_edit.setFocus()
                return
            product = Product(
                id=self.product_id if self.is_editing else 0,
                name=name,
                price=price,
                description=self.description_edit.toPlainText().strip(),
                image_path=self.current_image_path,
                manufacturer_id=self.manufacturer_combo.currentData(),
                is_active=self.active_check.isChecked()
            )
            saved_id = self.product_manager.save_product(product)
            if saved_id:
                if not self.is_editing:
                    self.product_id = saved_id
                self.accept()
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось сохранить товар")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при сохранении: {str(e)}")


# ==================== SALES HISTORY WINDOW ====================
class SalesHistoryWindow(QDialog):
    def __init__(self, product_manager, product_id=None, parent=None):
        super().__init__(parent)
        self.product_manager = product_manager
        self.product_id = product_id
        self.setWindowTitle("История продаж товаров")
        self.setModal(True)
        self.setMinimumSize(1000, 600)
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.setup_filters(layout)
        self.setup_sales_table(layout)
        self.setup_statistics(layout)
        self.setup_add_sale_section(layout)

    def setup_filters(self, parent_layout):
        filter_group = QGroupBox("Фильтры")
        filter_layout = QHBoxLayout(filter_group)
        filter_layout.addWidget(QLabel("Товар:"))
        self.product_combo = QComboBox()
        self.product_combo.currentIndexChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.product_combo)
        filter_layout.addStretch()
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.load_data)
        filter_layout.addWidget(refresh_btn)
        parent_layout.addWidget(filter_group)

    def setup_sales_table(self, parent_layout):
        self.sales_table = QTableWidget()
        self.sales_table.setColumnCount(7)
        self.sales_table.setHorizontalHeaderLabels([
            'ID', 'Товар', 'Количество', 'Стоимость за шт.', 'Общая сумма',
            'Дата продажи', 'Информация о клиенте'
        ])
        header = self.sales_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        parent_layout.addWidget(self.sales_table)

    def setup_statistics(self, parent_layout):
        stats_group = QGroupBox("Статистика")
        stats_layout = QHBoxLayout(stats_group)
        self.total_sales_label = QLabel("Общее количество продаж: 0")
        self.total_revenue_label = QLabel("Общая выручка: 0.00 ₽")
        self.avg_sale_label = QLabel("Средний чек: 0.00 ₽")
        stats_layout.addWidget(self.total_sales_label)
        stats_layout.addWidget(self.total_revenue_label)
        stats_layout.addWidget(self.avg_sale_label)
        stats_layout.addStretch()
        parent_layout.addWidget(stats_group)

    def setup_add_sale_section(self, parent_layout):
        add_group = QGroupBox("Добавить новую продажу")
        add_layout = QFormLayout(add_group)
        self.sale_product_combo = QComboBox()
        add_layout.addRow("Товар*:", self.sale_product_combo)
        self.quantity_spin = QSpinBox()
        self.quantity_spin.setMinimum(1)
        self.quantity_spin.setMaximum(1000)
        self.quantity_spin.setValue(1)
        add_layout.addRow("Количество*:", self.quantity_spin)
        self.customer_info_edit = QLineEdit()
        self.customer_info_edit.setPlaceholderText("ФИО клиента или дополнительная информация")
        add_layout.addRow("Информация о клиенте:", self.customer_info_edit)
        add_btn = QPushButton("Добавить продажу")
        add_btn.clicked.connect(self.add_sale)
        add_layout.addRow("", add_btn)
        parent_layout.addWidget(add_group)

    def load_data(self):
        try:
            products = self.product_manager.get_all_products()
            self.product_combo.clear()
            self.product_combo.addItem("Все товары", None)
            self.sale_product_combo.clear()
            for product in products:
                if product.is_active:
                    self.sale_product_combo.addItem(f"{product.name} ({product.price:.2f} ₽)", product.id)
                self.product_combo.addItem(product.name, product.id)
            if self.product_id:
                index = self.product_combo.findData(self.product_id)
                if index >= 0:
                    self.product_combo.setCurrentIndex(index)
            self.apply_filters()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные: {str(e)}")

    def apply_filters(self):
        try:
            product_id = self.product_combo.currentData()
            sales_history = self.product_manager.get_sales_history(product_id)
            self.populate_sales_table(sales_history)
            self.update_statistics(sales_history)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось применить фильтры: {str(e)}")

    def populate_sales_table(self, sales_history):
        self.sales_table.setRowCount(len(sales_history))
        for row, sale in enumerate(sales_history):
            self.sales_table.setItem(row, 0, QTableWidgetItem(str(sale.id)))
            self.sales_table.setItem(row, 1, QTableWidgetItem(sale.product_name))
            quantity_item = QTableWidgetItem(str(sale.quantity))
            quantity_item.setTextAlignment(Qt.AlignCenter)
            self.sales_table.setItem(row, 2, quantity_item)
            unit_price = sale.total_amount / sale.quantity
            self.sales_table.setItem(row, 3, QTableWidgetItem(f"{unit_price:.2f} ₽"))
            total_item = QTableWidgetItem(f"{sale.total_amount:.2f} ₽")
            total_item.setTextAlignment(Qt.AlignRight)
            self.sales_table.setItem(row, 4, total_item)
            sale_date = sale.sale_date.split(' ')[0] if isinstance(sale.sale_date, str) else sale.sale_date.strftime('%Y-%m-%d %H:%M')
            date_item = QTableWidgetItem(sale_date)
            self.sales_table.setItem(row, 5, date_item)
            self.sales_table.setItem(row, 6, QTableWidgetItem(sale.customer_info or ""))
        self.sales_table.resizeColumnsToContents()

    def update_statistics(self, sales_history):
        total_quantity = sum(sale.quantity for sale in sales_history)
        total_revenue = sum(float(sale.total_amount) for sale in sales_history)
        avg_sale = total_revenue / len(sales_history) if sales_history else 0
        self.total_sales_label.setText(f"Общее количество продаж: {total_quantity}")
        self.total_revenue_label.setText(f"Общая выручка: {total_revenue:.2f} ₽")
        self.avg_sale_label.setText(f"Средний чек: {avg_sale:.2f} ₽")

    def add_sale(self):
        try:
            product_id = self.sale_product_combo.currentData()
            quantity = self.quantity_spin.value()
            customer_info = self.customer_info_edit.text().strip()
            if not product_id:
                QMessageBox.warning(self, "Ошибка", "Выберите товар")
                return
            sale_id = self.product_manager.add_sale(product_id, quantity, customer_info)
            if sale_id:
                QMessageBox.information(self, "Успех", "Продажа успешно добавлена")
                self.customer_info_edit.clear()
                self.quantity_spin.setValue(1)
                self.load_data()
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось добавить продажу")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при добавлении продажи: {str(e)}")


# ==================== MAIN WINDOW ====================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db_manager = DatabaseManager()
        self.product_manager = ProductManager(self.db_manager)
        self.init_ui()
        self.load_data()

    def init_ui(self):
        self.setWindowTitle('Информационная система автосервиса "Доеду сам"')
        self.setGeometry(100, 100, 1200, 700)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        self.setup_toolbar()
        self.setup_filters(layout)
        self.setup_products_table(layout)
        self.setup_statusbar()

    def setup_toolbar(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        add_action = QAction('➕ Добавить товар', self)
        add_action.triggered.connect(self.add_product)
        toolbar.addAction(add_action)
        refresh_action = QAction('🔄 Обновить', self)
        refresh_action.triggered.connect(self.load_data)
        toolbar.addAction(refresh_action)

    def setup_filters(self, parent_layout):
        filter_frame = QFrame()
        filter_frame.setFrameStyle(QFrame.StyledPanel)
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.addWidget(QLabel("Производитель:"))
        self.manufacturer_combo = QComboBox()
        self.manufacturer_combo.currentIndexChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.manufacturer_combo)
        filter_layout.addWidget(QLabel("Поиск:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Введите название товара...")
        self.search_edit.textChanged.connect(self.on_search_changed)
        filter_layout.addWidget(self.search_edit)
        filter_layout.addWidget(QLabel("Сортировка:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["По названию", "По цене (возр.)", "По цене (убыв.)"])
        self.sort_combo.currentIndexChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.sort_combo)
        self.show_inactive_check = QCheckBox("Показать неактивные")
        self.show_inactive_check.stateChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.show_inactive_check)
        filter_layout.addStretch()
        parent_layout.addWidget(filter_frame)

    def setup_products_table(self, parent_layout):
        self.products_table = ProductsTableWidget()
        self.products_table.product_double_clicked.connect(self.edit_product)
        self.products_table.show_sales_history.connect(self.show_product_sales_history)
        self.products_table.delete_product_request.connect(self.confirm_delete_product)
        self.products_table.doubleClicked.connect(self.on_table_double_click)
        parent_layout.addWidget(self.products_table)

    def setup_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готово")

    def load_data(self):
        try:
            manufacturers = self.product_manager.get_all_manufacturers()
            self.manufacturer_combo.clear()
            self.manufacturer_combo.addItem("Все производители", None)
            for manufacturer in manufacturers:
                self.manufacturer_combo.addItem(manufacturer.name, manufacturer.id)
            self.apply_filters()
            self.status_bar.showMessage(f"Загружено товаров: {self.products_table.rowCount()}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные: {str(e)}")

    def apply_filters(self):
        try:
            manufacturer_id = self.manufacturer_combo.currentData()
            search_text = self.search_edit.text().strip().lower()
            sort_index = self.sort_combo.currentIndex()
            if sort_index == 0:
                sort_by, sort_order = None, 'ASC'
            elif sort_index == 1:
                sort_by, sort_order = 'price', 'ASC'
            else:
                sort_by, sort_order = 'price', 'DESC'
            products = self.product_manager.get_all_products(manufacturer_id, sort_by, sort_order)
            if search_text:
                products = [p for p in products if search_text in p.name.lower()]
            if not self.show_inactive_check.isChecked():
                products = [p for p in products if p.is_active]
            self.products_table.populate_table(products)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось применить фильтры: {str(e)}")

    def on_search_changed(self):
        if hasattr(self, '_search_timer'):
            self._search_timer.stop()
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self.apply_filters)
        self._search_timer.start(300)

    def on_table_double_click(self, index):
        if index.column() != 6:
            product_id = int(self.products_table.item(index.row(), 0).text())
            self.edit_product(product_id)

    def add_product(self):
        dialog = ProductForm(self.product_manager, parent=self)
        if dialog.exec_() == ProductForm.Accepted:
            self.load_data()
            self.status_bar.showMessage("Товар успешно добавлен")

    def edit_product(self, product_id):
        dialog = ProductForm(self.product_manager, product_id=product_id, parent=self)
        if dialog.exec_() == ProductForm.Accepted:
            self.load_data()
            self.status_bar.showMessage("Товар успешно обновлен")

    def show_product_sales_history(self, product_id):
        product = self.product_manager.get_product_by_id(product_id)
        if product:
            dialog = SalesHistoryWindow(self.product_manager, product_id, parent=self)
            dialog.exec_()

    def confirm_delete_product(self, product_id):
        reply = QMessageBox.question(
            self, "Подтверждение удаления",
            "Вы уверены, что хотите удалить этот товар и все его связи?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                self.product_manager.delete_product(product_id)
                self.load_data()
                self.status_bar.showMessage("Товар успешно удалён")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить товар: {str(e)}")


# ==================== UNIT TESTS ====================
class TestProductManager(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseManager(":memory:")
        self.manager = ProductManager(self.db)

    def test_add_product(self):
        product = Product(
            id=0, name="Тест", price=Decimal("100.00"), description="Тест",
            image_path="", manufacturer_id=None, is_active=True
        )
        pid = self.manager.save_product(product)
        self.assertIsNotNone(pid)
        loaded = self.manager.get_product_by_id(pid)
        self.assertEqual(loaded.name, "Тест")

    def test_delete_product(self):
        product = Product(
            id=0, name="Удалить", price=Decimal("50.00"), description="",
            image_path="", manufacturer_id=None, is_active=True
        )
        pid = self.manager.save_product(product)
        self.manager.delete_product(pid)
        loaded = self.manager.get_product_by_id(pid)
        self.assertIsNone(loaded)

    def test_add_related_product(self):
        p1 = Product(id=0, name="A", price=100, description="", image_path="", manufacturer_id=None, is_active=True)
        p2 = Product(id=0, name="B", price=200, description="", image_path="", manufacturer_id=None, is_active=True)
        id1 = self.manager.save_product(p1)
        id2 = self.manager.save_product(p2)
        rid = self.manager.add_related_product(id1, id2)
        self.assertIsNotNone(rid)
        relations = self.manager.get_related_products(id1)
        self.assertEqual(len(relations), 1)
        self.assertEqual(relations[0].related_product_id, id2)

    def test_sales_history(self):
        product = Product(id=0, name="Продажа", price=Decimal("99.99"), description="", image_path="", manufacturer_id=None, is_active=True)
        pid = self.manager.save_product(product)
        self.manager.add_sale(pid, 2, "Тестовый клиент")
        history = self.manager.get_sales_history(pid)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].quantity, 2)
        self.assertEqual(history[0].total_amount, Decimal("199.98"))


# ==================== MAIN APPLICATION ====================
def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setApplicationName("Автосервис 'Доеду сам'")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Автосервис Доеду сам")
    main_window = MainWindow()
    main_window.show()
    return app.exec_()

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        print("Запуск тестов...")
        unittest.main(argv=['ignored'], exit=False, verbosity=2)
    else:
        sys.exit(main())