﻿from PySide.QtGui import *
from PySide.QtCore import *
import res
from ui.configdialog import Ui_Settings
from ui.editor import Ui_Editor
from ui.customwidgets import SearchBox
from ui.customobjects import *
from db import Nikki

import sys, os
import socket
import time
import random
import logging

__version__ = 0.08


def restart_main():
    "Restart Main Window after language changed in settings."
    logging.debug('restart_main called')
    global main
    geo = main.saveGeometry()
    # delete the only reference to old one
    main = Main()
    main.restoreGeometry(geo)
    main.show()

def set_trans(settings):
    "Install translations"
    lang = settings.value('Main/lang')
    if lang is None:
        settings.setValue('Main/lang', 'en')
    else:
        global trans, transQt
        trans = QTranslator()
        trans.load('lang/'+lang)
        transQt = QTranslator()
        transQt.load('qt_'+lang, QLibraryInfo.location(QLibraryInfo.TranslationsPath))
        for i in [trans, transQt]: qApp.installTranslator(i)

def backupcheck(dbpath):
    "Check backups and do if necessary.Delete old backups."
    bkpath = 'backup'
    if not os.path.isdir(bkpath): os.mkdir(bkpath)
    dblst = sorted(os.listdir(bkpath))
    fil = lambda x: len(x)>10 and x[4]==x[7]=='-' and x[10]=='_'
    dblst = list(filter(fil, dblst))

    fmt = '%Y-%m-%d'
    today = time.strftime(fmt)
    try:
        newest = dblst[-1]
    except IndexError:  # empty directory
        newest = ''
    if newest.split('_')[0] != today:  # new day
        # make new backup
        import shutil
        shutil.copyfile(dbpath, os.path.join(bkpath,
                                             today+'_%d.db' % nikki.count()))
        logging.info('Everyday backup succeed')
        # delete old backups
        weekbefore = time.strftime(fmt , time.localtime(int(time.time())-604800))
        for dname in dblst:
            if dname < weekbefore:
                os.remove(os.path.join(bkpath, dname))
            else:
                break


class NListDelegate(QStyledItemDelegate):
    stylesheet = ('QListWidget{background-color: rgb(242, 241, 231);'
                  'border: solid 0px; margin-top: 1px}')
    def __init__(self):
        super(NListDelegate, self).__init__()
        self.title_h = QFontInfo(titlefont).pixelSize() + 10  # title area height
        self.text_h = (QFontMetrics(textfont).lineSpacing() *
                       int(settings.value('Nlist/previewlines', 4)))
        self.tagpath_h = QFontInfo(qApp.font()).pixelSize() + 4
        self.tag_h = self.tagpath_h + 4
        self.dt_w = QFontMetrics(titlefont).width('2000/00/00 00:00') + 20
        # doc is used to draw text(diary's body)
        self.doc = NTextDocument()
        self.doc.setDefaultFont(textfont)
        self.doc.setUndoRedoEnabled(False)
        self.doc.setDocumentMargin(0)
        # setup colors
        self.c_bg = QColor(255, 236, 176)
        self.c_border = QColor(214, 172, 41)
        self.c_unselbg = QColor(255, 236, 176, 40)
        self.c_gray = QColor(93, 73, 57)

    def paint(self, painter, option, index):
        x, y, w = option.rect.x(), option.rect.y(), option.rect.width()-1
        row = index.data()
        selected = bool(option.state & QStyle.State_Selected)
        active = bool(option.state & QStyle.State_Active)
        # draw border and background
        painter.setPen(self.c_border)
        painter.setBrush(self.c_bg if selected and active else
                         self.c_unselbg)
        border = QRect(x+1, y, w-2, self.all_h)
        painter.drawRect(border)
        if selected:
            innerborder = QRect(x+2, y+1, w-4, self.all_h-2)
            pen = QPen()
            pen.setStyle(Qt.DashLine)
            pen.setColor(self.c_gray)
            painter.setPen(pen)
            painter.drawRect(innerborder)
        # draw datetime and title
        painter.setPen(self.c_gray)
        painter.drawLine(x+10, y+self.title_h, x+w-10, y+self.title_h)
        painter.setPen(Qt.black)
        painter.setFont(datefont)
        painter.drawText(x+14, y, w, self.title_h, Qt.AlignBottom, row['datetime'])
        if row['title']:
            painter.setFont(titlefont)
            title_w = w-self.dt_w-13
            title = ttfontm.elidedText(row['title'], Qt.ElideRight, title_w)
            painter.drawText(x+self.dt_w, y, title_w, self.title_h,
                             Qt.AlignBottom|Qt.AlignRight, title)
        # draw text
        painter.save()
        formats = None if row['plaintext'] else nikki.getformat(row['id'])
        self.doc.setText(row['text'], formats)
        self.doc.setTextWidth(w-26)
        painter.translate(x+14, y+self.title_h+2)
        self.doc.drawContents(painter, QRect(0, 0, w-26, self.text_h))
        painter.restore()
        # draw tags
        if row['tags']:
            painter.save()
            painter.setPen(self.c_gray)
            painter.setFont(qApp.font())
            painter.translate(x + 15, y+self.title_h+6+self.text_h)
            for t in row['tags'].split():
                w = defontm.width(t) + 4
                tagpath = QPainterPath()
                tagpath.moveTo(8, 0)
                tagpath.lineTo(8+w, 0)
                tagpath.lineTo(8+w, self.tagpath_h)
                tagpath.lineTo(8, self.tagpath_h)
                tagpath.lineTo(0, self.tagpath_h/2)
                tagpath.closeSubpath()
                painter.drawPath(tagpath)
                painter.drawText(8, 1, w, self.tagpath_h, Qt.AlignCenter, t)
                painter.translate(w+15, 0)  # translate by offset
            painter.restore()

    def sizeHint(self, option, index):
        tag_h = self.tag_h if index.data()['tags'] else 0
        self.all_h = self.title_h + self.text_h + tag_h + 10
        return QSize(-1, self.all_h+3)  # 3 is spacing between entries


