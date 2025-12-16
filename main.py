import tkinter as tk
from tkinter import ttk
import ctypes
import sys

try:
    import win32con
    import win32gui
    import win32api
except ImportError:
    win32_support = False
else:
    win32_support = True

try:
    from pynput import mouse
except ImportError:
    mouse = None

class TransparentDotsWindow(tk.Toplevel):
    def __init__(self, speed=1.0, mode='static', dot_offset=0.10, dot_radius=12, dot_spacing=1.0):
        super().__init__()
        self.speed = speed
        self.mode = mode
        self.dot_offset = dot_offset  # относительный отступ от края
        self.dot_radius = dot_radius  # радиус точки (пиксели)
        self.dot_spacing = dot_spacing  # коэффициент расстояния между точками
        self.last_mouse_pos = None  # Сбросить положение мыши
        self.withdraw()  # Не показывать, пока не настроим
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.attributes('-transparentcolor', 'white')
        self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")

        # CANVAS только для точек
        self.canvas = tk.Canvas(self, bg='white', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.update_idletasks()

        self.screen_w = self.winfo_screenwidth()
        self.screen_h = self.winfo_screenheight()
        offset_x = int(self.screen_w * self.dot_offset)
        n = 4
        # dot_spacing=1.0 — базовое расстояние, меньше — плотнее, больше — дальше
        gutter = (self.screen_h * 0.8) / ((n-1) * self.dot_spacing)
        base_y = int(self.screen_h * 0.10)
        y_steps = [int(base_y + i * gutter) for i in range(n)]
        self.anchor_positions = [
            [offset_x, y] for y in y_steps
        ] + [
            [self.screen_w - offset_x, y] for y in y_steps
        ]  # итого 8
        self.dot_offsets = [[0, 0] for _ in range(8)]
        self.target_offsets = [[0, 0] for _ in range(8)]  # Целевые позиции для плавного движения

        self.canvas.delete('all')

        # В статичном режиме — рисуем точки сразу.
        if self.mode == 'static':
            self.dots = [
                self.canvas.create_oval(ax - self.dot_radius, ay - self.dot_radius, ax + self.dot_radius, ay + self.dot_radius, fill='', outline='')
                for ax, ay in self.anchor_positions
            ]
        else:
            self.dots = [
                self.canvas.create_oval(-100, -100, -99, -99, fill='', outline='')
                for _ in self.anchor_positions
            ]
        self._redraw_dots()

        self.after(100, self.make_click_through)
        self.deiconify()
        self.protocol('WM_DELETE_WINDOW', self._on_close)

        self.listener = None
        self._animation_running = False
        if self.mode != 'static' and mouse is not None:
            self.listener = mouse.Listener(on_move=self._on_mouse_move)
            self.listener.start()
            # Запускаем плавную анимацию движения
            self._animation_running = True
            self._animate_dots()

    def change_mode(self, mode, speed, dot_offset):
        old_listener = getattr(self, 'listener', None)
        if old_listener is not None:
            old_listener.stop()
            self.listener = None
        # Останавливаем анимацию
        self._animation_running = False
        self.mode = mode
        self.speed = speed
        self.dot_offset = dot_offset
        self.last_mouse_pos = None
        self.dot_offsets = [[0, 0] for _ in range(8)]
        self.target_offsets = [[0, 0] for _ in range(8)]
        offset_x = int(self.screen_w * self.dot_offset)
        y_steps = [int(self.screen_h * (i/5.0 + 1/10.0)) for i in range(4)]
        self.anchor_positions = [
            [offset_x, y] for y in y_steps
        ] + [
            [self.screen_w - offset_x, y] for y in y_steps
        ]
        self.canvas.delete('all')
        if self.mode == 'static':
            self.dots = [
                self.canvas.create_oval(ax - self.dot_radius, ay - self.dot_radius, ax + self.dot_radius, ay + self.dot_radius, fill='', outline='')
                for ax, ay in self.anchor_positions
            ]
        else:
            self.dots = [
                self.canvas.create_oval(-100, -100, -99, -99, fill='', outline='')
                for _ in self.anchor_positions
            ]
        self._redraw_dots()
        if self.mode != 'static' and mouse is not None:
            self.listener = mouse.Listener(on_move=self._on_mouse_move)
            self.listener.start()
            # Запускаем плавную анимацию движения
            self._animation_running = True
            self._animate_dots()

    def _redraw_dots(self):
        r = self.dot_radius
        color_order = ["black", "#e8e8e8", "black", "#e8e8e8"]
        for idx in range(8):
            ax, ay = self.anchor_positions[idx]
            ox, oy = self.dot_offsets[idx]
            x = ax + ox
            y = ay + oy
            color = color_order[idx % 4]
            if self.mode == 'static':
                self.canvas.coords(self.dots[idx], x - r, y - r, x + r, y + r)
                self.canvas.itemconfig(self.dots[idx], fill=color, outline='')
            else:
                if ox != 0 or oy != 0:
                    self.canvas.coords(self.dots[idx], x - r, y - r, x + r, y + r)
                    self.canvas.itemconfig(self.dots[idx], fill=color, outline='')
                # else:
                    # self.canvas.coords(self.dots[idx], -100, -100, -99, -99)
                    # self.canvas.itemconfig(self.dots[idx], fill='', outline='')

    def _on_mouse_move(self, x, y):
        if self.last_mouse_pos is not None:
            dx = (x - self.last_mouse_pos[0]) * self.speed
            dy = (y - self.last_mouse_pos[1]) * self.speed
            # В режиме reverse инвертируем направление движения
            if self.mode == 'reverse':
                dx = -dx
                dy = -dy
            # Обновляем целевые позиции вместо текущих для плавности
            for idx in range(8):
                self.target_offsets[idx][0] += dx
                self.target_offsets[idx][1] += dy
        self.last_mouse_pos = (x, y)
        # Запускаем возврат к исходной позиции, если еще не запущен
        if not getattr(self, '_returning', False):
            self._start_return_anim() 

    def make_click_through(self):
        if sys.platform != 'win32' or not win32_support:
            print('Click-through поддерживается только на Windows с pywin32.')
            return
        hwnd = self.winfo_id()
        styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        styles |= win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, styles)
        win32gui.SetLayeredWindowAttributes(hwnd, win32api.RGB(255, 255, 255), 0, win32con.LWA_COLORKEY)

    def _reset_return_anim(self):
        pass  # Не используется, задержки нет

    def _animate_dots(self):
        """Плавная анимация движения точек к целевым позициям"""
        if not getattr(self, '_animation_running', False):
            return
        
        changed = False
        # Коэффициент интерполяции для плавности (меньше = плавнее, но медленнее реакция)
        lerp_factor = 0.12
        
        for idx in range(8):
            for i in range(2):
                current = self.dot_offsets[idx][i]
                target = self.target_offsets[idx][i]
                # Плавная интерполяция к целевой позиции
                diff = target - current
                if abs(diff) > 0.05:
                    # Используем более плавную интерполяцию
                    self.dot_offsets[idx][i] += diff * lerp_factor
                    changed = True
                else:
                    self.dot_offsets[idx][i] = target
        
        self._redraw_dots()
        
        if self._animation_running:
            self.after(8, self._animate_dots)  # ~120 FPS для более плавной анимации

    def _start_return_anim(self):
        self._returning = True
        self._smooth_return_step()

    def _smooth_return_step(self):
        changed = False
        # Возвращаем целевые позиции к нулю более плавно
        for idx in range(8):
            for i in range(2):
                v = self.target_offsets[idx][i]
                # Плавное возвращение целевой позиции к anchor (ноль)
                if abs(v) > 0.1:
                    self.target_offsets[idx][i] -= v * 0.12
                    changed = True
                else:
                    self.target_offsets[idx][i] = 0
        if changed and self._returning:
            self._after_id = self.after(8, self._smooth_return_step)
        else:
            self._returning = False

    def _on_close(self):
        # Останавливаем анимацию
        self._animation_running = False
        if getattr(self, 'listener', None) is not None:
            self.listener.stop()
            self.listener = None
        self.destroy()
        self.update()  # Форсировать немедленное обновление после уничтожения

