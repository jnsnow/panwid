import logging
logger = logging.getLogger(__name__)
import os
import random
import string
from functools import wraps
import re
import itertools

import six
import urwid
from urwid_utils.palette import *
# import urwid_readline
from orderedattrdict import AttrDict

from .datatable import *
from .keymap import *
from .listbox import ScrollingListBox

class DropdownButton(urwid.Button):

    left_chars = u""
    right_chars = u""

    def __init__(self, label, left_chars=None, right_chars=None):

        self.label_text = label
        if left_chars:
            self.left_chars = left_chars
        if right_chars:
            self.right_chars = right_chars

        self.button_left = urwid.Text(self.left_chars)
        self.button_right = urwid.Text(self.right_chars)

        self._label = urwid.SelectableIcon("", cursor_position=0)
        self.cols = urwid.Columns([
            (len(self.left_chars), self.button_left),
            ('weight', 1, self._label),
            (len(self.right_chars), self.button_right)
        ], dividechars=0)
        self.set_label(("dropdown_text", self.label_text))
        super(urwid.Button, self).__init__(self.cols)

    @property
    def decoration_width(self):
        return len(self.left_chars) + len(self.right_chars)

    @property
    def width(self):
        return self.decoration_width + len(self.label_text)


class HighlightableTextMixin(object):

    @property
    def highlight_state(self):
        if not getattr(self, "_highlight_state", False):
            self._highlight_state = False
            self._highlight_case_sensitive = False
            self._highlight_string = None
        return self._highlight_state

    @property
    def highlight_content(self):
        if self.highlight_state:
            return self.get_highlight_text(self._highlight_string)
        else:
            return self.highlight_source


    def highlight(self, s, case_sensitive=False):
        self._highlight_state = True
        self._highlight_case_sensitive = case_sensitive
        self._highlight_string = s
        self.on_highlight()

    def unhighlight(self):
        self._highlight_state = False
        self._highlight_case_sensitive = False
        self._highlight_string = None
        self.on_unhighlight()

    def get_highlight_text(self, s, case_sensitive=False):
        (a, b, c) = re.search(
            r"(.*?)(%s)(.*)" %(self._highlight_string),
            str(self.highlight_source),
            re.IGNORECASE if not case_sensitive else 0
        ).groups()

        return [
            (self.highlightable_attr_normal, a),
            (self.highlightable_attr_highlight, b),
            (self.highlightable_attr_normal, c),
        ]

    @property
    def highlight_source(self):
        raise NotImplementedError

    @property
    def highlightable_attr_normal(self):
        raise NotImplementedError

    @property
    def highlightable_attr_highlight(self):
        raise NotImplementedError

    def on_highlight(self):
        pass

    def on_unhighlight(self):
        pass


class DropdownItem(HighlightableTextMixin, urwid.WidgetWrap):

    signals = ["click"]

    def __init__(self, label, value,
                 margin=0, left_chars=None, right_chars=None):

        self.label_text = label
        self.value = value
        self.margin = margin
        self.button = DropdownButton(
            self.label_text,
            left_chars=left_chars, right_chars=right_chars
        )
        self.padding = urwid.Padding(self.button, width=("relative", 100),
                                     left=self.margin, right=self.margin)


        self.attr = urwid.AttrMap(self.padding, {None: "dropdown_text"})
        self.attr.set_focus_map({
            None: "dropdown_focused",
            "dropdown_text": "dropdown_focused"
        })
        super(DropdownItem, self).__init__(self.attr)
        urwid.connect_signal(
            self.button,
            "click",
            lambda source: self._emit("click")
        )

    @property
    def highlight_source(self):
        return self.label_text

    @property
    def highlightable_attr_normal(self):
        return "dropdown_text"

    @property
    def highlightable_attr_highlight(self):
        return "dropdown_highlight"

    def on_highlight(self):
        self.set_text(self.highlight_content)

    def on_unhighlight(self):
        self.set_text(self.highlight_source)

    @property
    def width(self):
        return self.button.width + 2*self.margin

    @property
    def decoration_width(self):
        return self.button.decoration_width + 2*self.margin

    def __str__(self):
        return self.label_text

    def __contains__(self, s):
        return s in self.label_text

    def startswith(self, s):
        return self.label_text.startswith(s)

    @property
    def label(self):
        return self.button.label

    def set_text(self, text):
        self.button.set_label(text)


