from PySide.QtGui import *
from PySide.QtCore import *
from itertools import chain


cellLen = 9
cellSpacing = 2
monthSpacingX = 14
monthSpacingY = 20
cellColors = ((255, 255, 255), (255, 243, 208),
              (255, 221, 117), (255, 202, 40))

_cellDis = cellLen + cellSpacing
_monthDisX = _cellDis * 6 + cellLen + monthSpacingX
_monthDisY = _cellDis * 4 + cellLen + monthSpacingY


class HeatMap(QWidget):
    def __init__(self, *args, **kwargs):
        super(HeatMap, self).__init__(*args, **kwargs)
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        self.bar = QFrame(self, objectName='heatMapBar')
        barLayout = QHBoxLayout(self.bar)
        barLayout.setContentsMargins(0, 0, 0, 0)
        barLayout.setSpacing(3)
        # setup buttons and menu
        self.view = HeatMapView(self, font=self.font(), objectName='heatMapView')
        self.yearBtn = QPushButton(str(self.view.year), self,
                                   objectName='heatMapBtn')
        self.yearBtn.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.yearBtn.setFont(self.font())
        self.yearBtn.clicked.connect(self.yearBtnAct)
        self.yearMenu = QMenu(self, objectName='heatMapMenu')
        self._yearActGroup = QActionGroup(self.yearMenu)
        self.setupYearMenu()
        size = QSize(16, 16)
        preBtn = QToolButton(self, icon=QIcon(':/heatmap/arrow-left.png'),
                             clicked=self.yearPre, iconSize=size)
        nextBtn = QToolButton(self, icon=QIcon(':/heatmap/arrow-right.png'),
                              clicked=self.yearNext, iconSize=size)
        # setup color sample
        self.colorView = ColorSampleView(self, cellLen=11)
        # always bigger than sizeHint even policy is Maximum, so painful. use fixed
        self.colorView.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.colorView.setFixedSize(preBtn.sizeHint().width()*2 + barLayout.spacing(), 12)
        self.colorView.setupMap()
        barLayout.addWidget(preBtn, Qt.AlignVCenter)
        barLayout.addWidget(nextBtn, Qt.AlignVCenter)
        barLayout.addSpacerItem(QSpacerItem(30, 1, QSizePolicy.Expanding, QSizePolicy.Fixed))
        barLayout.addWidget(self.yearBtn)
        barLayout.addSpacerItem(QSpacerItem(30, 1, QSizePolicy.Expanding, QSizePolicy.Fixed))
        barLayout.addWidget(self.colorView)
        layout.addWidget(self.bar)
        layout.addWidget(self.view)

    def setupYearMenu(self):
        group, menu, curtYear = self._yearActGroup, self.yearMenu, self.view.year
        menu.clear()
        for y in chain([curtYear-10, curtYear-7], range(curtYear-4, curtYear)):
            menu.addAction(QAction(str(y), group, triggered=self.yearMenuAct))
        curtYearAc = QAction(str(curtYear), group)
        curtYearAc.setDisabled(True)
        curtYearAc.setCheckable(True)
        curtYearAc.setChecked(True)
        menu.addAction(curtYearAc)
        for y in chain(range(curtYear+1, curtYear+5), [curtYear+7, curtYear+10]):
            menu.addAction(QAction(str(y), group, triggered=self.yearMenuAct))

    def setColorFunc(self, f):
        self.view.cellColorFunc = f

    def yearPre(self):
        self.view.year -= 1
        self.yearBtn.setText(str(self.view.year))
        self.setupYearMenu()

    def yearNext(self):
        self.view.year += 1
        self.yearBtn.setText(str(self.view.year))
        self.setupYearMenu()

    def yearMenuAct(self):
        yearStr = self.sender().text()
        self.view.year = int(yearStr)
        self.yearBtn.setText(yearStr)
        self.setupYearMenu()

    def yearBtnAct(self):
        """Popup menu manually to avoid indicator in YearButton"""
        self.yearMenu.exec_(self.yearBtn.mapToGlobal(
            QPoint(0, self.yearBtn.height())))

    def showEvent(self, event):
        # must call setupMap after style polished
        self.view.setupMap()
        event.accept()


class HeatMapView(QGraphicsView):
    cellColorFunc = lambda *args: Qt.white  # dummy
    nameFontPx = 9

    def __init__(self, *args, **kwargs):
        super(HeatMapView, self).__init__(*args, **kwargs)
        self.yearVal = QDate.currentDate().year()
        self.cellBorderColorVal = Qt.lightGray
        self.scene = QGraphicsScene(self)
        f = self.font()
        f.setPixelSize(self.nameFontPx)
        self.nameH = QFontMetrics(f).height()
        self.setFont(f)
        self.scene.setSceneRect(0, 0, _monthDisX*3-monthSpacingX,
                                _monthDisY*4-monthSpacingY+self.nameH)
        self.setScene(self.scene)

    def setupMap(self):
        locale, date, font, nameH = QLocale(), QDate(), self.font(), self.nameH
        for m in range(12):
            date.setDate(self.year, m+1, 1)
            # cells. 7 days per line, index of line: (d//7)
            monthItems = [QGraphicsRectItem(_cellDis*d-(d//7)*_cellDis*7, _cellDis*(d//7),
                                            cellLen, cellLen)
                          for d in range(date.daysInMonth())]
            for (d, item) in enumerate(monthItems, 1):
                item.setPen(QPen(self.cellBorderColor))
                item.setBrush(self.cellColorFunc(self.year, m+1, d))
            monthGroup = self.scene.createItemGroup(monthItems)
            # 3 months per line
            x, y = _monthDisX*m-(m//3)*_monthDisX*3, _monthDisY*(m//3)
            monthGroup.setPos(x, y+nameH)
            # month name
            monthText = self.scene.addSimpleText(locale.toString(date, 'MMM'), font)
            monthText.setPen(self.palette().color(QPalette.WindowText))
            nameW = monthText.boundingRect().width()
            monthText.setPos(x+(_monthDisX-monthSpacingX-nameW)/2, y)

    def resizeEvent(self, event):
        self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def setCellBorderColor(self, color):
        self.cellBorderColorVal = color

    def getCellBorderColor(self):
        return self.cellBorderColorVal

    def getYear(self):
        return self.yearVal

    def setYear(self, year):
        self.yearVal = year
        self.scene.clear()
        self.setupMap()

    year = property(getYear, setYear)
    cellBorderColor = Property(QColor, getCellBorderColor, setCellBorderColor)


class ColorSampleView(QGraphicsView):
    def __init__(self, parent=None, cellLen=9):
        super(ColorSampleView, self).__init__(parent, objectName='heatMapSample',
                                              alignment=Qt.AlignRight)
        self.cellLen = cellLen
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(0, 0, cellLen*len(cellColors), cellLen)
        self.setScene(self.scene)

    def setupMap(self):
        for index, color in enumerate(cellColors):
            item = QGraphicsRectItem(self.cellLen*index, 0, self.cellLen, self.cellLen)
            item.setPen(QPen(Qt.darkGray))
            item.setBrush(QColor(*color))
            self.scene.addItem(item)


if __name__ == '__main__':
    app = QApplication([])
    v = HeatMap()
    v.show()
    app.exec_()