class TListDelegate(QStyledItemDelegate):
    '''Default TagList(TList) Delegate.Also contains TList's stylesheet'''
    TListSS = ('QListWidget{background-color: rgb(234,182,138);'
               'border: solid 0px}')
    def __init__(self):
        super(TListDelegate, self).__init__()
        self.h = QFontInfo(defont).pixelSize()+8

    def paint(self, painter, option, index):
        x, y, w= option.rect.x(), option.rect.y(), option.rect.width()
        tag, count = index.data(3), str(index.data(2))
        painter.setFont(defont)

        selected = bool(option.state & QStyle.State_Selected)

        if index.row() == 0:  # row 0 is always All(clear tag filter)
            painter.setPen(QColor(80, 80, 80))
            painter.drawText(x+4, y+1, w-8, self.h-1,
                             Qt.AlignLeft|Qt.AlignLeft,
                             qApp.translate('TList', 'All'))
        else:
            painter.setPen(QColor(209, 109, 63))
            painter.drawLine(x, y, w, y)
            if selected:
                trect = QRect(x, y+1, w-1, self.h-2)
                painter.setPen(QColor(181, 61, 0))
                painter.setBrush(QColor(250, 250, 250))
                painter.drawRect(trect)

            # draw tag
            painter.setPen(QColor(20, 20, 20) if selected else
                           QColor(80, 80, 80))
            textarea = QRect(x+4, y, w-8, self.h)
            tag = defontm.elidedText(tag, Qt.ElideRight, w-dfontm.width(count)-12)
            painter.drawText(textarea, Qt.AlignVCenter|Qt.AlignLeft, tag)
            # draw tag count
            painter.setFont(datefont)
            painter.drawText(textarea, Qt.AlignVCenter|Qt.AlignRight, count)

    def sizeHint(self, option, index):
        return QSize(-1, self.h)


class Entry(QListWidgetItem):
    def __init__(self, row, parent=None):
        super(Entry, self).__init__(parent)
        self.setData(2, row)