# class AutoCompleteEdit(urwid_readline.ReadlineEdit):
@keymapped()
class AutoCompleteEdit(urwid.Edit):

    signals = ["select", "close", "completion_next", "completion_prev"]

    KEYMAP = {
        "enter": "confirm",
        "esc": "cancel"
    }

    def clear(self):
        self.set_edit_text("")

    def confirm(self):
        self._emit("select")
        self._emit("close")

    def cancel(self):
        self._emit("close")

    def next(self):
        self._emit("next")

    def prev(self):
        self._emit("prev")

    def keypress(self, size, key):
        return super().keypress(size, key)

@keymapped()
class AutoCompleteBar(urwid.WidgetWrap):

    signals = ["change", "completion_prev", "completion_next", "select", "close"]

    def __init__(self):

        self.prompt = urwid.Text(("dropdown_prompt", "> "))
        self.text = AutoCompleteEdit("")
        # self.text.selectable = lambda x: False
        self.cols = urwid.Columns([
            (2, self.prompt),
            ("weight", 1, self.text)
        ], dividechars=0)
        self.cols.focus_position = 1
        self.filler = urwid.Filler(self.cols, valign="bottom")
        urwid.connect_signal(self.text, "postchange", self.text_changed)
        urwid.connect_signal(self.text, "completion_prev", lambda source: self._emit("completion_prev"))
        urwid.connect_signal(self.text, "completion_next", lambda source: self._emit("completion_next"))
        urwid.connect_signal(self.text, "select", lambda source: self._emit("select"))
        urwid.connect_signal(self.text, "close", lambda source: self._emit("close"))
        super(AutoCompleteBar, self).__init__(self.filler)

    def set_prompt(self, text):

        self.prompt.set_text(("dropdown_prompt", text))

    def set_text(self, text):

        self.text.set_edit_text(text)

    def text_changed(self, source, text):
        self._emit("change", text)

    def confirm(self):
        self._emit("select")
        self._emit("close")

    def cancel(self):
        self._emit("close")

    def __len__(self):
        return len(self.body)

    def keypress(self, size, key):
        return super().keypress(size, key)