class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Dot Control Panel")
        # self.geometry("350x260")  # УБРАНО
        self.resizable(False, False)

        self.dot_static_var = tk.BooleanVar(value=True)
        self.dot_active_var = tk.BooleanVar(value=False)
        self.dot_active_reverse_var = tk.BooleanVar(value=False)
        self.dots_window = None

        self.cb_static = ttk.Checkbutton(self, text="Dot Static",
                                         variable=self.dot_static_var,
                                         command=self.set_static)
        self.cb_active = ttk.Checkbutton(self, text="Dot active",
                                         variable=self.dot_active_var,
                                         command=self.set_active)
        self.cb_active_reverse = ttk.Checkbutton(self, text="Dot active reverse",
                                                 variable=self.dot_active_reverse_var,
                                                 command=self.set_active_reverse)
        self.cb_static.grid(row=0, column=0, padx=20, pady=(18, 2), sticky="w")
        self.cb_active.grid(row=1, column=0, padx=20, pady=2, sticky="w")
        self.cb_active_reverse.grid(row=2, column=0, padx=20, pady=2, sticky="w")

        self.speed_label = ttk.Label(self, text="Speed:")
        self.speed_label.grid(row=3, column=0, padx=20, pady=(18,2), sticky="w")
        self.speed_var = tk.DoubleVar(value=1.0)
        self.speed_slider = ttk.Scale(self, from_=0.2, to=3.0, variable=self.speed_var, orient='horizontal', length=200)
        self.speed_slider.grid(row=4, column=0, padx=20, pady=2, sticky="we")

        # Dot offset slider
        self.offset_label = ttk.Label(self, text="Dot offset:")
        self.offset_label.grid(row=5, column=0, padx=20, pady=(18,2), sticky="w")
        self.offset_var = tk.DoubleVar(value=0.10)
        self.offset_slider = ttk.Scale(self, from_=0.02, to=0.40, variable=self.offset_var, orient='horizontal', length=200)
        self.offset_slider.grid(row=6, column=0, padx=20, pady=2, sticky="we")

        # Dot size slider
        self.radius_label = ttk.Label(self, text="Dot size:")
        self.radius_label.grid(row=7, column=0, padx=20, pady=(18,2), sticky="w")
        self.radius_var = tk.DoubleVar(value=12)
        self.radius_slider = ttk.Scale(self, from_=4, to=40, variable=self.radius_var, orient='horizontal', length=200)
        self.radius_slider.grid(row=8, column=0, padx=20, pady=2, sticky="we")

        # Dot spacing slider
        self.gap_label = ttk.Label(self, text="Dot spacing:")
        self.gap_label.grid(row=9, column=0, padx=20, pady=(18,2), sticky="w")
        self.gap_var = tk.DoubleVar(value=1.00)
        self.gap_slider = ttk.Scale(self, from_=0.3, to=3.0, variable=self.gap_var, orient='horizontal', length=200)
        self.gap_slider.grid(row=10, column=0, padx=20, pady=2, sticky="we")

        self.start_button = ttk.Button(self, text="Start", command=self.on_start)
        self.start_button.grid(row=11, column=0, padx=20, pady=(25,5), sticky="we")

    def set_static(self):
        self.dot_static_var.set(True)
        self.dot_active_var.set(False)
        self.dot_active_reverse_var.set(False)

    def set_active(self):
        self.dot_static_var.set(False)
        self.dot_active_var.set(True)
        self.dot_active_reverse_var.set(False)

    def set_active_reverse(self):
        self.dot_static_var.set(False)
        self.dot_active_var.set(False)
        self.dot_active_reverse_var.set(True)

    def on_start(self):
        if self.dots_window and self.dots_window.winfo_exists():
            self.dots_window._on_close()
            self.dots_window = None
        mode = 'static' if self.dot_static_var.get() else (
            'reverse' if self.dot_active_reverse_var.get() else 'active')
        speed = self.speed_var.get()
        dot_offset = self.offset_var.get()
        dot_radius = self.radius_var.get()
        dot_spacing = self.gap_var.get()
        self.dots_window = TransparentDotsWindow(speed=speed, mode=mode, dot_offset=dot_offset, dot_radius=dot_radius, dot_spacing=dot_spacing)

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()