class NList(QListWidget):
    def __init__(self):
        super(NList, self).__init__()
        self.setMinimumSize(350,200)
        self.editors = {}

        self.setSelectionMode(self.ExtendedSelection)
        self.itemDoubleClicked.connect(self.starteditor)

        self.setItemDelegate(NListDelegate())
        self.setStyleSheet(NListDelegate.stylesheet)

        # Context Menu
        self.editAct = QAction(self.tr('Edit'), self,
                               shortcut=QKeySequence(Qt.Key_Return),
                               triggered=self.starteditor)
        self.delAct = QAction(self.tr('Delete'), self,
                              shortcut=QKeySequence.Delete,
                              triggered=self.delNikki)
        self.selAct = QAction(self.tr('Random'), self,
                              shortcut=QKeySequence(Qt.Key_F7),
                              triggered=self.selectRandomly)
        for i in [self.editAct, self.delAct, self.selAct]: self.addAction(i)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction(self.editAct)
        menu.addAction(self.delAct)
        menu.addSeparator()
        menu.addAction(self.selAct)

        selcount = len(self.selectedItems())
        self.editAct.setDisabled(True if selcount!=1 else False)
        self.delAct.setDisabled(False if selcount!=0 else True)
        self.selAct.setDisabled(False if selcount!=0 else True)
        menu.popup(event.globalPos())

    def starteditor(self, item=None, new=False):
        # called by doubleclick event or contextmenu or key-shortcut
        if not new:
            curtitem = item if item else self.selectedItems()[0]
            nikki = curtitem.data(2)
            id = nikki['id']
        else:
            curtitem = nikki = id = None

        if id in self.editors:
            self.editors[id].activateWindow()
        else:  # create new editor
            editor = Editor(new=True if id is None else False, row=nikki)
            self.editors[id] = editor
            editor.item = curtitem
            editor.show()

    def delNikki(self):
        msgbox = QMessageBox(QMessageBox.NoIcon,
                             self.tr('Delete selected diaries'),
                             self.tr('Selected diaries will be deleted '
                                     'permanently.Do it?'),
                             QMessageBox.Yes|QMessageBox.No,
                             parent=self)
        msgbox.setDefaultButton(QMessageBox.Cancel)
        ret = msgbox.exec_()

        if ret == QMessageBox.Yes:
            for i in self.selectedItems():
                nikki.delete(i.data(2)['id'])
                self.takeItem(self.row(i))
            if main.tlist.isVisible(): main.tlist.load()
            main.updateCountLabel()

        # QWidget.destroy() doesn't work
        msgbox.deleteLater()

    def newNikki(self):
        self.starteditor(None, True)

    def load(self, *, tagid=None, search=None):
        order, reverse = self.getOrder()
        for e in nikki.sorted(order, reverse, tagid=tagid, search=search):
            Entry(e, self)

        self.setCurrentRow(0)

    def reload(self, id):
        order, reverse = self.getOrder()
        logging.debug('Nikki List reload')
        self.clear()
        for e in nikki.sorted(order, reverse):
            if e['id'] == id:
                rownum = self.count()
            Entry(e, self)

        main.searchbox.clear()
        main.tlist.setCurrentRow(0)
        self.setCurrentRow(rownum)

    def getOrder(self):
        "get sort order(str) and reverse(int) from settings file"
        order = settings.value('NList/sortOrder', 'datetime')
        reverse = int(settings.value('NList/sortReverse', 1))
        return order, reverse

    def selectRandomly(self):
        self.setCurrentRow(random.randrange(0, self.count()))

    def editorNext(self):
        self.editorMove(1)

    def editorPrevious(self):
        self.editorMove(-1)

    def editorMove(self, step):
        '''Move to the Previous/Next Diary in Editor.Current
        Editor will close without saving,'''
        curtEditor = [k for k in self.editors.values()][0]
        try:
            index = self.row(curtEditor.item)
        except RuntimeError:  # C++ object already deleted
            return
        # disabled when multi-editor or editing new diary(if new,
        # shortcut would not be set) or no item to move on.
        if len(self.editors) != 1 or index is None:
            return
        elif step == 1 and not index < self.count()-1:
            return
        elif step == -1 and not 0 < index:
            return
        else:
            self.setCurrentRow(index+step)
            self.starteditor()
            curtEditor.closeNoSave()

    def sortDT(self, checked):
        if checked:
            settings.setValue('NList/sortOrder', 'datetime')
            self.clear()
            self.load()

    def sortTT(self, checked):
        if checked:
            settings.setValue('NList/sortOrder', 'title')
            self.clear()
            self.load()

    def sortLT(self, checked):
        if checked:
            settings.setValue('NList/sortOrder', 'length')
            self.clear()
            self.load()

    def sortRE(self, checked):
        settings.setValue('NList/sortReverse', int(checked))
        self.clear()
        self.load()