@keymapped()
class AutoCompleteMixin(object):

    auto_complete = None

    def __init__(self, auto_complete, *args, **kwargs):
        super().__init__(self.auto_complete_container, *args, **kwargs)
        if auto_complete is not None: self.auto_complete = auto_complete
        self.auto_complete_bar = None
        self.completing = False
        self.complete_anywhere = False
        self.last_complete_pos = None
        self.last_filter_text = None

        if self.auto_complete:
            self.auto_complete_bar = AutoCompleteBar()


            urwid.connect_signal(
                self.auto_complete_bar, "change",
                lambda source, text: self.complete()
            )
            urwid.connect_signal(
                self.auto_complete_bar, "completion_prev",
                lambda source: self.completion_prev()
            )
            urwid.connect_signal(
                self.auto_complete_bar, "completion_next",
                lambda source: self.completion_next()
            )

            urwid.connect_signal(
                self.auto_complete_bar, "select", self.on_complete_select
            )
            urwid.connect_signal(
                self.auto_complete_bar, "close", self.on_complete_close
            )

    def keypress(self, size, key):
        return super().keypress(size, key)
        # key = super().keypress(size, key)
        # if self.completing and key == "enter":
        #     self.on_complete_select(self)
        # else:
        #     return key

    @property
    def auto_complete_container(self):
        raise NotImplementedError

    @property
    def auto_complete_body(self):
        raise NotImplementedError

    @property
    def auto_complete_items(self):
        raise NotImplementedError

    def auto_complete_widget_at_pos(self, pos):
        return self.auto_complete_body[pos]

    def auto_complete_set_focus(self, pos):
        self.focus_position = pos

    @keymap_command()
    def complete_prefix(self):
        self.complete_on()

    @keymap_command()
    def complete_substring(self):
        self.complete_on(anywhere=True)

    def completion_prev(self):
        self.complete(step=-1)

    def completion_next(self):
        self.complete(step=1)

    def complete_on(self, anywhere=False, case_sensitive=False):

        if self.completing:
            return
        self.completing = True
        self.show_bar()
        if anywhere:
            self.complete_anywhere = True
        else:
            self.complete_anywhere = False


    @keymap_command()
    def complete_off(self):

        if not self.completing:
            return
        self.filter_text = ""

        self.hide_bar()
        self.completing = False

    @keymap_command
    def complete(self, step=None, no_wrap=False, case_sensitive=False):

        if not self.filter_text:
            return

        # if not step and self.filter_text == self.last_filter_text:
        #     return

        logger.info(f"complete: {self.filter_text}")

        if self.last_complete_pos:
            widget = self.auto_complete_widget_at_pos(self.last_complete_pos)
            widget.unhighlight()

        if case_sensitive:
            g = lambda x: x
        else:
            g = lambda x: x.lower()

        if self.complete_anywhere:
            f = lambda x: g(self.filter_text) in g(x)
        else:
            f = lambda x: g(x).startswith(g(self.filter_text))

        self.initial_pos = self.auto_complete_body.get_focus()[1]
        positions = itertools.cycle(self.auto_complete_body.positions(reverse=(step and step < 0)))
        pos = next(positions)
        while pos != self.initial_pos:
            logger.info(pos)
            pos = next(positions)
        for i in range(abs(step or 0)):
            pos = next(positions)

        # cycle = itertools.cycle(
        #     enumerate(self.auto_complete_items)
        #     if step is None or step > 0
        #     else reversed(list(enumerate(self.auto_complete_items)))
        # )
        # rows = list(itertools.islice(cycle, start, end))
        # logger.debug(f"{start}, {end}, len: {len(rows)}")
        while True:
            widget = self.auto_complete_widget_at_pos(pos)
            # logger.info(f"{pos}, {str(widget)}, {self.filter_text}")
            if f(str(widget)):
                self.last_complete_pos = pos
                # widget = self.auto_complete_widget_at_pos(self.auto_complete_items[i])
                widget.highlight(self.filter_text)
                # logger.info(f"found: {pos}")
                self.auto_complete_set_focus(pos)
                break
            pos = next(positions)
            if pos == self.initial_pos:
                break

        logger.info("done")
        self.last_filter_text = self.filter_text

    @keymap_command()
    def cancel(self):
        logger.debug("cancel")
        self.auto_complete_container.focus_position = self.selected_button
        self.close()

    def close(self):
        self._emit("close")

    def show_bar(self):
        self.auto_complete_container.contents.append(
            (self.auto_complete_bar, self.auto_complete_container.options("given", 1))
        )
        # self.box.height -= 1
        self.auto_complete_container.focus_position = 1

    def hide_bar(self):
        widget = self.auto_complete_widget_at_pos(self.auto_complete_body.get_focus()[1])
        widget.unhighlight()
        self.auto_complete_container.focus_position = 0
        del self.auto_complete_container.contents[1]
        # self.box.height += 1

    @property
    def filter_text(self):
        return self.auto_complete_bar.text.get_text()[0]

    @filter_text.setter
    def filter_text(self, value):
        return self.auto_complete_bar.set_text(value)

    def on_complete_select(self, source):
        widget = self.auto_complete_widget_at_pos(self.auto_complete_body.get_focus()[1])
        self.complete_off()
        self._emit("select", self.last_complete_pos, widget)
        self._emit("close")

    def on_complete_close(self, source):
        self.complete_off()

