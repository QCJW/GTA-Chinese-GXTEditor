import os
import shutil
import sys
import winreg  # 用于Windows文件关联
from pathlib import Path
from PySide6.QtGui import QIcon

from PySide6.QtCore import Qt, QTimer, QRect, Signal, QPoint
from PySide6.QtGui import (QPalette, QColor, QAction, QGuiApplication, QFont, 
                          QPixmap, QPainter, QImage, QFontDatabase, QCursor)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QListWidget, QTableWidget, QTableWidgetItem,
    QFileDialog, QLineEdit, QMessageBox, QVBoxLayout, QWidget, QMenuBar, QMenu,
    QStatusBar, QPushButton, QHBoxLayout, QLabel, QInputDialog, QTextEdit, QDialog,
    QDialogButtonBox, QAbstractItemView, QHeaderView, QCheckBox, QComboBox, QFontDialog,
    QScrollArea, QSizePolicy
)

# --- 导入核心逻辑 ---
from gxt_parser import getVersion, getReader
from IVGXT import generate_binary as write_iv, load_txt as load_iv_txt, process_special_chars, gta4_gxt_hash
from VCGXT import VCGXT
from SAGXT import SAGXT
from LCGXT import LCGXT

# ========== 字体生成器及相关组件 ==========

class FontTextureGenerator:
    """GTA 字体贴图生成器核心类"""
    def __init__(self):
        self.margin = 2
        self.y_offset = -4
        self.bg_color = QColor(0, 0, 0, 0)
        self.text_color = QColor('white')

    def create_pixmap(self, characters, version, texture_size, font):
        """创建并返回 QPixmap 对象，用于预览或保存"""
        if not characters:
            return QPixmap()

        chars_per_line = 64 if texture_size == 4096 else 32
        pixmap = QPixmap(texture_size, texture_size)
        pixmap.fill(self.bg_color)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(font)
        painter.setPen(self.text_color)

        char_width = texture_size // chars_per_line
        char_height_map = {"III": 80, "VC": 64, "SA": 80, "IV": 66}
        char_height = char_height_map.get(version, 64)

        x, y = 0, 0
        for char in characters:
            draw_rect = QRect(
                x + self.margin, y + self.margin + self.y_offset,
                char_width - 2 * self.margin, char_height - 2 * self.margin
            )
            painter.drawText(draw_rect, Qt.AlignmentFlag.AlignCenter, char)
            x += char_width
            if x >= texture_size:
                x = 0
                y += char_height
                if y + char_height > texture_size:
                    print(f"警告：字符过多，部分字符 '{char}' 之后的内容可能未被绘制")
                    break
        painter.end()
        return pixmap

    def generate_and_save(self, characters, output_path, version, texture_size, font):
        """生成贴图并保存到文件"""
        pixmap = self.create_pixmap(characters, version, texture_size, font)
        if not pixmap.isNull():
            if not pixmap.save(output_path, "PNG"):
                raise IOError(f"无法保存文件到 {output_path}")

    def generate_html_preview(self, settings, texture_filename, output_path):
        """生成HTML预览文件"""
        char_width = settings['resolution'] // (64 if settings['resolution'] == 4096 else 32)
        char_height_map = {"III": 80, "VC": 64, "SA": 80, "IV": 66}
        char_height = char_height_map.get(settings['version'], 64)

        html_content = f"""
        <!DOCTYPE html>
        <html lang="zh-CN"><head><meta charset="UTF-8"><title>字体贴图预览</title>
        <style>
            body {{ font-family: sans-serif; background-color: #1e1e1e; color: #e0e0e0; }}
            .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
            h1, h2 {{ text-align: center; color: #4fc3f7; }}
            .info-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; background-color: #2d2d2d; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
            .info-item {{ margin: 5px 0; }} .info-item strong {{ color: #82b1ff; }}
            .texture-container {{ text-align: center; margin-bottom: 30px; }}
            .texture-img {{ max-width: 100%; border: 1px solid #444; }}
            .char-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap: 10px; margin-top: 20px; }}
            .char-item {{ background-color: #2d2d2d; border: 1px solid #444; border-radius: 4px; padding: 10px; text-align: center; }}
            .char-display {{ font-size: 24px; margin-bottom: 5px; height: 40px; display: flex; align-items: center; justify-content: center; }}
            .char-code {{ font-size: 12px; color: #aaa; }}
        </style></head><body><div class="container">
            <h1>字体贴图预览</h1>
            <div class="info-grid">
                <div class="info-item"><strong>游戏版本:</strong> {settings['version']}</div>
                <div class="info-item"><strong>贴图尺寸:</strong> {settings['resolution']}x{settings['resolution']}px</div>
                <div class="info-item"><strong>字符总数:</strong> {len(settings['characters'])}</div>
                <div class="info-item"><strong>单元格尺寸:</strong> {char_width}x{char_height}px</div>
                <div class="info-item"><strong>Normal 字体:</strong> {settings['font_normal'].family()}, {settings['font_normal'].pointSize()}pt</div>
        """
        if 'font_slant' in settings:
            html_content += f"<div class=\"info-item\"><strong>Slant 字体:</strong> {settings['font_slant'].family()}, {settings['font_slant'].pointSize()}pt</div>"
        
        html_content += f"""
            </div>
            <div class="texture-container"><h2>字体贴图</h2><img src="{os.path.basename(texture_filename)}" alt="字体贴图" class="texture-img"></div>
            
            <div class="char-container">
                <h2>字符列表 (共 {len(settings['characters'])} 个字符)</h2>
                <div class="char-grid">
        """
        
        # 添加字符网格
        for char in settings['characters']:
            char_code = ord(char)
            html_content += f"""
                <div class="char-item">
                    <div class="char-display">{char}</div>
                    <div class="char-code">U+{char_code:04X}</div>
                </div>
            """
        
        html_content += """
                </div>
            </div>
        </div></body></html>
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

class ImageViewer(QDialog):
    """图片查看器对话框，支持缩放"""
    def __init__(self, pixmap, title="图片预览", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.original_pixmap = pixmap
        self.scale_factor = 1.0
        self.drag_position = QPoint()
        
        # 创建主部件
        self.image_label = QLabel()
        self.image_label.setPixmap(pixmap)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(False)
        
        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidgetResizable(True)
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.scroll_area)
        
        # 初始缩放以适应窗口
        self.fit_to_window()
        
    def fit_to_window(self):
        """初始缩放以适应窗口"""
        if not self.original_pixmap.isNull():
            # 计算适合窗口的缩放比例
            screen_size = QGuiApplication.primaryScreen().availableGeometry()
            max_width = int(screen_size.width() * 0.8)
            max_height = int(screen_size.height() * 0.8)
            
            pixmap_size = self.original_pixmap.size()
            width_ratio = max_width / pixmap_size.width()
            height_ratio = max_height / pixmap_size.height()
            
            # 取最小比例，确保完整显示
            self.scale_factor = min(width_ratio, height_ratio, 1.0)
            self.update_image()
            
            # 调整窗口大小
            new_width = min(pixmap_size.width() * self.scale_factor, max_width)
            new_height = min(pixmap_size.height() * self.scale_factor, max_height)
            self.resize(int(new_width), int(new_height))
    
    def wheelEvent(self, event):
        # 缩放因子
        zoom_factor = 1.1
        
        # 检查Ctrl键是否按下
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # 保存旧的位置
            old_pos = self.scroll_area.mapFromGlobal(QCursor.pos())
            
            # 计算缩放
            if event.angleDelta().y() > 0:
                # 放大
                self.scale_factor *= zoom_factor
            else:
                # 缩小
                self.scale_factor /= zoom_factor
                # 最小缩放限制
                if self.scale_factor < 0.1:
                    self.scale_factor = 0.1
                    
            # 设置新的大小
            self.update_image()
            
            # 调整滚动条以保持鼠标下的位置不变
            new_pos = old_pos * self.scale_factor
            self.scroll_area.horizontalScrollBar().setValue(int(new_pos.x() - self.scroll_area.width()/2 + self.scroll_area.horizontalScrollBar().value()))
            self.scroll_area.verticalScrollBar().setValue(int(new_pos.y() - self.scroll_area.height()/2 + self.scroll_area.verticalScrollBar().value()))
            
            event.accept()
        else:
            # 没有Ctrl键，执行默认的滚动行为
            super().wheelEvent(event)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
    
    def update_image(self):
        """根据缩放因子更新图像"""
        if not self.original_pixmap.isNull():
            new_size = self.original_pixmap.size() * self.scale_factor
            scaled_pixmap = self.original_pixmap.scaled(
                new_size, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.resize(new_size)

class ClickableLabel(QLabel):
    """可点击的QLabel"""
    clicked = Signal()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pixmap_cache = None

    def mousePressEvent(self, event):
        self.clicked.emit()

class FontSelectionWidget(QWidget):
    """封装的字体选择控件"""
    def __init__(self, title, default_font=QFont("Microsoft YaHei", 42)):
        super().__init__()
        self.font = default_font
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        
        title_label = QLabel(f"<b>{title}</b>")
        layout.addWidget(title_label)

        self.font_display_label = QLabel()
        self.font_display_label.setMinimumHeight(30)
        
        btn_layout = QHBoxLayout()
        select_system_button = QPushButton("选择系统字体...")
        select_system_button.clicked.connect(self.select_system_font)
        browse_font_button = QPushButton("浏览文件...")
        browse_font_button.clicked.connect(self.select_font_file)
        
        btn_layout.addWidget(self.font_display_label, 1)
        btn_layout.addWidget(select_system_button)
        btn_layout.addWidget(browse_font_button)
        layout.addLayout(btn_layout)
        
        self.update_font_display()

    def select_system_font(self):
        ok, font = QFontDialog.getFont(self.font, self, "选择字体")
        if ok:
            self.font = font
            self.update_font_display()

    def select_font_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择字体文件", "", "字体文件 (*.ttf *.otf)")
        if path:
            font_id = QFontDatabase.addApplicationFont(path)
            if font_id != -1:
                family = QFontDatabase.applicationFontFamilies(font_id)[0]
                self.font.setFamily(family)
                self.update_font_display()
            else:
                QMessageBox.warning(self, "错误", "无法加载字体文件。")

    def update_font_display(self):
        style = []
        if self.font.bold(): style.append("Bold")
        if self.font.italic(): style.append("Italic")
        style_str = ", ".join(style) if style else "Regular"
        self.font_display_label.setText(f"{self.font.family()}, {self.font.pointSize()}pt, {style_str}")

    def get_font(self):
        return self.font

class FontGeneratorDialog(QDialog):
    """最终版字体贴图生成器对话框"""
    def __init__(self, parent=None, initial_chars="", initial_version="IV"):
        super().__init__(parent)
        self.setWindowTitle("GTA 字体贴图生成器")
        self.setMinimumSize(640, 800)
        self.gxt_editor = parent
        self.generator = FontTextureGenerator()
        self.characters = initial_chars  # 存储字符数据

        layout = QVBoxLayout(self)
        
        # --- 顶部设置 ---
        top_grid = QHBoxLayout()
        ver_layout = QVBoxLayout()
        ver_layout.addWidget(QLabel("游戏版本:"))
        self.version_combo = QComboBox()
        self.version_combo.addItems(["GTA IV", "GTA San Andreas", "GTA Vice City", "GTA III"])
        self.version_combo.currentTextChanged.connect(self.update_ui_for_version)
        ver_layout.addWidget(self.version_combo)
        top_grid.addLayout(ver_layout)
        res_layout = QVBoxLayout()
        res_layout.addWidget(QLabel("分辨率:"))
        self.res_combo = QComboBox()
        self.res_combo.addItems(["4096x4096", "2048x2048"])
        res_layout.addWidget(self.res_combo)
        top_grid.addLayout(res_layout)
        layout.addLayout(top_grid)

        # --- 字体选择区 ---
        self.font_normal_widget = FontSelectionWidget("字体贴图 Normal", QFont("Microsoft YaHei", 42, QFont.Weight.Bold))
        layout.addWidget(self.font_normal_widget)
        
        self.font_slant_widget = FontSelectionWidget("字体贴图 Slant", QFont("Microsoft YaHei", 42, QFont.Weight.Bold))
        layout.addWidget(self.font_slant_widget)
        
        # --- 字符操作区 ---
        char_layout = QVBoxLayout()
        char_layout.addWidget(QLabel("字符操作:"))
        
        # 字符按钮布局
        char_btn_layout = QHBoxLayout()
        self.btn_load_from_gxt = QPushButton("从当前GXT加载特殊字符")
        self.btn_load_from_gxt.clicked.connect(self.load_chars_from_parent)
        self.btn_import_chars = QPushButton("导入字符文件")
        self.btn_import_chars.clicked.connect(self.import_char_file)
        self.btn_input_chars = QPushButton("输入字符生成")
        self.btn_input_chars.clicked.connect(self.input_chars_manually)
        char_btn_layout.addWidget(self.btn_load_from_gxt)
        char_btn_layout.addWidget(self.btn_import_chars)
        char_btn_layout.addWidget(self.btn_input_chars)
        char_layout.addLayout(char_btn_layout)
        
        # 字符信息显示
        self.char_info_layout = QHBoxLayout()
        self.char_count_label = QLabel("字符数: 0")
        self.char_info_layout.addWidget(self.char_count_label)
        self.btn_show_chars = QPushButton("查看字符")
        self.btn_show_chars.clicked.connect(self.show_chars_list)
        self.char_info_layout.addWidget(self.btn_show_chars)
        char_layout.addLayout(self.char_info_layout)
        
        layout.addLayout(char_layout)
        
        # 更新字符数显示
        self.update_char_count()

        # --- 预览区 ---
        self.preview_button = QPushButton("刷新预览")
        self.preview_button.clicked.connect(self.update_previews)
        layout.addWidget(self.preview_button)
        self.preview_area = QHBoxLayout()
        
        # 创建预览标签容器
        self.preview_normal_container = self.create_preview_container("常规 (Normal) 预览")
        self.preview_slant_container = self.create_preview_container("斜体 (Slant) 预览")
        
        self.preview_area.addWidget(self.preview_normal_container)
        self.preview_area.addWidget(self.preview_slant_container)
        layout.addLayout(self.preview_area)

        # --- 底部按钮 ---
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("生成文件")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        # 设置初始版本
        ver_map = {"IV": "GTA IV", "VC": "GTA Vice City", "SA": "GTA San Andreas", "III": "GTA III"}
        if initial_version in ver_map:
            self.version_combo.setCurrentText(ver_map[initial_version])
            
        self.update_ui_for_version()

    def create_preview_container(self, title):
        """创建预览容器"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(QLabel(f"<b>{title}</b>"), 0, Qt.AlignmentFlag.AlignCenter)
        
        # 创建标签
        label = ClickableLabel("点击'刷新预览'以生成")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedSize(280, 280)
        label.setStyleSheet("border: 1px solid #555; background-color: #2a2a2a;")
        label.clicked.connect(lambda: self.show_full_preview(label))
        
        # 保存标签引用
        if "Normal" in title:
            self.preview_normal_label = label
        else:
            self.preview_slant_label = label
            
        layout.addWidget(label)
        return container

    def show_full_preview(self, label):
        if label.pixmap_cache and not label.pixmap_cache.isNull():
            viewer = ImageViewer(label.pixmap_cache, label.parent().findChild(QLabel).text(), self)
            viewer.exec()

    def update_ui_for_version(self):
        is_vc_or_iii = self.get_settings()["version"] in ["VC", "III"]
        self.font_slant_widget.setVisible(is_vc_or_iii)
        self.preview_slant_container.setVisible(is_vc_or_iii)

    def update_previews(self):
        settings = self.get_settings()
        if not settings["characters"]:
            QMessageBox.warning(self, "提示", "字符不能为空，无法预览。")
            return
        
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            # 获取标签引用
            normal_label = self.preview_normal_label
            slant_label = self.preview_slant_label
            
            pixmap_normal = self.generator.create_pixmap(settings["characters"], settings["version"], settings["resolution"], settings["font_normal"])
            if normal_label:
                self.display_pixmap(normal_label, pixmap_normal)
            
            if self.font_slant_widget.isVisible() and slant_label:
                pixmap_slant = self.generator.create_pixmap(settings["characters"], settings["version"], settings["resolution"], settings["font_slant"])
                self.display_pixmap(slant_label, pixmap_slant)
        finally:
            QApplication.restoreOverrideCursor()
            
    def display_pixmap(self, label, pixmap):
        if not pixmap.isNull():
            label.pixmap_cache = pixmap
            label.setPixmap(pixmap.scaled(label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            label.pixmap_cache = None
            label.setText("生成失败")

    def load_chars_from_parent(self):
        if self.gxt_editor and hasattr(self.gxt_editor, 'collect_and_filter_chars'):
            chars = self.gxt_editor.collect_and_filter_chars()
            if chars:
                self.characters = chars
                self.update_char_count()
                QMessageBox.information(self, "成功", f"已从当前GXT加载 {len(chars)} 个特殊字符。")
            else:
                QMessageBox.warning(self, "提示", "当前GXT中未找到符合条件的特殊字符。")

    def import_char_file(self):
        """导入字符文件"""
        path, _ = QFileDialog.getOpenFileName(self, "导入字符文件", "", "文本文件 (*.txt);;所有文件 (*.*)")
        if not path: return
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 移除换行和空格
                chars = content.replace("\n", "").replace(" ", "")
                # 去重
                unique_chars = "".join(dict.fromkeys(chars))
                self.characters = unique_chars
                self.update_char_count()
                QMessageBox.information(self, "导入成功", f"已导入 {len(unique_chars)} 个字符")
        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"无法读取文件: {str(e)}")

    def input_chars_manually(self):
        """手动输入字符"""
        text, ok = QInputDialog.getMultiLineText(
            self, 
            "输入字符", 
            "请输入需要生成的字符 (可粘贴):", 
            self.characters
        )
        if ok and text:
            # 移除换行和空格
            chars = text.replace("\n", "").replace(" ", "")
            # 去重
            unique_chars = "".join(dict.fromkeys(chars))
            self.characters = unique_chars
            self.update_char_count()
            QMessageBox.information(self, "成功", f"已设置 {len(unique_chars)} 个字符")

    def show_chars_list(self):
        """显示字符列表对话框"""
        if not self.characters:
            QMessageBox.information(self, "字符列表", "当前没有字符")
            return
            
        dlg = QDialog(self)
        dlg.setWindowTitle("字符列表")
        dlg.resize(400, 300)
        
        layout = QVBoxLayout(dlg)
        
        # 字符列表显示 - 设置自动换行
        text_edit = QTextEdit()
        text_edit.setPlainText(self.characters)
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Consolas", 12))
        text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)  # 自动换行
        layout.addWidget(text_edit)
        
        # 字符统计信息
        char_count = len(self.characters)
        unique_count = len(set(self.characters))
        info_label = QLabel(f"字符总数: {char_count} | 唯一字符数: {unique_count}")
        layout.addWidget(info_label)
        
        # 关闭按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)
        
        dlg.exec()

    def update_char_count(self):
        """更新字符数量显示"""
        char_count = len(self.characters)
        unique_count = len(set(self.characters))
        self.char_count_label.setText(f"字符总数: {char_count} | 唯一字符数: {unique_count}")

    def get_settings(self):
        ver_map = {"GTA IV": "IV", "GTA San Andreas": "SA", "GTA Vice City": "VC", "GTA III": "III"}
        version = ver_map.get(self.version_combo.currentText())
        resolution = int(self.res_combo.currentText().split('x')[0])
        
        settings = {
            "version": version,
            "resolution": resolution,
            "characters": self.characters,
            "font_normal": self.font_normal_widget.get_font(),
        }
        if self.font_slant_widget.isVisible():
            settings["font_slant"] = self.font_slant_widget.get_font()
        return settings