class Editor(QWidget, Ui_Editor):
    "Widget used to edit diary's body,title,tag, datetime."
    def __init__(self, new, row):
        super(Editor, self).__init__()
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setupUi(self)
        self.new = new
        # setup window geometry
        if int(settings.value("Editor/centeropen", 0)):
            center = main.geometry().center()
            w, h = settings.value('Editor/size', (500,400))
            self.setGeometry(center.x()-w/2, center.y()-h/2, int(w), int(h))
        else:
            self.restoreGeometry(settings.value("Editor/windowGeo"))
        # setup texteditor and titleeditor, set window title
        if not new:
            self.id = row['id']
            self.datetime = row['datetime']
            self.titleEditor.setText(row['title'])
            formats = None if row['plaintext'] else nikki.getformat(row['id'])
            self.textEditor.setText(row['text'], formats)
        else:
            self.id = self.datetime = None
        self.textEditor.setFont(textfont)
        self.textEditor.setAutoIndent(int(settings.value(':/Editor/autoindent', 1)))
        self.titleEditor.setFont(titlefont)
        titlehint = (row['title'] if row else None) or \
                    (self.datetime.split()[0] if self.datetime else None) or \
                    self.tr('New Diary')
        self.setWindowTitle("%s - Hazama" % titlehint)
        # setup datetime display
        self.dtLabel.setText(self.datetime if self.datetime is not None else '')
        self.dtLabel.setFont(datefont)
        self.dtBtn.setIcon(QIcon(':/editor/clock.png'))
        sz = min(dfontm.ascent(), 16)
        self.dtBtn.setIconSize(QSize(sz, sz))
        # set up tageditor
        self.updateTagEditorFont('')
        if not new: self.tagEditor.setText(row['tags'])
        completer = TagCompleter(nikki.gettag(), self)
        self.tagEditor.setCompleter(completer)
        self.timeModified = self.tagsModified = False
        # setup shortcuts
        self.closeSaveSc = QShortcut(QKeySequence.Save, self)
        self.closeSaveSc.activated.connect(self.close)
        self.closeSaveSc2 = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.closeSaveSc2.activated.connect(self.close)
        if not new:
            self.preSc = QShortcut(QKeySequence(Qt.CTRL+Qt.Key_PageUp), self)
            self.preSc.activated.connect(main.nlist.editorPrevious)
            self.nextSc = QShortcut(QKeySequence(Qt.CTRL+Qt.Key_PageDown), self)
            self.nextSc.activated.connect(main.nlist.editorNext)

    def closeEvent(self, event):
        "Save geometry information and diary(if changed)"
        if int(settings.value('Editor/centeropen', 0)):
            settings.setValue('Editor/size', self.size().toTuple())
        else:
            settings.setValue('Editor/windowGeo', self.saveGeometry())
        self.saveNikki()
        event.accept()
        del main.nlist.editors[self.id]

    def closeNoSave(self):
        self.hide()
        self.deleteLater()
        del main.nlist.editors[self.id]

    def saveNikki(self):
        "Save when necessary;Refresh NList and TList when necessary"
        if (self.textEditor.document().isModified() or
        self.titleEditor.isModified() or self.timeModified or
        self.tagsModified):
            if self.datetime is None:
                self.datetime = time.strftime('%Y-%m-%d %H:%M')
            if self.tagsModified:
                tags = self.tagEditor.text().split()
                tags = list(filter(lambda t: tags.count(t)==1, tags))
            else:
                tags = None
            # realid: id returned by database
            realid = nikki.save(self.id, self.datetime,
                                self.textEditor.toHtml(),
                                self.titleEditor.text(), tags)
            main.nlist.reload(realid)
            if self.new: main.updateCountLabel()

        if self.tagsModified and main.tlist.isVisible():
            main.tlist.load()

    @Slot()
    def on_tagEditor_textEdited(self):
        # tageditor.isModified() will be reset by completer.So this instead.
        self.tagsModified = True

    @Slot()
    def on_dtBtn_clicked(self):
        time = DateTimeDialog.getDateTime(self.datetime, self)
        if time is not None and time!=self.datetime:
            self.datetime = time
            self.dtLabel.setText(time)
            self.timeModified = True

    def showEvent(self, event):
        if not int(settings.value('/Editor/titlefocus', 1)):
            self.textEditor.setFocus()
        self.textEditor.moveCursor(QTextCursor.Start)

    def updateTagEditorFont(self, text):
        "Set tagEditor's placeHoderFont to italic"
        fontstyle = 'normal' if text else 'italic'
        self.tagEditor.setStyleSheet('font-style: %s' % fontstyle)