@keymapped()
class DropdownDialog(AutoCompleteMixin, urwid.WidgetWrap, KeymapMovementMixin):

    signals = ["select", "close"]

    min_width = 4

    label = None
    border = None
    scrollbar = False
    margin = 0
    max_height = None

    def __init__(
            self,
            drop_down,
            items,
            default=None,
            label=None,
            border=False,
            margin = None,
            scrollbar=None,
            left_chars=None,
            right_chars=None,
            left_chars_top=None,
            rigth_chars_top=None,
            max_height=None,
            keymap = {},
            **kwargs
    ):
        self.drop_down = drop_down
        self.items = items
        if label is not None: self.label = label
        if border is not None: self.border = border
        if margin is not None: self.margin = margin
        if scrollbar is not None: self.scrollbar = scrollbar
        if max_height is not None: self.max_height = max_height
        # self.KEYMAP = keymap

        self.selected_button = 0
        buttons = []

        buttons = [
                DropdownItem(
                    label=l, value=v, margin=self.margin,
                    left_chars=left_chars,
                    right_chars=right_chars,
                )
                for l, v in self.items.items()
        ]
        self.dropdown_buttons = ScrollingListBox(
            urwid.SimpleListWalker(buttons), with_scrollbar=scrollbar
        )

        urwid.connect_signal(
            self.dropdown_buttons,
            'select',
            lambda source, selection: self.on_complete_select(source)
        )

        box_height = self.height -2 if self.border else self.height
        self.box = urwid.BoxAdapter(self.dropdown_buttons, box_height)
        self.fill = urwid.Filler(self.box)
        kwargs = {}
        if self.label is not None:
            kwargs["title"] = self.label
            kwargs["tlcorner"] = u"\N{BOX DRAWINGS LIGHT DOWN AND HORIZONTAL}"
            kwargs["trcorner"] = u"\N{BOX DRAWINGS LIGHT DOWN AND LEFT}"

        w = self.fill
        if self.border:
           w = urwid.LineBox(w, **kwargs)

        self.pile = urwid.Pile([
            ("weight", 1, w),
        ])
        super().__init__(self.pile)

    @property
    def auto_complete_container(self):
        return self.pile

    @property
    def auto_complete_body(self):
        return self.body

    @property
    def auto_complete_items(self):
        return self.body

    @property
    def max_item_width(self):
        if not len(self):
            return self.min_width
        return max(w.width for w in self)

    @property
    def width(self):
        width = self.max_item_width
        if self.border:
            width += 2
        return width

    @property
    def height(self):
        height = min(len(self), self.max_height)
        if self.border:
            height += 2
        return height

    @property
    def body(self):
        return self.dropdown_buttons.body

    def __getitem__(self, i):
        return self.body[i]

    def __len__(self):
        return len(self.body)

    @property
    def focus_position(self):
        return self.dropdown_buttons.focus_position

    @focus_position.setter
    def focus_position(self, pos):
        self.dropdown_buttons.listbox.set_focus_valign("top")
        self.dropdown_buttons.focus_position = pos

    @property
    def selection(self):
        return self.dropdown_buttons.selection

    # def on_complete_select(self, pos, widget):

    #     # logger.debug("select_button: %s" %(button))
    #     label = widget.label
    #     value = widget.value
    #     self.selected_button = self.focus_position
    #     self.complete_off()
    #     self._emit("select", widget)
    #     self._emit("close")

    # def keypress(self, size, key):
    #     return super(DropdownDialog, self).keypress(size, key)


    @property
    def selected_value(self):
        if not self.focus_position:
            return None
        return self.body[self.focus_position].value