class EditKeyDialog(QDialog):
    """编辑/新增 键值对对话框"""
    def __init__(self, parent=None, title="编辑键值对", key="", value=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)

        self.key_edit = QLineEdit(self)
        self.key_edit.setText(key)
        self.key_edit.setPlaceholderText("键名 (Key)")
        layout.addWidget(QLabel("键名 (Key):"))
        layout.addWidget(self.key_edit)

        self.value_edit = QTextEdit(self)
        self.value_edit.setPlainText(value)
        layout.addWidget(QLabel("值 (Value):"))
        layout.addWidget(self.value_edit, 1)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, parent=self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def get_data(self):
        return self.key_edit.text().strip(), self.value_edit.toPlainText().rstrip("\n")

class BatchEditDialog(QDialog):
    """批量编辑键值对对话框"""
    def __init__(self, parent=None, keys_values=None):
        super().__init__(parent)
        self.setWindowTitle("批量编辑键值对")
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)
        
        info_label = QLabel("每行一对，格式为 key=value。修改后点击保存。")
        layout.addWidget(info_label)
        
        self.text_edit = QTextEdit()
        self.text_edit.setAcceptRichText(False)
        self.text_edit.setFont(QFont("Consolas", 10))
        
        if keys_values:
            text_content = [f"{key}={value}\n" for key, value in keys_values]
            self.text_edit.setPlainText("".join(text_content))
        
        layout.addWidget(self.text_edit, 1)
        
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, 
            Qt.Orientation.Horizontal, 
            self
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def get_data(self):
        lines = self.text_edit.toPlainText().splitlines()
        pairs = []
        for line in lines:
            s = line.strip()
            if "=" in s:
                k, v = s.split("=", 1)
                if k.strip():
                    pairs.append((k.strip(), v.strip()))
        return pairs