class DateTimeDialog(QDialog):
    timeFmt = "yyyy-MM-dd HH:mm"
    def __init__(self, timestr, parent=None):
        super(DateTimeDialog, self).__init__(parent, Qt.WindowTitleHint)
        self.setWindowModality(Qt.WindowModal)
        self.setWindowTitle(self.tr('Edit datetime'))
        self.setMinimumWidth(100)

        self.verticalLayout = QVBoxLayout(self)

        if timestr is None:
            timestr = time.strftime('%Y-%m-%d %H:%M')
        dt = QDateTime.fromString(timestr, self.timeFmt)
        self.dtEdit = QDateTimeEdit(dt)
        self.dtEdit.setDisplayFormat(self.timeFmt)
        self.verticalLayout.addWidget(self.dtEdit)

        self.btnBox = QDialogButtonBox()
        self.btnBox.setOrientation(Qt.Horizontal)
        self.btnBox.setStandardButtons(QDialogButtonBox.Ok |
                                       QDialogButtonBox.Cancel)
        self.verticalLayout.addWidget(self.btnBox)

        self.btnBox.accepted.connect(self.accept)
        self.btnBox.rejected.connect(self.reject)

    @staticmethod
    def getDateTime(timestr, parent):
        "Run Dialog,return None if canceled,otherwise return timestr"
        dialog = DateTimeDialog(timestr, parent)
        code = dialog.exec_()
        return dialog.dtEdit.dateTime().toString(dialog.timeFmt) if code else None


class Main(QWidget):
    def __init__(self):
        super(Main, self).__init__()
        self.restoreGeometry(settings.value("Main/windowGeo"))
        self.setWindowTitle('Hazama Prototype Ver'+str(__version__))

        self.nlist = NList()
        self.nlist.load()
        self.tlist = TList()
        self.splitter = MainSplitter()
        self.toolbar = QToolBar()
        self.searchbox = SearchBox()
        self.countlabel = QLabel()

        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)

        # setuo MainSplitter
        self.splitter.splitterMoved.connect(self.keepTList)
        self.searchbox.textChanged.connect(self.filter)
        self.splitter.addWidget(self.tlist)
        self.splitter.addWidget(self.nlist)
        for i in range(2):
            self.splitter.setCollapsible(i, False)

        # setup ToolBar
        self.creActs()  #create actions
        self.toolbar.setIconSize(QSize(24, 24))
        self.toolbar.setStyleSheet('QToolBar{background: rgb(242, 241, 231);'
                                   'border-bottom: 1px solid rgb(181, 61, 0);'
                                   'padding: 2px; spacing: 2px}')
        self.sorAct.setMenu(SortOrderMenu(nlist=self.nlist))
        for a in [self.creAct, self.delAct, self.tlistAct, self.sorAct, self.cfgAct]:
            self.toolbar.addAction(a)
        #label
        self.countlabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.countlabel.setAlignment(Qt.AlignVCenter|Qt.AlignRight)
        self.countlabel.setIndent(6)
        self.countlabel.setStyleSheet('color: rgb(144, 144, 144)')
        self.updateCountLabel()
        self.toolbar.addWidget(self.countlabel)

        self.toolbar.addWidget(self.searchbox)
        self.searchbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        sortbtn = self.toolbar.widgetForAction(self.sorAct)
        sortbtn.setPopupMode(QToolButton.InstantPopup)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.splitter)
        self.setLayout(layout)
        if not int(settings.value('Main/TListVisible', 0)): self.tlist.hide()

    def closeEvent(self, event):
        settings.setValue('Main/windowGeo', self.saveGeometry())
        TListWidth = self.splitter.sizes()[0]
        if TListWidth == 0:
            settings.setValue('Main/TListVisible', 0)
        else:
            settings.setValue('Main/TListVisible', 1)

        event.accept()
        qApp.quit()

    def keepTList(self, pos=None, index=None, init=False):
        "keep TList's size when reducing window's width"
        if init:
            self.setMinimumWidth(int(settings.value('Main/TListWidth'))+350+2)
        else:
            if self.tlist.isVisible():
                self.setMinimumWidth(pos+350+2)

    def filter(self, text=None):
        "Connected to SearchBox and TList.text belongs to SearchBox's event"
        text = self.searchbox.text()
        try:
            tagid = self.tlist.currentItem().data(1)
        except AttributeError:  # TList hidden
            tagid = None
        search = text if text else None

        if tagid == 'All':
            self.nlist.clear()
            self.nlist.load(search=search)
        else:
            self.nlist.clear()
            self.nlist.load(tagid=tagid, search=search)

    def creActs(self):
        self.tlistAct = QAction(QIcon(':/images/tlist.png'), self.tr('Tag List'),
                                self, shortcut=QKeySequence(Qt.Key_F9))
        self.tlistAct.setCheckable(True)
        self.tlistAct.triggered[bool].connect(self.setTList)
        self.creAct = QAction(QIcon(':/images/new.png'), self.tr('New'),
                              self, shortcut=QKeySequence.New,
                              triggered=self.nlist.newNikki)
        self.delAct = QAction(QIcon(':/images/delete.png'), self.tr('Delete'),
                              self, triggered=self.nlist.delNikki)
        self.sorAct = QAction(QIcon(':/images/sort.png'), self.tr('Sort By'), self)
        self.cfgAct = QAction(QIcon(':/images/config.png'), self.tr('Settings'),
                              self, triggered=self.startConfigDialog)

    def startConfigDialog(self):
        self.cfgdialog = ConfigDialog(self)
        self.cfgdialog.show()

    def setTList(self, checked):
        self.tlist.setVisible(checked)

    def showEvent(self, event):
        self.nlist.setFocus()

    def updateCountLabel(self):
        "Only called when diary saving or deleting"
        c = nikki.count()
        if c > 1: self.countlabel.setText(self.tr('%i diaries') % c)