@keymapped()
class Dropdown(urwid.PopUpLauncher):
    # Based in part on SelectOne widget from
    # https://github.com/tuffy/python-audio-tools

    signals = ["change"]

    auto_complete = None
    label = None
    empty_label = u"\N{EMPTY SET}"
    margin = 0

    def __init__(
            self,
            items = None,
            label = None,
            default = None,
            border = False, scrollbar = False,
            margin = None,
            left_chars = None, right_chars = None,
            left_chars_top = None, right_chars_top = None,
            auto_complete = None,
            max_height = 10,
            # keymap = {}
    ):

        if items is not None:
            self._items = items
        if label is not None:
            self.label = label
        self.default = default

        self.border = border
        self.scrollbar = scrollbar
        if auto_complete is not None: self.auto_complete = auto_complete

        # self.keymap = keymap

        if margin:
            self.margin = margin

        if isinstance(self.items, list):
            if len(self.items):
                if isinstance(self.items[0], tuple):
                    self._items = AttrDict(self.items)
                else:
                    logger.debug(self.items)
                    self._items = AttrDict(( (item, n) for n, item in enumerate(self.items)))
            else:
                self._items = AttrDict()
        else:
            self._items = self.items


        self.button = DropdownItem(
            u"", None,
            margin=self.margin,
            left_chars = left_chars_top if left_chars_top else left_chars,
            right_chars = right_chars_top if right_chars_top else right_chars
        )

        self.pop_up = DropdownDialog(
            self,
            self._items,
            self.default,
            label = self.label,
            border = self.border,
            margin = self.margin,
            left_chars = left_chars,
            right_chars = right_chars,
            auto_complete = self.auto_complete,
            scrollbar = scrollbar,
            max_height = max_height,
            # keymap = self.KEYMAP
        )

        urwid.connect_signal(
            self.pop_up,
            "select",
            lambda souce, pos, selection: self.select(selection)
        )

        urwid.connect_signal(
            self.pop_up,
            "close",
            lambda source: self.close_pop_up()
        )

        if self.default is not None:
            try:
                if isinstance(self.default, str):
                    try:
                        self.select_label(self.default)
                    except ValueError:
                        pass
                else:
                    raise StopIteration
            except StopIteration:
                try:
                    self.select_value(self.default)
                except StopIteration:
                    self.focus_position = 0

        if len(self):
            self.select(self.selection)
        else:
            self.button.set_text(("dropdown_text", self.empty_label))

        cols = [ (self.button_width, self.button) ]

        if self.label:
            cols[0:0] = [
                ("pack", urwid.Text([("dropdown_label", "%s: " %(self.label))])),
            ]
        self.columns = urwid.Columns(cols, dividechars=0)

        w = self.columns
        if self.border:
            w = urwid.LineBox(self.columns)
        w = urwid.Padding(w, width=self.width)

        super(Dropdown, self).__init__(w)
        urwid.connect_signal(
            self.button,
            'click',
            lambda button: self.open_pop_up()
        )

    @classmethod
    def get_palette_entries(cls):
        return {
            "dropdown_text": PaletteEntry(
                foreground = "light gray",
                background = "dark blue",
                foreground_high = "light gray",
                background_high = "#003",
            ),
            "dropdown_focused": PaletteEntry(
                foreground = "white",
                background = "light blue",
                foreground_high = "white",
                background_high = "#009",
            ),
            "dropdown_highlight": PaletteEntry(
                foreground = "yellow",
                background = "light blue",
                foreground_high = "yellow",
                background_high = "#009",
            ),
            "dropdown_label": PaletteEntry(
                foreground = "white",
                background = "black"
            ),
            "dropdown_prompt": PaletteEntry(
                foreground = "light blue",
                background = "black"
            )
        }


    @keymap_command()
    def complete_prefix(self):
        if not self.auto_complete:
            return
        self.open_pop_up()
        self.pop_up.complete_prefix()

    @keymap_command()
    def complete_substring(self):
        if not self.auto_complete:
            return
        self.open_pop_up()
        self.pop_up.complete_substring()

    def create_pop_up(self):
        # print("create")
        return self.pop_up

    @property
    def button_width(self):
        return self.pop_up.max_item_width + self.button.decoration_width

    @property
    def pop_up_width(self):
        w = self.button_width
        if self.border:
            w += 2
        return w

    @property
    def contents_width(self):
        # raise Exception(self.button.width)
        w = self.button_width
        if self.label:
            w += len(self.label) + 2
        return max(self.pop_up.width, w)

    @property
    def width(self):
        width = max(self.contents_width, self.pop_up.width)
        if self.border:
            width += 2
        return width

    @property
    def height(self):
        height = self.pop_up.height + 1
        return height

    def pack(self, size, focus=False):
        return (self.width, self.height)

    @property
    def page_size(self):
        return self.pop_up.height

    def open_pop_up(self):
        # print("open")
        super(Dropdown, self).open_pop_up()

    def close_pop_up(self):
        super().close_pop_up()

    def get_pop_up_parameters(self):
        return {'left': (len(self.label) + 2 if self.label else 0),
                'top': 0,
                'overlay_width': self.pop_up_width,
                'overlay_height': self.pop_up.height
        }

    @property
    def focus_position(self):
        return self.pop_up.focus_position

    @focus_position.setter
    def focus_position(self, pos):
        if pos == self.focus_position:
            return
        # self.select_index(pos)
        old_pos = self.focus_position
        self.pop_up.selected_button = self.pop_up.focus_position = pos
        self.select(self.selection)

    @property
    def items(self):
        return self._items

    @property
    def selection(self):
        return self.pop_up.selection

    def select_label(self, label, case_sensitive=False):

        old_value = self.value

        f = lambda x: x
        if not case_sensitive:
            f = lambda x: x.lower()

        index = next(itertools.dropwhile(
                lambda x: f(x[1]) != f(label),
                enumerate((self._items.keys())
            )
        ))[0]
        self.focus_position = index



    @property
    def items(self):
        return self._items

    @property
    def selection(self):
        return self.pop_up.selection


    def select_label(self, label, case_sensitive=False):

        old_value = self.value

        f = lambda x: x
        if not case_sensitive:
            f = lambda x: x.lower() if isinstance(x, str) else x

        try:
            index = next(itertools.dropwhile(
                    lambda x: f(x[1]) != f(label),
                    enumerate((self._items.keys())
                )
            ))[0]
        except StopIteration:
            raise ValueError
        self.focus_position = index



    def select_value(self, value):

        index = next(itertools.dropwhile(
                lambda x: x[1] != value,
                enumerate((self._items.values())
            )
        ))[0]
        self.focus_position = index


    @property
    def labels(self):
        return self._items.keys()

    @property
    def values(self):
        return self._items.values()

    @property
    def selected_label(self):
        return self.selection.label

    @selected_label.setter
    def selected_label(self, label):
        return self.select_label(label)

    @property
    def selected_value(self):
        if not self.selection:
            return None
        return self.selection.value

    @selected_value.setter
    def selected_value(self, value):
        return self.select_value(value)

    @property
    def value(self):
        return self.selected_value

    @value.setter
    def value(self, value):
        old_value = self.value

        # try to set by value.  if not found, try to set by label
        try:
            self.selected_value = value
        except StopIteration:
            self.selected_label = value

    def cycle_prev(self):
        self.cycle(-1)

    @keymap_command("cycle")
    def cycle(self, n):
        pos = self.focus_position + n
        if pos > len(self) - 1:
            pos = len(self) - 1
        elif pos < 0:
            pos = 0
        # self.focus_position = pos
        self.focus_position = pos

    def select(self, button):
        logger.debug("select: %s" %(button))
        self.button.set_text(("dropdown_text", button.label))
        self.pop_up.dropdown_buttons.listbox.set_focus_valign("top")
        # if old_pos != pos:
        self._emit("change", self.selected_label, self.selected_value)

    # def set_items(self, items, selected_value):
    #     self._items = items
    #     self.make_selection([label for (label, value) in items if
    #                          value is selected_value][0],
    #                         selected_value)
    def __len__(self):
        return len(self.items)

__all__ = ["Dropdown"]