class AddKeysDialog(QDialog):
    """新增键值对：支持 单个/批量"""
    def __init__(self, parent=None, table_name=""):
        super().__init__(parent)
        self.setWindowTitle(f"向表 '{table_name}' 添加键值对")
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)

        mode_layout = QHBoxLayout()
        self.btn_single = QPushButton("单个添加")
        self.btn_batch = QPushButton("批量添加 (key=value)")
        mode_layout.addWidget(self.btn_single)
        mode_layout.addWidget(self.btn_batch)
        layout.addLayout(mode_layout)

        self.single_key = QLineEdit()
        self.single_val = QLineEdit()
        self.single_key.setPlaceholderText("键名 (Key)")
        self.single_val.setPlaceholderText("值 (Value)")

        self.single_wrap = QWidget()
        single_v = QVBoxLayout(self.single_wrap)
        single_v.addWidget(QLabel("键名 (Key):"))
        single_v.addWidget(self.single_key)
        single_v.addWidget(QLabel("值 (Value):"))
        single_v.addWidget(self.single_val)
        self.single_wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.batch_wrap = QWidget()
        batch_v = QVBoxLayout(self.batch_wrap)
        self.batch_text = QTextEdit()
        self.batch_text.setPlaceholderText("每行一对，格式：key=value\n多个键值对之间可以用空行分隔")
        batch_v.addWidget(QLabel("每行一对，格式：key=value"))
        batch_v.addWidget(self.batch_text)
        self.batch_wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout.addWidget(self.single_wrap)
        layout.addWidget(self.batch_wrap)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self)
        layout.addWidget(self.buttons)

        self.btn_single.clicked.connect(self._enable_single)
        self.btn_batch.clicked.connect(self._enable_batch)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        self._enable_single()

    def _enable_single(self):
        self.single_wrap.setVisible(True)
        self.batch_wrap.setVisible(False)
        self.single_key.setFocus()
        self.adjustSize()

    def _enable_batch(self):
        self.single_wrap.setVisible(False)
        self.batch_wrap.setVisible(True)
        self.batch_text.setFocus()
        self.adjectSize()

    def get_single(self):
        return self.single_key.text().strip(), self.single_val.text().strip()

    def get_batch(self):
        lines = self.batch_text.toPlainText().splitlines()
        pairs = []
        for line in lines:
            s = line.strip()
            if "=" in s:
                k, v = s.split("=", 1)
                if k.strip():
                    pairs.append((k.strip(), v.strip()))
        return pairs