class TList(QListWidget):
    def __init__(self):
        super(TList, self).__init__()
        self.setItemDelegate(TListDelegate())
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setUniformItemSizes(True)
        self.setStyleSheet(TListDelegate.TListSS)

    def load(self):
        logging.info('Tag List load')
        self.clear()  # this may emit unexpected signal when has selection
        all = QListWidgetItem(self)
        all.setData(1, 'All')
        for t in nikki.gettag(getcount=True):
            item = QListWidgetItem(self)
            item.setData(3, t[1])
            item.setData(2, t[2])
            item.setData(1, t[0])

    def showEvent(self, event):
        self.load()
        main.keepTList(init=True)
        self.setCurrentRow(0)
        # avoid refreshing nlist by unexpected signal
        self.itemSelectionChanged.connect(main.filter)
        main.tlistAct.setChecked(True)

    def hideEvent(self, event):
        # Reset minimumWidth which set by Main.keepTList
        main.setMinimumWidth(350)
        # currentItem is None when tag deleted
        if self.currentItem() is None or self.currentItem().data(1)!='All':
            self.setCurrentRow(0)
        # avoid refreshing nlist by unexpected signal
        self.itemSelectionChanged.disconnect(main.filter)
        settings.setValue('Main/TListWidth', main.splitter.sizes()[0])

    # all three events below for drag scroll
    def mousePressEvent(self, event):
        self.tracklst = []

    def mouseMoveEvent(self, event):
        if self.tracklst != None:
            self.tracklst.append(event.pos().y())
            if len(self.tracklst) > 4:
                change = self.tracklst[-1] - self.tracklst[-2]
                scrollbar = self.verticalScrollBar()
                scrollbar.setValue(scrollbar.value() - change)

    def mouseReleaseEvent(self, event):
        if self.tracklst is not None:
            if len(self.tracklst) <= 4:  # haven't moved
                pevent = QMouseEvent(QEvent.MouseButtonPress, event.pos(),
                                    event.globalPos(), Qt.LeftButton,
                                    Qt.LeftButton, Qt.NoModifier)
                QListWidget.mousePressEvent(self, pevent)

        self.tracklst = None


class MainSplitter(QSplitter):
    def __init__(self, parent=None):
        super(MainSplitter, self).__init__(parent)
        self.setHandleWidth(2)

    def resizeEvent(self, event):
        # reference: stackoverflow.com/questions/14397653
        if event.oldSize().width() != -1:
            TListWidth = self.sizes()[0]
            self.setSizes([TListWidth, event.size().width()-2-TListWidth])
        else:
            # init, set taglist to saved size
            w = int(settings.value('Main/TListWidth', 0))
            self.setSizes([w, event.size().width()-2-w])

    def createHandle(self):
        handle = TSplitterHandle(Qt.Horizontal, self)
        handle.setCursor(Qt.SizeHorCursor)
        return handle


