"""
MicroPython SSD1306 OLED driver
I2C interface for 128x64 displays
"""

from micropython import const
import framebuf


# Register definitions
SET_CONTRAST = const(0x81)
SET_ENTIRE_ON = const(0xA4)
SET_NORM_INV = const(0xA6)
SET_DISP = const(0xAE)
SET_MEM_ADDR = const(0x20)
SET_COL_ADDR = const(0x21)
SET_PAGE_ADDR = const(0x22)
SET_DISP_START_LINE = const(0x40)
SET_SEG_REMAP = const(0xA0)
SET_MUX_RATIO = const(0xA8)
SET_COM_OUT_DIR = const(0xC0)
SET_DISP_OFFSET = const(0xD3)
SET_COM_PIN_CFG = const(0xDA)
SET_DISP_CLK_DIV = const(0xD5)
SET_PRECHARGE = const(0xD9)
SET_VCOM_DESEL = const(0xDB)
SET_CHARGE_PUMP = const(0x8D)


class SSD1306:
    """Base class for SSD1306 displays."""

    def __init__(self, width, height, external_vcc):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = height // 8
        self.buffer = bytearray(self.pages * width)
        self.framebuf = framebuf.FrameBuffer(
            self.buffer, width, height, framebuf.MONO_VLSB
        )
        self.init_display()

    def init_display(self):
        """Initialize display."""
        for cmd in (
            SET_DISP | 0x00,  # Display off
            SET_MEM_ADDR, 0x00,  # Horizontal addressing mode
            SET_DISP_START_LINE | 0x00,
            SET_SEG_REMAP | 0x01,  # Column 127 mapped to SEG0
            SET_MUX_RATIO, self.height - 1,
            SET_COM_OUT_DIR | 0x08,  # Scan from COM[N-1] to COM0
            SET_DISP_OFFSET, 0x00,
            SET_COM_PIN_CFG, 0x02 if self.height == 32 else 0x12,
            SET_DISP_CLK_DIV, 0x80,
            SET_PRECHARGE, 0x22 if self.external_vcc else 0xF1,
            SET_VCOM_DESEL, 0x30,
            SET_CONTRAST, 0xFF,
            SET_ENTIRE_ON,
            SET_NORM_INV,
            SET_CHARGE_PUMP, 0x10 if self.external_vcc else 0x14,
            SET_DISP | 0x01,  # Display on
        ):
            self.write_cmd(cmd)
        self.fill(0)
        self.show()

    def poweroff(self):
        """Turn off display."""
        self.write_cmd(SET_DISP | 0x00)

    def poweron(self):
        """Turn on display."""
        self.write_cmd(SET_DISP | 0x01)

    def contrast(self, value):
        """Set contrast (0-255)."""
        self.write_cmd(SET_CONTRAST)
        self.write_cmd(value)

    def invert(self, invert):
        """Invert display."""
        self.write_cmd(SET_NORM_INV | (invert & 1))

    def show(self):
        """Update display with buffer contents."""
        self.write_cmd(SET_COL_ADDR)
        self.write_cmd(0)
        self.write_cmd(self.width - 1)
        self.write_cmd(SET_PAGE_ADDR)
        self.write_cmd(0)
        self.write_cmd(self.pages - 1)
        self.write_data(self.buffer)

    def fill(self, value):
        """Fill entire display."""
        self.framebuf.fill(value)

    def pixel(self, x, y, value):
        """Set pixel."""
        self.framebuf.pixel(x, y, value)

    def text(self, string, x, y, value=1):
        """Draw text."""
        self.framebuf.text(string, x, y, value)

    def rect(self, x, y, w, h, value):
        """Draw rectangle outline."""
        self.framebuf.rect(x, y, w, h, value)

    def fill_rect(self, x, y, w, h, value):
        """Draw filled rectangle."""
        self.framebuf.fill_rect(x, y, w, h, value)

    def hline(self, x, y, w, value):
        """Draw horizontal line."""
        self.framebuf.hline(x, y, w, value)

    def vline(self, x, y, h, value):
        """Draw vertical line."""
        self.framebuf.vline(x, y, h, value)

    def line(self, x1, y1, x2, y2, value):
        """Draw line."""
        self.framebuf.line(x1, y1, x2, y2, value)

    def scroll(self, dx, dy):
        """Scroll display."""
        self.framebuf.scroll(dx, dy)


class SSD1306_I2C(SSD1306):
    """I2C interface for SSD1306."""

    def __init__(self, width, height, i2c, addr=0x3C, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        self.temp = bytearray(2)
        self.write_list = [b"\x40", None]  # Co=0, D/C#=1
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        """Write command."""
        self.temp[0] = 0x80  # Co=1, D/C#=0
        self.temp[1] = cmd
        self.i2c.writeto(self.addr, self.temp)

    def write_data(self, buf):
        """Write data."""
        self.write_list[1] = buf
        self.i2c.writevto(self.addr, self.write_list)