class VersionDialog(QDialog):
    """选择 TXT 文件对应的游戏版本。"""
    def __init__(self, parent=None, default="IV"):
        super().__init__(parent)
        self.setWindowTitle("选择版本")
        layout = QVBoxLayout(self)
        self.versions = [("GTA IV", "IV"), ("GTA Vice City", "VC"), ("GTA San Andreas", "SA"), ("GTA III (LC)", "III")]
        self.inputs = []
        for text, val in self.versions:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, b=btn: self._select(b))
            layout.addWidget(btn)
            self.inputs.append((btn, val))

        for b, val in self.inputs:
            if val == default:
                b.setChecked(True)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _select(self, clicked_btn):
        for b, _ in self.inputs:
            b.setChecked(b is clicked_btn)

    def get_value(self):
        for b, v in self.inputs:
            if b.isChecked():
                return v
        return "IV"

# ========== 主窗口 ==========
class GXTEditorApp(QMainWindow):
    def __init__(self, file_to_open=None):
        super().__init__()
        self.setWindowTitle(" GTA文本对话表编辑器 v2.0 作者：倾城剑舞")
        self.resize(1240, 760)
        self.setAcceptDrops(True)
        
        # 添加图标设置
        import sys
        from pathlib import Path
        # 获取脚本所在目录
        if getattr(sys, 'frozen', False):
            # 打包后环境
            base_dir = Path(sys._MEIPASS)
        else:
            # 开发环境
            base_dir = Path(__file__).parent
        icon_path = base_dir / "app_icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
             
        self.file_to_open = file_to_open

        # --- 状态数据 ---
        self.data = {}
        self.version = None
        self.filepath = None
        self.current_table = None
        self.value_display_limit = 60
        self.version_filename_map = {'IV': 'GTA4.txt', 'VC': 'GTAVC.txt', 'SA': 'GTASA.txt', 'III': 'GTA3.txt'}
        self.remember_gen_extra_choice = None

        # --- UI ---
        self._apply_neutral_dark_theme()
        self._setup_menu()
        self._setup_statusbar()
        self._setup_body()
        
        if self.file_to_open:
            QTimer.singleShot(300, lambda: self.open_gxt(path=self.file_to_open))

    # ====== 主题 ======
    def _apply_neutral_dark_theme(self):
        """应用中性深色主题"""
        app = QApplication.instance()
        palette = QPalette()
        
        # 基础颜色设置
        dark_bg = QColor(30, 30, 34)
        darker_bg = QColor(25, 25, 28)
        text_color = QColor(220, 220, 220)
        highlight = QColor(0, 122, 204)
        button_bg = QColor(45, 45, 50)
        border_color = QColor(60, 60, 65)
        
        palette.setColor(QPalette.ColorRole.Window, dark_bg)
        palette.setColor(QPalette.ColorRole.WindowText, text_color)
        palette.setColor(QPalette.ColorRole.Base, darker_bg)
        palette.setColor(QPalette.ColorRole.AlternateBase, dark_bg)
        palette.setColor(QPalette.ColorRole.ToolTipBase, dark_bg)
        palette.setColor(QPalette.ColorRole.ToolTipText, text_color)
        palette.setColor(QPalette.ColorRole.Text, text_color)
        palette.setColor(QPalette.ColorRole.Button, button_bg)
        palette.setColor(QPalette.ColorRole.ButtonText, text_color)
        palette.setColor(QPalette.ColorRole.Highlight, highlight)
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, highlight)
        
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor(150, 150, 150))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(150, 150, 150))
        
        app.setPalette(palette)
        app.setStyle("Fusion")
        
        app.setStyleSheet(f"""
            QWidget {{
                font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
                font-size: 10pt;
            }}
            QMainWindow {{
                background-color: {dark_bg.name()};
            }}
            QMenuBar {{
                background-color: {darker_bg.name()};
                padding: 5px;
                border-bottom: 1px solid {border_color.name()};
            }}
            QMenuBar::item {{
                background: transparent;
                padding: 5px 10px;
                color: {text_color.name()};
                border-radius: 4px;
            }}
            QMenuBar::item:selected {{
                background-color: {highlight.name()};
            }}
            QMenu {{
                background-color: {darker_bg.name()};
                border: 1px solid {border_color.name()};
                padding: 5px;
            }}
            QMenu::item {{
                padding: 5px 30px 5px 20px;
            }}
            QMenu::item:selected {{
                background-color: {highlight.name()};
            }}
            QPushButton {{
                background-color: {button_bg.name()};
                color: {text_color.name()};
                border: 1px solid {border_color.name()};
                border-radius: 4px;
                padding: 5px 10px;
                min-height: 28px;
            }}
            QPushButton:hover {{
                background-color: #3a3a40;
                border-color: #7a7a7a;
            }}
            QPushButton:pressed {{
                background-color: #2a2a2e;
            }}

            /* ========== 新增样式：增强版本选择按钮的选中效果 ========== */
            QPushButton:checked {{
                background-color: {highlight.name()};
                border-color: {QColor(highlight).lighter(120).name()};
            }}
            /* ======================================================= */

            QLineEdit, QTextEdit, QListWidget, QTableWidget, QComboBox {{
                background-color: {darker_bg.name()};
                color: {text_color.name()};
                border: 1px solid {border_color.name()};
                border-radius: 4px;
                padding: 5px;
                selection-background-color: {highlight.name()};
                selection-color: white;
            }}
            QLineEdit:focus, QTextEdit:focus, QListWidget:focus, QTableWidget:focus, QComboBox:focus {{
                border: 1px solid {highlight.name()};
            }}
            QDockWidget {{
                titlebar-close-icon: url(:/qss_icons/rc/close.png);
                titlebar-normal-icon: url(:/qss_icons/rc/undock.png);
                background: {dark_bg.name()};
                border: 1px solid {border_color.name()};
                titlebar-normal-icon: none;
            }}
            QDockWidget::title {{
                background: {darker_bg.name()};
                padding: 5px;
                text-align: center;
            }}
            QHeaderView::section {{
                background-color: {button_bg.name()};
                color: {text_color.name()};
                padding: 5px;
                border: 1px solid {border_color.name()};
            }}
            QTableWidget::item {{
                padding: 5px;
            }}
            QTableCornerButton::section {{
                background-color: {button_bg.name()};
                border: 1px solid {border_color.name()};
            }}
            QStatusBar {{
                background-color: {darker_bg.name()};
                border-top: 1px solid {border_color.name()};
                color: {text_color.name()};
            }}
            QScrollBar:vertical {{
                border: none;
                background: {darker_bg.name()};
                width: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {button_bg.name()};
                min-height: 20px;
                border-radius: 4px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                background: none;
            }}
        """)

    # ====== 菜单 ======
    def _setup_menu(self):
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)

        file_menu = QMenu("文件", self)
        menubar.addMenu(file_menu)
        file_menu.addAction(self._act("📂 打开GXT文件", self.open_gxt, "Ctrl+O"))
        file_menu.addAction(self._act("📄 打开TXT文件", self.open_txt))
        file_menu.addSeparator()
        file_menu.addAction(self._act("🆕 新建GXT文件", self.new_gxt))
        file_menu.addAction(self._act("💾 保存GXT文件", self.save_gxt, "Ctrl+S"))
        file_menu.addAction(self._act("💾 另存为...", self.save_gxt_as))
        file_menu.addSeparator()
        file_menu.addAction(self._act("➡ 导出为单个TXT", lambda: self.export_txt(single=True)))
        file_menu.addAction(self._act("➡ 导出为多个TXT", lambda: self.export_txt(single=False)))
        file_menu.addSeparator()
        file_menu.addAction(self._act("📎 设置.gxt文件关联", self.set_file_association))
        file_menu.addSeparator()
        file_menu.addAction(self._act("❌ 退出", self.close, "Ctrl+Q"))
        
        tools_menu = QMenu("工具", self)
        menubar.addMenu(tools_menu)
        tools_menu.addAction(self._act("🎨 GTA 字体贴图生成器", self.open_font_generator))

        help_menu = QMenu("帮助", self)
        menubar.addMenu(help_menu)
        help_menu.addAction(self._act("💡 关于", self.show_about))
        help_menu.addAction(self._act("❓ 使用帮助", self.show_help))
    
    def _setup_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.update_status("就绪。将 .gxt 或 .txt 文件拖入窗口可打开。")

    def _setup_body(self):
        self.tables_dock = QDockWidget("表列表", self)
        self.tables_dock.setMaximumWidth(200)  # 限制最大宽度
        self.tables_dock.setMinimumWidth(150)  # 设置最小宽度
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.tables_dock)
        
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(5, 5, 5, 5)
        
        # 搜索框
        self.table_search = QLineEdit()
        self.table_search.setPlaceholderText("🔍 搜索表名...")
        self.table_search.textChanged.connect(self.filter_tables)
        left_layout.addWidget(self.table_search)
        
        # 表列表
        self.table_list = QListWidget()
        self.table_list.itemSelectionChanged.connect(self.select_table)
        self.table_list.itemDoubleClicked.connect(self.rename_table)
        left_layout.addWidget(self.table_list, 1)  # 给列表更多空间
        
        # 按钮布局 - 使用紧凑布局
        btn_layout = QHBoxLayout()
        btn_add = QPushButton("➕")
        btn_add.setToolTip("添加表")
        btn_add.clicked.connect(self.add_table)
        
        btn_del = QPushButton("🗑️")
        btn_del.setToolTip("删除表")
        btn_del.clicked.connect(self.delete_table)
        
        btn_export = QPushButton("📤")
        btn_export.setToolTip("导出此表")
        btn_export.clicked.connect(self.export_current_table)
        
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_del)
        btn_layout.addWidget(btn_export)
        left_layout.addLayout(btn_layout)
        
        self.tables_dock.setWidget(left)
        
        # 中央区域
        central = QWidget()
        c_layout = QVBoxLayout(central)
        
        # 搜索框
        self.key_search = QLineEdit()
        self.key_search.setPlaceholderText("🔍 搜索键或值...")
        self.key_search.textChanged.connect(self.search_key_value)
        c_layout.addWidget(self.key_search)
        
        # 表格
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["序号", "键名 (Key)", "值 (Value)"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.doubleClicked.connect(self.on_table_double_click)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 50)  # 减小序号列宽度
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
        # 设置右键菜单
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        c_layout.addWidget(self.table)
        
        # 底部按钮栏 - 移动到表格下方
        key_btns = QHBoxLayout()
        key_btns.setContentsMargins(0, 5, 0, 0)  # 添加上边距
        btn_kadd = QPushButton("➕ 添加键")
        btn_clear = QPushButton("💥 清空此表")
        
        btn_kadd.clicked.connect(self.add_key)
        btn_clear.clicked.connect(self.clear_current_table)
        
        key_btns.addWidget(btn_kadd)
        key_btns.addWidget(btn_clear)
        key_btns.addStretch()  # 添加弹性空间使按钮左对齐
        c_layout.addLayout(key_btns)
        
        self.setCentralWidget(central)

    def show_context_menu(self, position):
        """显示右键菜单"""
        if not self.current_table:
            return
            
        menu = QMenu()
        
        # 获取选中的行
        selected_rows = self.table.selectionModel().selectedRows()
        
        # 只在选中单个行时显示编辑按钮
        if len(selected_rows) == 1:
            edit_action = QAction("✏️ 编辑", self)
            edit_action.triggered.connect(self.on_table_double_click)
            menu.addAction(edit_action)
        
        # 添加删除操作
        delete_action = QAction("🗑️ 删除", self)
        delete_action.triggered.connect(self.delete_key)
        menu.addAction(delete_action)
        
        # 添加复制操作
        copy_action = QAction("📋 复制", self)
        copy_action.triggered.connect(self.copy_selected)
        menu.addAction(copy_action)
        
        # 如果有多个选中项，添加批量编辑操作
        if len(selected_rows) > 1:
            batch_edit_action = QAction("✏️ 批量编辑", self)
            batch_edit_action.triggered.connect(self.batch_edit_selected)
            menu.addAction(batch_edit_action)
        
        # 显示菜单
        menu.exec(self.table.viewport().mapToGlobal(position))

    def _act(self, text, slot, shortcut=None):
        a = QAction(text, self)
        if shortcut: a.setShortcut(shortcut)
        a.triggered.connect(slot)
        return a

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls: return
        paths = [u.toLocalFile() for u in urls]
        gxt_files = [p for p in paths if p.lower().endswith(".gxt")]
        txt_files = [p for p in paths if p.lower().endswith(".txt")]
        if gxt_files: self.open_gxt(path=gxt_files[0])
        elif txt_files: self.open_txt(files=txt_files)
        else: self.update_status("错误：请拖拽 .gxt 或 .txt 文件。")

    def filter_tables(self):
        keyword = self.table_search.text().lower()
        self.table_list.clear()
        for name in sorted(self.data):
            if keyword in name.lower(): self.table_list.addItem(name)
        self.update_status(f"显示 {self.table_list.count()} 个表")

    def select_table(self):
        items = self.table_list.selectedItems()
        if not items: return
        self.current_table = items[0].text()
        self.refresh_keys()
        self.update_status(f"查看表: {self.current_table}，共 {len(self.data.get(self.current_table, {}))} 个键值对")

    def refresh_keys(self):
        self.table.setRowCount(0)
        if self.current_table and self.current_table in self.data:
            for idx, (k, v) in enumerate(sorted(self.data[self.current_table].items()), 1):
                display_value = v if len(v) <= self.value_display_limit else v[:self.value_display_limit] + "..."
                self._insert_row(idx, k, display_value, v)

    def _insert_row(self, idx, key, display_value, full_value):
        row = self.table.rowCount()
        self.table.insertRow(row)
        idx_item = QTableWidgetItem(str(idx))
        idx_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 0, idx_item)
        self.table.setItem(row, 1, QTableWidgetItem(key))
        value_item = QTableWidgetItem(display_value)
        value_item.setData(Qt.ItemDataRole.UserRole, full_value)
        self.table.setItem(row, 2, value_item)

    def search_key_value(self):
        keyword = self.key_search.text().lower()
        self.table.setRowCount(0)
        count = 0
        if self.current_table and self.current_table in self.data:
            current_index = 1
            for k, v in sorted(self.data[self.current_table].items()):
                if keyword in k.lower() or keyword in str(v).lower():
                    display_value = v if len(v) <= self.value_display_limit else v[:self.value_display_limit] + "..."
                    self._insert_row(current_index, k, display_value, v)
                    current_index += 1
            count = current_index - 1
        self.update_status(f"搜索结果: {count} 个匹配项")

    def add_table(self):
        if not hasattr(self, 'version') or self.version is None:
            QMessageBox.information(self, "提示", "请先新建或打开一个GXT文件。")
            return
            
        name, ok = QInputDialog.getText(self, "新建表", "请输入表名：")
        if ok and name.strip():
            name = name.strip()
            if name in self.data:
                QMessageBox.warning(self, "错误", f"表 '{name}' 已存在！")
                return
            self.data[name] = {}
            self.table_search.clear()
            self.filter_tables()
            items = self.table_list.findItems(name, Qt.MatchFlag.MatchExactly)
            if items: self.table_list.setCurrentItem(items[0])
            self.update_status(f"已添加新表: {name}")

    def delete_table(self):
        if not self.current_table: return
        if QMessageBox.question(self, "确认", f"是否删除表 '{self.current_table}'？\n此操作不可恢复！") == QMessageBox.StandardButton.Yes:
            old = self.current_table
            del self.data[self.current_table]
            self.current_table = None
            self.refresh_keys()
            self.filter_tables()
            self.update_status(f"已删除表: {old}")

    def rename_table(self, _item):
        if not self.current_table: return
        old = self.current_table
        new, ok = QInputDialog.getText(self, "重命名表", "请输入新名称：", text=old)
        if ok and new.strip():
            new = new.strip()
            if new in self.data and new != old:
                QMessageBox.warning(self, "错误", f"表 '{new}' 已存在！")
                return
            self.data[new] = self.data.pop(old)
            self.current_table = new
            self.filter_tables()
            items = self.table_list.findItems(new, Qt.MatchFlag.MatchExactly)
            if items: self.table_list.setCurrentItem(items[0])
            self.update_status(f"已将表 '{old}' 重命名为 '{new}'")

    def export_current_table(self):
        if not self.current_table or not self.data.get(self.current_table):
            QMessageBox.information(self, "提示", "没有数据可导出")
            return
        default_filename = f"{self.current_table}.txt"
        filepath, _ = QFileDialog.getSaveFileName(self, "导出当前表为TXT", default_filename, "文本文件 (*.txt)")
        if not filepath: return
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                if self.version != 'III': f.write(f"[{self.current_table}]\n")
                for k, v in sorted(self.data[self.current_table].items()): f.write(f"{k}={v}\n")
            QMessageBox.information(self, "导出成功", f"表 '{self.current_table}' 已导出到:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")

    def on_table_double_click(self):
        if not self.current_table: return
        row = self.table.currentRow()
        if row < 0: return
        key = self.table.item(row, 1).text()
        original_value = self.data[self.current_table].get(key, "")
        dlg = EditKeyDialog(self, title=f"编辑: {key}", key=key, value=original_value)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_key, new_val = dlg.get_data()
            if not new_key:
                QMessageBox.critical(self, "错误", "键名不能为空！")
                return
            if new_key != key and new_key in self.data[self.current_table]:
                QMessageBox.critical(self, "错误", f"键名 '{new_key}' 已存在！")
                return
            if new_key != key:
                if key in self.data[self.current_table]: del self.data[self.current_table][key]
            self.data[self.current_table][new_key] = new_val
            self.refresh_keys()
            self.update_status(f"已更新键: {new_key}")

    def batch_edit_selected(self):
        if not self.current_table: return
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "提示", "请先选择要编辑的键值对")
            return
        keys_values = []
        for index in selected_rows:
            key = self.table.item(index.row(), 1).text()
            full_value = self.data[self.current_table].get(key, "")
            keys_values.append((key, full_value))
        if not keys_values: return
        dialog = BatchEditDialog(self, keys_values)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_pairs = dialog.get_data()
            if len(new_pairs) != len(keys_values):
                QMessageBox.critical(self, "错误", "编辑后键值对数量发生变化，请确保数量一致！")
                return
            new_keys = [p[0] for p in new_pairs]
            if len(new_keys) != len(set(new_keys)):
                QMessageBox.critical(self, "错误", "编辑后的键名有重复！")
                return
            existing_keys = set(self.data[self.current_table].keys()) - set(kv[0] for kv in keys_values)
            for new_key in new_keys:
                if new_key in existing_keys:
                    QMessageBox.critical(self, "错误", f"键 '{new_key}' 在表中已存在！")
                    return
            for key, _ in keys_values:
                if key in self.data[self.current_table]: del self.data[self.current_table][key]
            for new_key, new_value in new_pairs:
                self.data[self.current_table][new_key] = new_value
            self.refresh_keys()
            self.update_status(f"已批量更新 {len(new_pairs)} 个键值对")

    def add_key(self):
        if not self.current_table: 
            QMessageBox.information(self, "提示", "请先选择一个表")
            return
            
        dlg = AddKeysDialog(self, table_name=self.current_table)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            added, overwrite = 0, 0
            pairs = dlg.get_batch() if dlg.batch_wrap.isVisible() else [dlg.get_single()]
            for k, v in pairs:
                if not k: continue
                if k in self.data[self.current_table]: overwrite += 1
                else: added += 1
                self.data[self.current_table][k] = v
            self.refresh_keys()
            self.update_status(f"添加: {added}, 覆盖: {overwrite}")

    def delete_key(self):
        if not self.current_table: return
        rows = self.table.selectionModel().selectedRows()
        if not rows: return
        if QMessageBox.question(self, "确认", f"是否删除选中的 {len(rows)} 个键值对？") == QMessageBox.StandardButton.Yes:
            keys = [self.table.item(idx.row(), 1).text() for idx in rows]
            for k in keys: self.data[self.current_table].pop(k, None)
            self.refresh_keys()
            self.update_status(f"已删除 {len(keys)} 个键值对")

    def clear_current_table(self):
        if not self.current_table: return
        if QMessageBox.question(self, "确认", f"是否清空表 '{self.current_table}' 中的所有键值对？\n此操作不可恢复！") == QMessageBox.StandardButton.Yes:
            self.data[self.current_table].clear()
            self.refresh_keys()
            self.update_status(f"已清空表 {self.current_table}")

    def copy_selected(self):
        if not self.current_table: return
        rows = self.table.selectionModel().selectedRows()
        if not rows: return
        pairs = []
        for idx in rows:
            k = self.table.item(idx.row(), 1).text()
            v = self.data[self.current_table].get(k, "")
            pairs.append(f"{k}={v}")
        if pairs:
            QGuiApplication.clipboard().setText("\n".join(pairs))
            self.update_status(f"已复制 {len(pairs)} 个键值对到剪贴板")

    def new_gxt(self):
        dlg = VersionDialog(self, default="IV")
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        self.data.clear()
        self.version = dlg.get_value()
        self.filepath = None
        self.current_table = None
        if self.version == 'III': self.data["MAIN"] = {}
        self.table_search.clear()
        self.filter_tables()
        if self.table_list.count() > 0: self.table_list.setCurrentRow(0)
        self.update_status(f"已创建新GXT文件 (版本: {self.version})")

    def open_gxt(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "打开GXT文件", "", "GXT文件 (*.gxt);;所有文件 (*.*)")
        if not path: return
        try:
            with open(path, "rb") as f:
                version = getVersion(f)
                reader = getReader(version)
                f.seek(0)
                self.data.clear()
                if reader.hasTables():
                    for name, offset in reader.parseTables(f):
                        f.seek(offset)
                        self.data[name] = dict(reader.parseTKeyTDat(f))
                else:
                    self.data["MAIN"] = dict(reader.parseTKeyTDat(f))
                self.version = version
                self.filepath = path
                self.table_search.clear()
                self.filter_tables()
                if self.table_list.count() > 0: self.table_list.setCurrentRow(0)
                self.update_status(f"已打开GXT文件: {os.path.basename(path)}, 版本: {version}")
                # 显示成功消息框
                QMessageBox.information(self, "成功", f"已成功打开GXT文件\n版本: {version}\n表数量: {len(self.data)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开文件失败: {str(e)}")

    def open_txt(self, files=None):
        dlg = VersionDialog(self, default="IV")
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        version = dlg.get_value()
        if not files:
            files, _ = QFileDialog.getOpenFileNames(self, "打开TXT文件", "", "文本文件 (*.txt);;所有文件 (*.*)")
        if not files: return
        try:
            self.data.clear()
            if version == 'IV':
                merged_data = {}
                for file_path in files:
                    txt_data, _ = load_iv_txt(Path(file_path))
                    for table_name, entries in txt_data.items():
                        if table_name not in merged_data: merged_data[table_name] = {}
                        for entry in entries: merged_data[table_name][entry['hash_string']] = entry['translated']
                self.data = merged_data
            else:
                reader = getReader(version)
                self.data = self._load_standard_txt(files, has_tables=reader.hasTables())
            self.version = version
            self.filepath = None
            self.table_search.clear()
            self.filter_tables()
            if self.table_list.count() > 0: self.table_list.setCurrentRow(0)
            self.update_status(f"已打开 {len(files)} 个TXT文件 (版本: {version})")
            # 显示成功消息框
            QMessageBox.information(self, "成功", f"已成功打开{len(files)}个TXT文件\n版本: {version}\n表数量: {len(self.data)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开文件失败: {str(e)}")

    def save_gxt(self):
        if not self.version: 
            QMessageBox.warning(self, "警告", "请先打开或新建一个GXT文件")
            return
        if self.filepath: self._save_to_path(self.filepath)
        else: self.save_gxt_as()

    def save_gxt_as(self):
        if not self.version: 
            QMessageBox.warning(self, "警告", "请先打开或新建一个GXT文件")
            return
        default_name = os.path.basename(self.filepath) if self.filepath else "output.gxt"
        path, _ = QFileDialog.getSaveFileName(self, "保存GXT文件", default_name, "GXT文件 (*.gxt);;所有文件 (*.*)")
        if path:
            self._save_to_path(path)
            self.filepath = path

    def _save_to_path(self, path):
        gen_extra = False
        if self.remember_gen_extra_choice is None:
            msg_box = QMessageBox(self)
            msg_box.setText("是否生成字符映射辅助文件？")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            check_box = QCheckBox("记住我的选择")
            msg_box.setCheckBox(check_box)
            reply = msg_box.exec()
            if check_box.isChecked(): self.remember_gen_extra_choice = (reply == QMessageBox.StandardButton.Yes)
            gen_extra = (reply == QMessageBox.StandardButton.Yes)
        else:
            gen_extra = self.remember_gen_extra_choice

        original_dir = os.getcwd()
        try:
            os.chdir(os.path.dirname(path))
            if self.version == 'IV':
                m_Data = {}
                all_chars = set()
                for table_name, entries_dict in self.data.items():
                    m_Data[table_name] = []
                    for key_str, translated_text in entries_dict.items():
                        hash_str = f'0x{gta4_gxt_hash(key_str):08X}' if not key_str.lower().startswith('0x') else key_str
                        m_Data[table_name].append({'hash_string': hash_str, 'original': '', 'translated': translated_text})
                        if gen_extra: all_chars.update(c for c in translated_text if ord(c) > 255)
                write_iv(m_Data, Path(os.path.basename(path)))
                if gen_extra: process_special_chars(all_chars)
            else:
                all_chars = {char for table in self.data.values() for value in table.values() for char in value}
                if self.version == 'VC':
                    g = VCGXT()
                    g.m_GxtData = {t: {k: g._utf8_to_utf16(v) for k, v in d.items()} for t, d in self.data.items()}
                    if gen_extra: g.m_WideCharCollection = {ord(c) for c in all_chars if ord(c) > 0x7F}; g.GenerateWMHHZStuff()
                    g.SaveAsGXT(os.path.basename(path))
                elif self.version == 'SA':
                    g = SAGXT()
                    g.m_GxtData = {t: {int(k, 16): v for k, v in d.items()} for t, d in self.data.items()}
                    if gen_extra: g.m_WideCharCollection = {c for c in all_chars if ord(c) > 0x7F}; g.generate_wmhhz_stuff()
                    g.save_as_gxt(os.path.basename(path))
                elif self.version == 'III':
                    g = LCGXT()
                    g.m_GxtData = {k: g.utf8_to_utf16(v) for k, v in self.data.get('MAIN', {}).items()}
                    if gen_extra: g.m_WideCharCollection = {ord(c) for c in all_chars if ord(c) >= 0x80}; g.generate_wmhhz_stuff()
                    g.save_as_gxt(os.path.basename(path))
            QMessageBox.information(self, "成功", f"GXT 已保存到 {path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存文件失败: {str(e)}")
        finally:
            os.chdir(original_dir)

    def export_txt(self, single=True):
        if not self.data: 
            QMessageBox.warning(self, "警告", "没有数据可导出")
            return
        try:
            if single:
                default_filename = self.version_filename_map.get(self.version, "merged.txt")
                filepath, _ = QFileDialog.getSaveFileName(self, "导出为单个TXT文件", default_filename, "文本文件 (*.txt)")
                if not filepath: return
                with open(filepath, 'w', encoding='utf-8') as f:
                    for i, (t, d) in enumerate(sorted(self.data.items())):
                        if i > 0: f.write("\n\n")
                        if self.version != 'III': f.write(f"[{t}]\n")
                        for k, v in sorted(d.items()): f.write(f"{k}={v}\n")
                QMessageBox.information(self, "导出成功", f"已导出到: {filepath}")
            else:
                if self.version == 'III':
                    QMessageBox.warning(self, "提示", "GTA III GXT 文件不支持导出为多个TXT。")
                    return
                default_dirname = {'IV': 'GTA4_txt', 'VC': 'GTAVC_txt', 'SA': 'GTASA_txt'}.get(self.version, "gxt_export")
                base_name, ok = QInputDialog.getText(self, "导出多个TXT", "请输入导出目录名称：", text=default_dirname)
                if not ok or not base_name.strip(): return
                export_dir = os.path.join(os.path.dirname(self.filepath) if self.filepath else os.getcwd(), base_name.strip())
                if os.path.exists(export_dir):
                    if QMessageBox.question(self, "确认", f"目录 '{export_dir}' 已存在，是否覆盖？") != QMessageBox.StandardButton.Yes: return
                    shutil.rmtree(export_dir)
                os.makedirs(export_dir)
                for t, d in sorted(self.data.items()):
                    with open(os.path.join(export_dir, f"{t}.txt"), 'w', encoding='utf-8') as f:
                        f.write(f"[{t}]\n")
                        for k, v in sorted(d.items()): f.write(f"{k}={v}\n")
                QMessageBox.information(self, "导出成功", f"已导出 {len(self.data)} 个文件到:\n{export_dir}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")

    def _load_standard_txt(self, files, has_tables):
        data = {}
        current_table = "MAIN" if not has_tables else None
        if not has_tables: data["MAIN"] = {}
        for file_path in files:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    if has_tables and line.startswith('[') and line.endswith(']'):
                        current_table = line[1:-1].strip()
                        if current_table and current_table not in data: data[current_table] = {}
                    elif '=' in line and current_table is not None:
                        key, value = line.split('=', 1)
                        if key.strip(): data[current_table][key.strip()] = value.strip()
        return data

    # ====== 辅助与工具 ======
    def collect_and_filter_chars(self):
        """根据指定逻辑收集和筛选GXT中的特殊字符"""
        if not self.data:
            return ""
        
        all_chars = {char for table in self.data.values() for value in table.values() for char in value}
        
        special_chars = set()
        for char in all_chars:
            if ord(char) > 255:
                special_chars.add(char)
        
        # 排除特定字符
        special_chars.discard(chr(0x2122))  # trademark
        special_chars.discard(chr(0x3000))  # ideographic space
        special_chars.discard(chr(0xFEFF))  # byte order mark
        
        return "".join(sorted(list(special_chars), key=lambda c: ord(c)))
        
    def open_font_generator(self):
        initial_chars = self.collect_and_filter_chars()
        # 获取当前GXT版本，如果没有则默认为"IV"
        current_version = self.version if self.version else "IV"
        dlg = FontGeneratorDialog(self, initial_chars, initial_version=current_version)
        
        if dlg.exec() != QDialog.DialogCode.Accepted: return
            
        settings = dlg.get_settings()
        if not settings["characters"]:
            QMessageBox.warning(self, "提示", "没有需要生成的字符，操作已取消。")
            return
            
        output_dir = QFileDialog.getExistingDirectory(self, "选择保存字体贴图的目录")
        if not output_dir: return
            
        try:
            self.update_status("正在生成字体贴图，请稍候...")
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

            generator = FontTextureGenerator()
            version = settings["version"]

            if version in ['III', 'VC']:
                # 生成 Normal
                path_normal = os.path.join(output_dir, 'normal.png')
                generator.generate_and_save(settings["characters"], path_normal, version, settings["resolution"], settings["font_normal"])
                # 生成 Slant
                path_slant = os.path.join(output_dir, 'slant.png')
                generator.generate_and_save(settings["characters"], path_slant, version, settings["resolution"], settings["font_slant"])
                # 生成 HTML
                html_path = os.path.join(output_dir, 'font_preview.html')
                generator.generate_html_preview(settings, path_normal, html_path)
                
                QMessageBox.information(self, "生成成功", f"已成功生成文件:\n- {path_normal}\n- {path_slant}\n- {html_path}")
            else:
                # 生成 Font
                path_font = os.path.join(output_dir, 'font.png')
                generator.generate_and_save(settings["characters"], path_font, version, settings["resolution"], settings["font_normal"])
                # 生成 HTML
                html_path = os.path.join(output_dir, 'font_preview.html')
                generator.generate_html_preview(settings, path_font, html_path)
                QMessageBox.information(self, "生成成功", f"已成功生成文件:\n- {path_font}\n- {html_path}")
            
            self.update_status(f"成功生成字体贴图到: {output_dir}")
        except Exception as e:
            QMessageBox.critical(self, "生成失败", f"生成字体贴图时发生错误: {e}")
            self.update_status(f"字体贴图生成失败: {e}")
        finally:
            QApplication.restoreOverrideCursor()

    def update_status(self, message):
        self.status.showMessage(message)

    def show_about(self):
        QMessageBox.information(self, "关于", 
            "倾城剑舞 GXT 编辑器 v2.0\n"
            "支持 IV/VC/SA/III 的 GXT/TXT 编辑、导入导出。\n"
            "新增功能：文件关联、新建GXT、批量编辑、导出单个表、生成png透明汉化字体贴图")

    def show_help(self):
        QMessageBox.information(self, "使用帮助", 
            "1. 打开文件：菜单或将 .gxt / .txt 拖入窗口，也可通过文件关联gxt文件打开。\n"
            "2. 新建文件：文件菜单→新建GXT文件，选择游戏版本。\n"
            "3. 编辑：双击右侧列表中的任意条目，弹出编辑窗口。\n"
            "4. 多选编辑：选择多行后点击'批量编辑'按钮。\n"
            "5. 添加/删除：使用左侧或按钮条中的按钮进行操作。\n"
            "6. 复制：选择多行后点击“复制选中 (key=value)”。\n"
            "7. 保存：支持生成字符映射辅助文件（可选），并可记住选择。\n"
            "8. 导出：支持导出整个GXT或单个表为TXT文件。\n"
            "9. TXT 导入：支持单个或多个TXT导入并直接生成GXT。\n"
            "10. GTA IV 特别说明：键名可为明文（如 T1_NAME_82）或哈希（0xhash），保存时自动转换哈希。\n"
            "11. 字体生成器：工具菜单→GTA字体贴图生成器，用于创建游戏字体PNG文件。支持为VC/III分别设置字体，加载外部字体文件，点击预览图可放大查看。【仅限：汉化字体贴图】")

    def set_file_association(self):
        if sys.platform != 'win32':
            QMessageBox.information(self, "提示", "文件关联功能目前仅支持Windows系统")
            return
        try:
            exe_path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"' if not getattr(sys, 'frozen', False) else sys.executable
            key_path = r"Software\Classes"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{key_path}\\.gxt") as key:
                winreg.SetValue(key, '', winreg.REG_SZ, 'GXTEditor.File')
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{key_path}\\GXTEditor.File") as key:
                winreg.SetValue(key, '', winreg.REG_SZ, 'GTA GXT File')
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{key_path}\\GXTEditor.File\\DefaultIcon") as key:
                winreg.SetValue(key, '', winreg.REG_SZ, f'"{exe_path}",0')
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{key_path}\\GXTEditor.File\\shell\\open\\command") as key:
                winreg.SetValue(key, '', winreg.REG_SZ, f'"{exe_path}" "%1"')
            
            import ctypes
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
            QMessageBox.information(self, "成功", "已设置.gxt文件关联! 可能需要重启资源管理器或电脑生效。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"设置文件关联失败: {str(e)}")


# ========== 入口 ==========
if __name__ == "__main__":
    import sys
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    
    file_to_open = sys.argv[1] if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) and sys.argv[1].lower().endswith('.gxt') else None

    editor = GXTEditorApp(file_to_open)
    editor.show()
    sys.exit(app.exec())