class TSplitterHandle(QSplitterHandle):
    def paintEvent(self, event):
        w, h = self.size().toTuple()
        painter = QPainter(self)
        painter.fillRect(0, 0, w-1, h, QColor(234, 182, 138))  # same as bg of TList
        painter.fillRect(w-1, 0, 1, h, QColor(181, 61, 0))


class ConfigDialog(QDialog, Ui_Settings):
    # first try that using Qt Designer generated UI.
    lang2index = {'en': 0, 'zh_CN': 1, 'ja': 2}  # index used in combo
    index2lang = {b: a for (a, b) in lang2index.items()}
    def __init__(self, parent=None):
        super(ConfigDialog, self).__init__(parent, Qt.WindowTitleHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setupUi(self)
        self.setFont(sysfont)

        self.aindCheck.setChecked(int(settings.value('Editor/autoindent', 1)))
        self.copenCheck.setChecked(int(settings.value('Editor/centeropen', 0)))
        self.tfocusCheck.setChecked(int(settings.value('Editor/titlefocus', 0)))
        self.bkCheck.setChecked(int(settings.value('Main/backup', 1)))
        self.langCombo.setCurrentIndex(self.lang2index[
                                       settings.value('Main/lang', 'en')])

    def closeEvent(self, event):
        del main.cfgdialog
        event.accept()

    def accept(self):
        settings.setValue('Editor/autoindent', int(self.aindCheck.isChecked()))
        settings.setValue('Editor/centeropen', int(self.copenCheck.isChecked()))
        settings.setValue('Editor/titlefocus', int(self.tfocusCheck.isChecked()))
        settings.setValue('Main/backup', int(self.bkCheck.isChecked()))
        lang = self.index2lang[self.langCombo.currentIndex()]
        if settings.value('Main/lang') != lang:
            settings.setValue('Main/lang', lang)
            set_trans(settings)
            restart_main()
        logging.info('Settings saved')
        try:
            super(ConfigDialog, self).accept()
        except RuntimeError:
            # main.cfgdialog has been deleted after restart_main
            pass

    @Slot()
    def on_exportBtn_clicked(self):
        export_all = not bool(self.exportOption.currentIndex())
        txtpath, type = QFileDialog.getSaveFileName(self,
            self.tr('Export Diary'), os.getcwd(),
            self.tr('Plain Text (*.txt);;Rich Text (*.rtf)'))

        if txtpath == '': return    # dialog canceled
        if type.endswith('txt)'):
            selected = (None if export_all else
                        [i.data(2) for i in main.nlist.selectedItems()])
            nikki.exporttxt(txtpath, selected)



if __name__ == '__main__':
    program_path = os.path.dirname(os.path.realpath(__file__))
    os.chdir(program_path)

    timee = time.clock()
    app = QApplication(sys.argv)
    appicon = QIcon(':/appicon16.png')
    appicon.addFile(':/appicon32.png')
    appicon.addFile(':/appicon64.png')
    app.setWindowIcon(appicon)
    settings = QSettings('config.ini', QSettings.IniFormat)
    set_trans(settings)

    # setup fonts
    titlefont = QFont()
    titlefont.fromString(settings.value('/Font/title'))
    ttfontm = QFontMetrics(titlefont)
    datefont = QFont()
    datefont.fromString(settings.value('/Font/datetime'))
    dfontm = QFontMetrics(datefont)
    textfont = QFont()  # WenQuanYi Micro Hei
    textfont.fromString(settings.value('/Font/text'))
    sysfont = app.font()
    defont = QFont('Microsoft YaHei', app.font().pointSize())
    defontm = QFontMetrics(defont)
    app.setFont(defont)

    try:
        socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socket.bind(('127.0.0.1', 5002))
    except OSError:
        logging.warning('already running,exit')
        msgbox = QMessageBox()
        msgbox.setText(qApp.translate('FailStart',
                                      'Hazama is already running'))
        msgbox.setWindowTitle('Hazama')
        msgbox.exec_()
        sys.exit()

    logging.basicConfig(level=logging.DEBUG)
    dbpath = settings.value('/Main/dbpath', 'nikkichou.db')
    nikki = Nikki(dbpath)
    logging.info(str(nikki))

    main = Main()
    main.show()
    logging.debug('startup take %s seconds' % round(time.clock()-timee,3))
    if int(settings.value('Main/backup', 1)): backupcheck(dbpath)
    sys.exit(app.exec_())
