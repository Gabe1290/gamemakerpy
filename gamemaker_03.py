import sys
import json
import base64
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QAction, QDockWidget, QListWidget, QListWidgetItem,
    QFileDialog, QWidget, QVBoxLayout, QMessageBox, QInputDialog, QLineEdit,
    QPushButton, QHBoxLayout, QDialog, QFormLayout, QLabel, QColorDialog, QComboBox, QCheckBox
)
from PyQt5.QtGui import QPixmap, QPainter, QColor, QMovie, QIcon
from PyQt5.QtCore import Qt, QByteArray, QBuffer, QSize, QTimer

# -------------------
# Data Classes
# -------------------

class Sprite:
    def __init__(self, name, img_bytes=None, img_format="PNG"):
        self.name = name
        self.img_bytes = img_bytes
        self.img_format = img_format
        self._is_gif = (img_format.lower() == "gif" or (name and name.lower().endswith(".gif")))
        self._movie = None
        self._pixmap = None
        self._prepare()

    def _prepare(self):
        if self.img_bytes:
            if self._is_gif:
                self._movie = QMovie()
                self._movie.setDevice(QBuffer(QByteArray(self.img_bytes)))
                self._movie.start()
                self._movie.jumpToFrame(0)
            else:
                self._pixmap = QPixmap()
                self._pixmap.loadFromData(self.img_bytes)

    def pixmap(self):
        if self._is_gif and self._movie:
            return self._movie.currentPixmap()
        elif self._pixmap:
            return self._pixmap
        return QPixmap(40, 40)

    def to_dict(self):
        return {
            "name": self.name,
            "img_bytes": base64.b64encode(self.img_bytes).decode("utf-8") if self.img_bytes else None,
            "img_format": self.img_format,
        }
    @staticmethod
    def from_dict(d):
        img_bytes = base64.b64decode(d["img_bytes"]) if d.get("img_bytes") else None
        return Sprite(d["name"], img_bytes, d.get("img_format", "PNG"))

class BackgroundResource:
    def __init__(self, name, mode="color", color=None, img_bytes=None, img_format="PNG", tiled=True):
        self.name = name
        self.mode = mode
        self.color = color or QColor(200,200,255)
        self.img_bytes = img_bytes
        self.img_format = img_format
        self.tiled = tiled
        self._is_gif = (img_format and img_format.lower() == "gif") or (name and name.lower().endswith(".gif"))
        self._movie = None
        self._pixmap = None
        self._prepare()

    def _prepare(self):
        if self.mode == "image" and self.img_bytes:
            if self._is_gif:
                self._movie = QMovie()
                self._movie.setDevice(QBuffer(QByteArray(self.img_bytes)))
                self._movie.start()
                self._movie.jumpToFrame(0)
            else:
                self._pixmap = QPixmap()
                self._pixmap.loadFromData(self.img_bytes)

    def pixmap(self):
        if self.mode == "color":
            pix = QPixmap(60, 30)
            pix.fill(self.color)
            return pix
        elif self._is_gif and self._movie:
            return self._movie.currentPixmap()
        elif self._pixmap:
            return self._pixmap
        return QPixmap(60, 30)

    def to_dict(self):
        return {
            "name": self.name,
            "mode": self.mode,
            "color": (self.color.red(), self.color.green(), self.color.blue(), self.color.alpha()) if self.color else None,
            "img_bytes": base64.b64encode(self.img_bytes).decode("utf-8") if self.img_bytes else None,
            "img_format": self.img_format,
            "tiled": self.tiled
        }
    @staticmethod
    def from_dict(d):
        img_bytes = base64.b64decode(d["img_bytes"]) if d.get("img_bytes") else None
        color = QColor(*d["color"]) if d.get("color") else QColor(200,200,255)
        return BackgroundResource(d["name"], d.get("mode", "color"), color, img_bytes, d.get("img_format", "PNG"), d.get("tiled", True))

class GameObjectType:
    def __init__(self, name, sprite_index=None):
        self.name = name
        self.sprite_index = sprite_index

class GameObjectInstance:
    def __init__(self, x, y, object_index):
        self.x = x
        self.y = y
        self.object_index = object_index
    def contains_point(self, px, py, objects, sprites):
        obj = objects[self.object_index]
        if obj.sprite_index is None or obj.sprite_index >= len(sprites):
            return False
        sprite = sprites[obj.sprite_index]
        pix = sprite.pixmap()
        if pix is None:
            return False
        width, height = pix.width(), pix.height()
        return (self.x <= px <= self.x + width) and (self.y <= py <= self.y + height)

class Level:
    def __init__(self, name, width, height, background_index=None):
        self.name = name
        self.width = width
        self.height = height
        self.background_index = background_index
        self.instances = []

# -------------------
# Dialogs
# -------------------

class DragDropLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFixedSize(60, 30)
        self.setStyleSheet("border:1px solid #999; background:white;")
        self.setAlignment(Qt.AlignCenter)
        self.file_dropped_callback = None
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                    event.accept()
                    return
        event.ignore()
    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                    if self.file_dropped_callback:
                        self.file_dropped_callback(url.toLocalFile())
                    break

class SpriteEditDialog(QDialog):
    def __init__(self, name="", img_bytes=None, img_format="PNG", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sprite Properties")
        self.result_name = name
        self.result_img_bytes = img_bytes
        self.result_img_format = img_format

        self.name_edit = QLineEdit(name)
        self.image_btn = QPushButton("Import Image")
        self.image_btn.clicked.connect(self.import_image)
        self.preview_label = DragDropLabel()
        self.preview_label.file_dropped_callback = self.load_image_file
        if img_bytes:
            self.set_preview_image(img_bytes, img_format)
        else:
            self.preview_label.setText("Drop Image\nHere")
        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow(self.image_btn)
        form.addRow("Preview:", self.preview_label)

        btns = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(btns)
        self.setLayout(layout)
    def import_image(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Import Sprite Image", "", "Images (*.png *.jpg *.bmp *.gif)")
        if file_name:
            self.load_image_file(file_name)
    def load_image_file(self, file_name):
        img_format = file_name.split(".")[-1].upper()
        with open(file_name, "rb") as f:
            img_bytes = f.read()
        self.set_preview_image(img_bytes, img_format)
        self.result_img_bytes = img_bytes
        self.result_img_format = img_format
    def set_preview_image(self, img_bytes, img_format):
        if img_format.lower() == "gif":
            movie = QMovie()
            movie.setDevice(QBuffer(QByteArray(img_bytes)))
            movie.start()
            movie.jumpToFrame(0)
            self.preview_label.setMovie(movie)
            movie.start()
        else:
            pix = QPixmap()
            pix.loadFromData(img_bytes)
            self.preview_label.setPixmap(pix.scaled(60, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    def get_values(self):
        name = self.name_edit.text()
        return name, self.result_img_bytes, self.result_img_format

class BackgroundEditDialog(QDialog):
    def __init__(self, name="", mode="color", color=QColor(200,200,255), img_bytes=None, img_format="PNG", tiled=True, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Background Properties")
        self.result_color = color
        self.result_img_bytes = img_bytes
        self.result_img_format = img_format
        self.result_mode = mode
        self.result_tiled = tiled

        self.name_edit = QLineEdit(name)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["color", "image"])
        self.mode_combo.setCurrentText(mode)
        self.color_btn = QPushButton("Pick Color")
        self.color_btn.clicked.connect(self.pick_color)
        self.image_btn = QPushButton("Import Image")
        self.image_btn.clicked.connect(self.import_image)
        self.tiled_check = QCheckBox("Tiled (otherwise stretched)")
        self.tiled_check.setChecked(tiled)
        self.preview_label = DragDropLabel()
        self.preview_label.file_dropped_callback = self.load_image_file
        if mode == "color":
            self.set_preview_color(color)
        elif img_bytes:
            self.set_preview_image(img_bytes, img_format)
        else:
            self.preview_label.setText("Drop Image\nHere")
        self.mode_combo.currentTextChanged.connect(self.update_ui)

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("Type:", self.mode_combo)
        form.addRow(self.color_btn)
        form.addRow(self.image_btn)
        form.addRow("Preview:", self.preview_label)
        form.addRow(self.tiled_check)
        self.update_ui(mode)

        btns = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(btns)
        self.setLayout(layout)
    def set_preview_color(self, color):
        pix = QPixmap(60, 30)
        pix.fill(color)
        self.preview_label.setPixmap(pix)
    def set_preview_image(self, img_bytes, img_format):
        if img_format.lower() == "gif":
            movie = QMovie()
            movie.setDevice(QBuffer(QByteArray(img_bytes)))
            movie.start()
            movie.jumpToFrame(0)
            self.preview_label.setMovie(movie)
            movie.start()
        else:
            pix = QPixmap()
            pix.loadFromData(img_bytes)
            self.preview_label.setPixmap(pix.scaled(60, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    def pick_color(self):
        c = QColorDialog.getColor(self.result_color or QColor(200,200,255), self)
        if c.isValid():
            self.result_color = c
            self.set_preview_color(c)
    def import_image(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Import Background Image", "", "Images (*.png *.jpg *.bmp *.gif)")
        if file_name:
            self.load_image_file(file_name)
    def load_image_file(self, file_name):
        img_format = file_name.split(".")[-1].upper()
        with open(file_name, "rb") as f:
            img_bytes = f.read()
        self.set_preview_image(img_bytes, img_format)
        self.result_img_bytes = img_bytes
        self.result_img_format = img_format
    def update_ui(self, mode=None):
        if not mode:
            mode = self.mode_combo.currentText()
        is_color = (mode == "color")
        self.color_btn.setEnabled(is_color)
        self.image_btn.setEnabled(not is_color)
        self.tiled_check.setEnabled(not is_color)
        self.preview_label.setEnabled(not is_color)
        if is_color:
            self.set_preview_color(self.result_color)
        elif self.result_img_bytes:
            self.set_preview_image(self.result_img_bytes, self.result_img_format)
    def get_values(self):
        name = self.name_edit.text()
        mode = self.mode_combo.currentText()
        tiled = self.tiled_check.isChecked()
        return name, mode, self.result_color, self.result_img_bytes, self.result_img_format, tiled

# -------------------
# Main Canvas
# -------------------

class GameCanvas(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.dragged_instance = None
        self.drag_offset = (0, 0)
        self.setMinimumSize(64, 64)
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update)
        self.animation_timer.start(50)
        self.grid_size = 32
        self.show_grid = True

    def paintEvent(self, event):
        painter = QPainter(self)
        level = self.main_window.get_current_level()
        objects = self.main_window.objects
        sprites = self.main_window.sprites
        backgrounds = self.main_window.backgrounds
        if not level:
            return
        # Draw background
        bg_idx = level.background_index
        if bg_idx is not None and 0 <= bg_idx < len(backgrounds):
            bg = backgrounds[bg_idx]
            if bg.mode == "color":
                painter.fillRect(0, 0, level.width, level.height, bg.color)
            elif bg.mode == "image" and bg.img_bytes:
                pix = bg.pixmap()
                if pix and not pix.isNull():
                    if bg.tiled:
                        w, h = pix.width(), pix.height()
                        for x in range(0, level.width, w):
                            for y in range(0, level.height, h):
                                painter.drawPixmap(x, y, pix)
                    else:
                        painter.drawPixmap(0, 0, pix.scaled(level.width, level.height, Qt.IgnoreAspectRatio))
        else:
            painter.fillRect(0, 0, level.width, level.height, Qt.white)
        # --- Draw grid ---
        if self.show_grid:
            grid_color = QColor(230, 230, 230)
            painter.setPen(grid_color)
            for x in range(0, level.width, self.grid_size):
                painter.drawLine(x, 0, x, level.height)
            for y in range(0, level.height, self.grid_size):
                painter.drawLine(0, y, level.width, y)
        # Draw object instances
        for inst in level.instances:
            obj_idx = inst.object_index
            if obj_idx >= len(objects):
                continue
            obj = objects[obj_idx]
            if obj.sprite_index is not None and 0 <= obj.sprite_index < len(sprites):
                sprite = sprites[obj.sprite_index]
                pix = sprite.pixmap()
                if pix and not pix.isNull():
                    painter.drawPixmap(inst.x, inst.y, pix)

    def mousePressEvent(self, event):
        level = self.main_window.get_current_level()
        objects = self.main_window.objects
        sprites = self.main_window.sprites
        if not level:
            return
        if event.button() == Qt.LeftButton:
            for i in reversed(range(len(level.instances))):
                inst = level.instances[i]
                if inst.contains_point(event.x(), event.y(), objects, sprites):
                    self.dragged_instance = inst
                    self.drag_offset = (event.x() - inst.x, event.y() - inst.y)
                    level.instances.append(level.instances.pop(i))
                    self.update()
                    return
            selected_object_index = self.main_window.selected_object_index
            if selected_object_index is not None:
                snap_x = (event.x() // self.grid_size) * self.grid_size
                snap_y = (event.y() // self.grid_size) * self.grid_size
                level.instances.append(GameObjectInstance(snap_x, snap_y, selected_object_index))
                self.update()
        elif event.button() == Qt.RightButton:
            for i in reversed(range(len(level.instances))):
                inst = level.instances[i]
                if inst.contains_point(event.x(), event.y(), objects, sprites):
                    del level.instances[i]
                    self.update()
                    break

    def mouseMoveEvent(self, event):
        if self.dragged_instance is not None:
            new_x = event.x() - self.drag_offset[0]
            new_y = event.y() - self.drag_offset[1]
            snap_x = (new_x // self.grid_size) * self.grid_size
            snap_y = (new_y // self.grid_size) * self.grid_size
            self.dragged_instance.x = snap_x
            self.dragged_instance.y = snap_y
            self.update()

    def refresh(self):
        self.update()
        level = self.main_window.get_current_level()
        if level:
            self.setFixedSize(level.width, level.height)
        else:
            self.setFixedSize(640, 360)

# -------------------
# Main Window
# -------------------

class GameMakerIDE(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyGameMaker IDE")
        self.setGeometry(100, 100, 1300, 820)
        self.sprites = []
        self.objects = []
        self.levels = []
        self.backgrounds = []
        self.selected_sprite_index = None
        self.selected_object_index = None
        self.selected_level_index = None
        self.selected_background_index = None

        # --- UI Left panel ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setLayout(left_layout)

        # Backgrounds
        left_layout.addWidget(QLabel("<b>Backgrounds</b>"))
        self.background_list = QListWidget()
        self.background_list.setIconSize(QSize(60, 30))
        self.background_list.clicked.connect(self.on_background_selected)
        self.background_list.setAcceptDrops(True)
        self.background_list.dragEnterEvent = self.bg_dragEnterEvent
        self.background_list.dropEvent = self.bg_dropEvent
        left_layout.addWidget(self.background_list)
        bg_btn_layout = QHBoxLayout()
        bg_add_btn = QPushButton("Add")
        bg_add_btn.clicked.connect(self.add_background)
        bg_edit_btn = QPushButton("Edit")
        bg_edit_btn.clicked.connect(self.edit_background)
        bg_rename_btn = QPushButton("Rename")
        bg_rename_btn.clicked.connect(self.rename_background)
        bg_delete_btn = QPushButton("Delete")
        bg_delete_btn.clicked.connect(self.delete_background)
        bg_btn_layout.addWidget(bg_add_btn)
        bg_btn_layout.addWidget(bg_edit_btn)
        bg_btn_layout.addWidget(bg_rename_btn)
        bg_btn_layout.addWidget(bg_delete_btn)
        left_layout.addLayout(bg_btn_layout)

        # Sprites
        left_layout.addWidget(QLabel("<b>Sprites</b>"))
        self.sprite_list = QListWidget()
        self.sprite_list.setIconSize(QSize(60, 30))
        self.sprite_list.clicked.connect(self.on_sprite_selected)
        self.sprite_list.setAcceptDrops(True)
        self.sprite_list.dragEnterEvent = self.sprite_dragEnterEvent
        self.sprite_list.dropEvent = self.sprite_dropEvent
        left_layout.addWidget(self.sprite_list)
        sprite_btn_layout = QHBoxLayout()
        sprite_add_btn = QPushButton("Add")
        sprite_add_btn.clicked.connect(self.add_sprite)
        sprite_edit_btn = QPushButton("Edit")
        sprite_edit_btn.clicked.connect(self.edit_sprite)
        sprite_rename_btn = QPushButton("Rename")
        sprite_rename_btn.clicked.connect(self.rename_sprite)
        sprite_delete_btn = QPushButton("Delete")
        sprite_delete_btn.clicked.connect(self.delete_sprite)
        sprite_btn_layout.addWidget(sprite_add_btn)
        sprite_btn_layout.addWidget(sprite_edit_btn)
        sprite_btn_layout.addWidget(sprite_rename_btn)
        sprite_btn_layout.addWidget(sprite_delete_btn)
        left_layout.addLayout(sprite_btn_layout)

        # Objects
        left_layout.addWidget(QLabel("<b>Objects</b>"))
        self.object_list = QListWidget()
        self.object_list.clicked.connect(self.on_object_selected)
        left_layout.addWidget(self.object_list)
        object_btn_layout = QHBoxLayout()
        object_add_btn = QPushButton("Add")
        object_add_btn.clicked.connect(self.add_object)
        object_edit_btn = QPushButton("Edit")
        object_edit_btn.clicked.connect(self.edit_object)
        object_rename_btn = QPushButton("Rename")
        object_rename_btn.clicked.connect(self.rename_object)
        object_delete_btn = QPushButton("Delete")
        object_delete_btn.clicked.connect(self.delete_object)
        object_btn_layout.addWidget(object_add_btn)
        object_btn_layout.addWidget(object_edit_btn)
        object_btn_layout.addWidget(object_rename_btn)
        object_btn_layout.addWidget(object_delete_btn)
        left_layout.addLayout(object_btn_layout)

        # Levels
        left_layout.addWidget(QLabel("<b>Levels</b>"))
        self.level_list = QListWidget()
        self.level_list.clicked.connect(self.on_level_selected)
        left_layout.addWidget(self.level_list)
        level_btn_layout = QHBoxLayout()
        level_add_btn = QPushButton("Add")
        level_add_btn.clicked.connect(self.add_level)
        level_rename_btn = QPushButton("Rename")
        level_rename_btn.clicked.connect(self.rename_level)
        level_size_btn = QPushButton("Size")
        level_size_btn.clicked.connect(self.set_level_screen_size)
        level_bg_btn = QPushButton("Background")
        level_bg_btn.clicked.connect(self.set_level_background)
        level_delete_btn = QPushButton("Delete")
        level_delete_btn.clicked.connect(self.delete_level)
        level_btn_layout.addWidget(level_add_btn)
        level_btn_layout.addWidget(level_rename_btn)
        level_btn_layout.addWidget(level_size_btn)
        level_btn_layout.addWidget(level_bg_btn)
        level_btn_layout.addWidget(level_delete_btn)
        left_layout.addLayout(level_btn_layout)

        left_layout.addStretch()
        dock = QDockWidget("Resources", self)
        dock.setWidget(left_panel)
        dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

        # Canvas
        self.canvas = GameCanvas(self)
        self.setCentralWidget(self.canvas)

        # Menus
        menubar = self.menuBar()
        file_menu = menubar.addMenu('File')
        open_action = QAction('Open', self)
        open_action.triggered.connect(self.open_project)
        file_menu.addAction(open_action)
        save_action = QAction('Save', self)
        save_action.triggered.connect(self.save_project)
        file_menu.addAction(save_action)

        grid_menu = menubar.addMenu("Grid")
        self.grid_size_action = QAction(f"Grid Size: {self.canvas.grid_size}", self)
        self.grid_size_action.triggered.connect(self.set_grid_size)
        grid_menu.addAction(self.grid_size_action)
        self.toggle_grid_action = QAction("Show Grid", self, checkable=True)
        self.toggle_grid_action.setChecked(self.canvas.show_grid)
        self.toggle_grid_action.triggered.connect(self.toggle_grid)
        grid_menu.addAction(self.toggle_grid_action)

        # Start with default resources
        self.add_background(init=True)
        self.add_level(init=True)
        self.add_object(init=True)
        self.add_sprite(init=True)

        # Animated GIFs update in lists
        self.list_timer = QTimer(self)
        self.list_timer.timeout.connect(self.refresh_list_icons)
        self.list_timer.start(80)

    # --- Grid menu actions ---
    def set_grid_size(self):
        sizes = ["8", "16", "32", "64", "128"]
        cur_idx = sizes.index(str(self.canvas.grid_size)) if str(self.canvas.grid_size) in sizes else 2
        new_size, ok = QInputDialog.getItem(self, "Select Grid Size", "Grid Size:", sizes, cur_idx, False)
        if ok and new_size.isdigit():
            self.canvas.grid_size = int(new_size)
            self.grid_size_action.setText(f"Grid Size: {new_size}")
            self.canvas.update()

    def toggle_grid(self):
        self.canvas.show_grid = self.toggle_grid_action.isChecked()
        self.canvas.update()

    def refresh_list_icons(self):
        # Sprites
        for i, sprite in enumerate(self.sprites):
            if sprite._is_gif and sprite._movie:
                item = self.sprite_list.item(i)
                icon = QPixmap(sprite.pixmap()).scaled(60, 30, Qt.KeepAspectRatio)
                item.setIcon(QIcon(icon))
        # Backgrounds
        for i, bg in enumerate(self.backgrounds):
            if bg.mode == "color":
                icon = QPixmap(60, 30)
                icon.fill(bg.color)
            elif bg._is_gif and bg._movie:
                icon = QPixmap(bg.pixmap()).scaled(60, 30, Qt.KeepAspectRatio)
            elif bg._pixmap:
                icon = QPixmap(bg._pixmap).scaled(60, 30, Qt.KeepAspectRatio)
            else:
                icon = QPixmap(60, 30)
            self.background_list.item(i).setIcon(QIcon(icon))

    def bg_dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                    event.accept()
                    return
        event.ignore()
    def bg_dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                    file_name = url.toLocalFile()
                    img_format = file_name.split(".")[-1].upper()
                    with open(file_name, "rb") as f:
                        img_bytes = f.read()
                    bg = BackgroundResource(
                        name=file_name.split("/")[-1],
                        mode="image",
                        color=None,
                        img_bytes=img_bytes,
                        img_format=img_format,
                        tiled=True,
                    )
                    self.backgrounds.append(bg)
                    item = QListWidgetItem(bg.name)
                    icon = QPixmap(bg.pixmap()).scaled(60, 30, Qt.KeepAspectRatio)
                    item.setIcon(QIcon(icon))
                    self.background_list.addItem(item)
                    self.refresh_canvas()
                    break
    def add_background(self, init=False):
        if not init:
            dlg = BackgroundEditDialog(parent=self)
            if dlg.exec_():
                name, mode, color, img_bytes, img_format, tiled = dlg.get_values()
            else:
                return
        else:
            name, mode, color, img_bytes, img_format, tiled = "Background 1", "color", QColor(200,200,255), None, "PNG", True
        bg = BackgroundResource(name, mode, color, img_bytes, img_format, tiled)
        self.backgrounds.append(bg)
        item = QListWidgetItem(name)
        icon = QPixmap(bg.pixmap()).scaled(60, 30, Qt.KeepAspectRatio)
        item.setIcon(QIcon(icon))
        self.background_list.addItem(item)
        self.refresh_canvas()
    def edit_background(self):
        idx = self.selected_background_index
        if idx is not None and 0 <= idx < len(self.backgrounds):
            bg = self.backgrounds[idx]
            dlg = BackgroundEditDialog(bg.name, bg.mode, bg.color, bg.img_bytes, bg.img_format, bg.tiled, self)
            if dlg.exec_():
                name, mode, color, img_bytes, img_format, tiled = dlg.get_values()
                bg.name = name
                bg.mode = mode
                bg.color = color
                bg.img_bytes = img_bytes
                bg.img_format = img_format
                bg.tiled = tiled
                bg._prepare()
                self.background_list.item(idx).setText(name)
                icon = QPixmap(bg.pixmap()).scaled(60, 30, Qt.KeepAspectRatio)
                self.background_list.item(idx).setIcon(QIcon(icon))
                self.refresh_canvas()
    def rename_background(self):
        idx = self.selected_background_index
        if idx is not None and 0 <= idx < len(self.backgrounds):
            name, ok = QInputDialog.getText(self, "Rename Background", "New name:", QLineEdit.Normal, self.backgrounds[idx].name)
            if ok and name.strip():
                self.backgrounds[idx].name = name
                self.background_list.item(idx).setText(name)
                self.refresh_canvas()
    def delete_background(self):
        idx = self.selected_background_index
        if idx is not None and 0 <= idx < len(self.backgrounds):
            confirm = QMessageBox.question(self, "Delete Background", "Delete this background? Levels using it will show white.",
                                          QMessageBox.Yes | QMessageBox.No)
            if confirm == QMessageBox.Yes:
                for lvl in self.levels:
                    if lvl.background_index == idx:
                        lvl.background_index = None
                    elif lvl.background_index is not None and lvl.background_index > idx:
                        lvl.background_index -= 1
                del self.backgrounds[idx]
                self.background_list.takeItem(idx)
                self.selected_background_index = None
                self.refresh_canvas()
    def on_background_selected(self, index):
        self.selected_background_index = index.row()

    # --- Sprites ---
    def sprite_dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                    event.accept()
                    return
        event.ignore()
    def sprite_dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                    file_name = url.toLocalFile()
                    img_format = file_name.split(".")[-1].upper()
                    with open(file_name, "rb") as f:
                        img_bytes = f.read()
                    sprite = Sprite(file_name.split("/")[-1], img_bytes, img_format)
                    self.sprites.append(sprite)
                    item = QListWidgetItem(sprite.name)
                    icon = QPixmap(sprite.pixmap()).scaled(60, 30, Qt.KeepAspectRatio)
                    item.setIcon(QIcon(icon))
                    self.sprite_list.addItem(item)
                    self.refresh_canvas()
                    break
    def add_sprite(self, init=False):
        if not init:
            dlg = SpriteEditDialog(parent=self)
            if dlg.exec_():
                name, img_bytes, img_format = dlg.get_values()
            else:
                return
        else:
            name, img_bytes, img_format = "Sprite 1", None, "PNG"
        sprite = Sprite(name, img_bytes, img_format)
        self.sprites.append(sprite)
        item = QListWidgetItem(name)
        icon = QPixmap(sprite.pixmap()).scaled(60, 30, Qt.KeepAspectRatio)
        item.setIcon(QIcon(icon))
        self.sprite_list.addItem(item)
        self.refresh_canvas()
    def edit_sprite(self):
        idx = self.selected_sprite_index
        if idx is not None and 0 <= idx < len(self.sprites):
            sprite = self.sprites[idx]
            dlg = SpriteEditDialog(sprite.name, sprite.img_bytes, sprite.img_format, self)
            if dlg.exec_():
                name, img_bytes, img_format = dlg.get_values()
                sprite.name = name
                sprite.img_bytes = img_bytes
                sprite.img_format = img_format
                sprite._prepare()
                self.sprite_list.item(idx).setText(name)
                icon = QPixmap(sprite.pixmap()).scaled(60, 30, Qt.KeepAspectRatio)
                self.sprite_list.item(idx).setIcon(QIcon(icon))
                self.refresh_canvas()
    def rename_sprite(self):
        idx = self.selected_sprite_index
        if idx is not None and 0 <= idx < len(self.sprites):
            name, ok = QInputDialog.getText(self, "Rename Sprite", "New name:", QLineEdit.Normal, self.sprites[idx].name)
            if ok and name.strip():
                self.sprites[idx].name = name
                self.sprite_list.item(idx).setText(name)
                self.refresh_canvas()
    def delete_sprite(self):
        idx = self.selected_sprite_index
        if idx is not None and 0 <= idx < len(self.sprites):
            confirm = QMessageBox.question(self, "Delete Sprite", "Delete this sprite? Objects using it will show no sprite.",
                                          QMessageBox.Yes | QMessageBox.No)
            if confirm == QMessageBox.Yes:
                for obj in self.objects:
                    if obj.sprite_index == idx:
                        obj.sprite_index = None
                    elif obj.sprite_index is not None and obj.sprite_index > idx:
                        obj.sprite_index -= 1
                del self.sprites[idx]
                self.sprite_list.takeItem(idx)
                self.selected_sprite_index = None
                self.refresh_canvas()
    def on_sprite_selected(self, index):
        self.selected_sprite_index = index.row()

    # --- Objects ---
    def add_object(self, init=False):
        if not init:
            name, ok = QInputDialog.getText(self, "Add Object", "Object name:")
            if not ok or not name.strip():
                return
            sprite_index = None
        else:
            name = "Object 1"
            sprite_index = None
        obj = GameObjectType(name, sprite_index)
        self.objects.append(obj)
        self.object_list.addItem(name)
        self.selected_object_index = len(self.objects) - 1
        self.object_list.setCurrentRow(self.selected_object_index)
        self.refresh_canvas()
    def edit_object(self):
        idx = self.selected_object_index
        if idx is not None and 0 <= idx < len(self.objects):
            obj = self.objects[idx]
            dlg = QInputDialog(self)
            dlg.setWindowTitle("Object Properties")
            choices = ["None"] + [s.name for s in self.sprites]
            dlg.setLabelText(f"Sprite for object (0=None):")
            dlg.setComboBoxItems(choices)
            dlg.setComboBoxEditable(False)
            dlg.setTextValue(choices[obj.sprite_index+1] if obj.sprite_index is not None else choices[0])
            if dlg.exec_():
                val = dlg.textValue()
                idx_val = choices.index(val) - 1
                obj.sprite_index = idx_val if idx_val >= 0 else None
                self.refresh_canvas()
    def rename_object(self):
        idx = self.selected_object_index
        if idx is not None and 0 <= idx < len(self.objects):
            name, ok = QInputDialog.getText(self, "Rename Object", "New name:", QLineEdit.Normal, self.objects[idx].name)
            if ok and name.strip():
                self.objects[idx].name = name
                self.object_list.item(idx).setText(name)
                self.refresh_canvas()
    def delete_object(self):
        idx = self.selected_object_index
        if idx is not None and 0 <= idx < len(self.objects):
            confirm = QMessageBox.question(self, "Delete Object", "Delete this object and all placed instances?",
                                          QMessageBox.Yes | QMessageBox.No)
            if confirm == QMessageBox.Yes:
                for lvl in self.levels:
                    lvl.instances = [inst for inst in lvl.instances if inst.object_index != idx]
                    for inst in lvl.instances:
                        if inst.object_index > idx:
                            inst.object_index -= 1
                del self.objects[idx]
                self.object_list.takeItem(idx)
                self.selected_object_index = None
                self.refresh_canvas()
    def on_object_selected(self, index):
        self.selected_object_index = index.row()

    # --- Levels ---
    def add_level(self, init=False):
        if not init:
            name, ok = QInputDialog.getText(self, "Add Level", "Level name:")
            if not ok or not name.strip():
                return
            width, height = 640, 360
            background_index = 0 if self.backgrounds else None
        else:
            name, width, height, background_index = "Level 1", 640, 360, 0
        lvl = Level(name, width, height, background_index)
        self.levels.append(lvl)
        self.level_list.addItem(name)
        self.selected_level_index = len(self.levels) - 1
        self.level_list.setCurrentRow(self.selected_level_index)
        self.refresh_canvas()
    def rename_level(self):
        idx = self.selected_level_index
        if idx is not None and 0 <= idx < len(self.levels):
            name, ok = QInputDialog.getText(self, "Rename Level", "New name:", QLineEdit.Normal, self.levels[idx].name)
            if ok and name.strip():
                self.levels[idx].name = name
                self.level_list.item(idx).setText(name)
                self.refresh_canvas()
    def set_level_screen_size(self):
        lvl = self.get_current_level()
        if not lvl:
            return
        dlg = QInputDialog(self)
        dlg.setWindowTitle("Resize Level")
        dlg.setLabelText("Width,Height (e.g. 800,600):")
        dlg.setTextValue(f"{lvl.width},{lvl.height}")
        if dlg.exec_():
            try:
                w, h = map(int, dlg.textValue().split(","))
                lvl.width = w
                lvl.height = h
                self.refresh_canvas()
            except Exception:
                QMessageBox.warning(self, "Error", "Invalid format.")
    def set_level_background(self):
        lvl = self.get_current_level()
        if not lvl:
            return
        if not self.backgrounds:
            QMessageBox.warning(self, "Error", "No backgrounds defined.")
            return
        idx, ok = QInputDialog.getInt(self, "Set Level Background",
                                      f"Background index for this level (0..{len(self.backgrounds)-1}):",
                                      value=lvl.background_index if lvl.background_index is not None else 0,
                                      min=0, max=len(self.backgrounds)-1)
        if ok:
            lvl.background_index = idx
            self.refresh_canvas()
    def delete_level(self):
        idx = self.selected_level_index
        if idx is not None and 0 <= idx < len(self.levels):
            confirm = QMessageBox.question(self, "Delete Level", "Delete this level? This cannot be undone.",
                                          QMessageBox.Yes | QMessageBox.No)
            if confirm == QMessageBox.Yes:
                del self.levels[idx]
                self.level_list.takeItem(idx)
                if self.levels:
                    self.selected_level_index = min(idx, len(self.levels) - 1)
                    self.level_list.setCurrentRow(self.selected_level_index)
                else:
                    self.selected_level_index = None
                self.refresh_canvas()
    def on_level_selected(self, index):
        self.selected_level_index = index.row()
        self.refresh_canvas()
    def get_current_level(self):
        if self.selected_level_index is not None and 0 <= self.selected_level_index < len(self.levels):
            return self.levels[self.selected_level_index]
        return None

    # --- Save/Load ---
    def save_project(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "PyGameMaker Project (*.pgm.json)")
        if file_name:
            data = {
                "backgrounds": [bg.to_dict() for bg in self.backgrounds],
                "sprites": [sprite.to_dict() for sprite in self.sprites],
                "objects": [
                    {"name": obj.name, "sprite_index": obj.sprite_index}
                    for obj in self.objects
                ],
                "levels": [
                    {
                        "name": lvl.name,
                        "width": lvl.width,
                        "height": lvl.height,
                        "background_index": lvl.background_index,
                        "instances": [
                            {"x": inst.x, "y": inst.y, "object_index": inst.object_index}
                            for inst in lvl.instances
                        ]
                    } for lvl in self.levels
                ],
                "selected_level_index": self.selected_level_index,
                "selected_object_index": self.selected_object_index,
                "selected_background_index": self.selected_background_index
            }
            try:
                with open(file_name, 'w') as f:
                    json.dump(data, f)
                QMessageBox.information(self, "Save", "Project saved successfully!")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to save project: {e}")
    def open_project(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Project", "", "PyGameMaker Project (*.pgm.json)")
        if file_name:
            try:
                with open(file_name, 'r') as f:
                    data = json.load(f)
                # Backgrounds
                self.backgrounds = []
                self.background_list.clear()
                for bg_info in data["backgrounds"]:
                    bg = BackgroundResource.from_dict(bg_info)
                    item = QListWidgetItem(bg.name)
                    icon = QPixmap(bg.pixmap()).scaled(60, 30, Qt.KeepAspectRatio)
                    item.setIcon(QIcon(icon))
                    self.background_list.addItem(item)
                    self.backgrounds.append(bg)
                # Sprites
                self.sprites = []
                self.sprite_list.clear()
                for sprite_info in data["sprites"]:
                    sprite = Sprite.from_dict(sprite_info)
                    item = QListWidgetItem(sprite.name)
                    icon = QPixmap(sprite.pixmap()).scaled(60, 30, Qt.KeepAspectRatio)
                    item.setIcon(QIcon(icon))
                    self.sprite_list.addItem(item)
                    self.sprites.append(sprite)
                # Objects
                self.objects = []
                self.object_list.clear()
                for obj_info in data["objects"]:
                    obj = GameObjectType(obj_info["name"], obj_info["sprite_index"])
                    self.objects.append(obj)
                    self.object_list.addItem(obj_info["name"])
                # Levels
                self.levels = []
                self.level_list.clear()
                for lvl_info in data["levels"]:
                    lvl = Level(lvl_info["name"], lvl_info["width"], lvl_info["height"], lvl_info.get("background_index"))
                    for inst in lvl_info["instances"]:
                        if 0 <= inst["object_index"] < len(self.objects):
                            lvl.instances.append(GameObjectInstance(inst["x"], inst["y"], inst["object_index"]))
                    self.levels.append(lvl)
                    self.level_list.addItem(lvl.name)
                # Handle selected indices safely!
                self.selected_level_index = data.get("selected_level_index")
                self.selected_object_index = data.get("selected_object_index")
                self.selected_background_index = data.get("selected_background_index")
                if self.levels:
                    if self.selected_level_index is not None:
                        self.level_list.setCurrentRow(self.selected_level_index)
                    else:
                        self.selected_level_index = 0
                        self.level_list.setCurrentRow(0)
                if self.objects:
                    if self.selected_object_index is not None:
                        self.object_list.setCurrentRow(self.selected_object_index)
                    else:
                        self.selected_object_index = 0
                        self.object_list.setCurrentRow(0)
                if self.backgrounds:
                    if self.selected_background_index is not None:
                        self.background_list.setCurrentRow(self.selected_background_index)
                    else:
                        self.selected_background_index = 0
                        self.background_list.setCurrentRow(0)
                self.refresh_canvas()
                QMessageBox.information(self, "Open", "Project opened successfully!")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to open project: {e}")
    def refresh_canvas(self):
        self.canvas.refresh()

if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        window = GameMakerIDE()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        import traceback
        print("Crash:", e)
        print(traceback.format_exc())
        QMessageBox.critical(None, "Fatal Error", str(e))
