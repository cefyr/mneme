#!/usr/bin/env python3

import collections
import copy
from os import getenv
from os.path import isdir, join
import re
import sys

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt

from libsyntyche.common import read_json, read_file, write_json, kill_theming, local_path, make_sure_config_exists
from libsyntyche.fileviewer import FileViewer
from indexframe import IndexFrame


class MainWindow(QtGui.QFrame):
    def __init__(self, configdir, activation_event, dry_run):
        super().__init__()
        self.setWindowTitle('Mneme')
        self.configdir = configdir
        activation_event.connect(self.reload_settings)
        self.force_quit_flag = False

        # Create layouts
        self.stack = QtGui.QStackedLayout(self)
        kill_theming(self.stack)

        # Index viewer
        self.index_viewer = IndexFrame(self, dry_run)
        self.stack.addWidget(self.index_viewer)

        # Popup viewer
        self.popup_viewer = FileViewer(self)
        self.stack.addWidget(self.popup_viewer)
        self.popuphomekey = QtGui.QShortcut(QtGui.QKeySequence(),
                                            self.popup_viewer,
                                            self.show_index)

        # Load settings
        self.defaultstyle = read_json(local_path('defaultstyle.json'))
        self.css_template = read_file(local_path(join('templates','template.css')))
        self.index_css_template = read_file(local_path(join('templates','index_page.css')))
        self.settings, self.style = {}, {}
        self.reload_settings()

        # Misc
        self.connect_signals()
        self.show()


    def quit(self, force):
        self.force_quit_flag = force
        self.close()

    def connect_signals(self):
        connects = (
            (self.index_viewer.quit,        self.close),
            (self.index_viewer.show_popup,  self.show_popup),
        )
        for signal, slot in connects:
            signal.connect(slot)


    def show_index(self):
        self.stack.setCurrentWidget(self.index_viewer)
        self.index_viewer.terminal.setFocus()

    def show_popup(self, *args):
        self.popup_viewer.set_page(*args)
        self.stack.setCurrentWidget(self.popup_viewer)


    def reload_settings(self):
        settings, style, stylepath = read_config(self.configdir, self.defaultstyle)
        # TODO: FIX THIS UGLY ASS SHIT
        # Something somewhere fucks up and changes the settings dict,
        # therefor the deepcopy(). Fix pls.
        if settings != self.settings:
            if settings['title']:
                self.setWindowTitle(settings['title'])
            else:
                self.setWindowTitle('Mneme')
            self.settings = copy.deepcopy(settings)
            self.index_viewer.update_settings(settings)
            self.popuphomekey.setKey(QtGui.QKeySequence(settings['hotkeys']['home']))
        if style != self.style:
            self.style = style.copy()
            self.update_style(style)
            write_json(stylepath, style)


    def update_style(self, style):
        try:
            css = self.css_template.format(**style)
            indexcss = self.index_css_template.format(**style)
        except KeyError as e:
            print(e)
            self.index_viewer.error('Invalid style config: key missing')
            return
        self.setStyleSheet(css)
        self.index_viewer.defaulttagcolor = style['index entry tag default background']
        self.index_viewer.css = indexcss
        self.index_viewer.refresh_view(keep_position=True)


    # ===== Input overrides ===========================
    def wheelEvent(self, ev):
        self.index_viewer.webview.wheelEvent(ev)

    def keyPressEvent(self, ev):
        if self.stack.currentWidget() == self.index_viewer and ev.key() in (Qt.Key_PageUp, Qt.Key_PageDown):
            self.index_viewer.webview.keyPressEvent(ev)
        else:
            return super().keyPressEvent(ev)

    def keyReleaseEvent(self, ev):
        if self.stack.currentWidget() == self.index_viewer and ev.key() in (Qt.Key_PageUp, Qt.Key_PageDown):
            self.index_viewer.webview.keyReleaseEvent(ev)
        else:
            return super().keyReleaseEvent(ev)
    # =================================================


def read_config(configdir, defaultstyle):
    if configdir:
        configpath = configdir
    else:
        configpath = join(getenv('HOME'), '.config', 'mneme')
    configfile = join(configpath, 'settings.json')
    stylefile = join(configpath, 'style.json')
    make_sure_config_exists(configfile, local_path('defaultconfig.json'))
    make_sure_config_exists(stylefile, local_path('defaultstyle.json'))
    # Make sure to update the style with the defaultstyle's values
    newstyle = read_json(stylefile)
    style = defaultstyle.copy()
    style.update({k:v for k,v in newstyle.items() if k in defaultstyle})
    return read_json(configfile), style, stylefile


def main():
    import argparse
    parser = argparse.ArgumentParser()
    def valid_dir(dirname):
        if isdir(dirname):
            return dirname
        parser.error('Directory does not exist: {}'.format(dirname))
    parser.add_argument('-c', '--config-directory', type=valid_dir)
    parser.add_argument('-d', '--dry-run', action='store_true',
                        help='don\'t write anything to disk')
    args = parser.parse_args()

    app = QtGui.QApplication(sys.argv)

    class AppEventFilter(QtCore.QObject):
        activation_event = QtCore.pyqtSignal()
        def eventFilter(self, object, event):
            if event.type() == QtCore.QEvent.ApplicationActivate:
                self.activation_event.emit()
            return False
    app.event_filter = AppEventFilter()
    app.installEventFilter(app.event_filter)

    window = MainWindow(args.config_directory,
                        app.event_filter.activation_event,
                        args.dry_run)
    app.setActiveWindow(window)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
