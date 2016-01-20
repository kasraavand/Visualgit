from subprocess import Popen, PIPE
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure
from pyqtgraph.Qt import QtGui, QtCore
from datetime import datetime
from itertools import izip
import numpy as np
import pyqtgraph as pg
import time
import sys
import re

class DateAxis(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        strns = []
        rng = max(values)-min(values)
        #if rng < 120:
        #    return pg.AxisItem.tickStrings(self, values, scale, spacing)
        if rng < 3600*24:
            string = '%H:%M:%S'
            label1 = '%b %d -'
            label2 = ' %b %d, %Y'
        elif rng >= 3600*24 and rng < 3600*24*30:
            string = '%d'
            label1 = '%b - '
            label2 = '%b, %Y'
        elif rng >= 3600*24*30 and rng < 3600*24*30*24:
            string = '%b'
            label1 = '%Y -'
            label2 = ' %Y'
        elif rng >=3600*24*30*24:
            string = '%Y'
            label1 = ''
            label2 = ''
        for x in values:
            try:
                strns.append(time.strftime(string, time.localtime(x)))
            except ValueError:  ## Windows can't handle dates before 1970
                strns.append('')
        try:
            label = time.strftime(label1, time.localtime(min(values)))+time.strftime(label2, time.localtime(max(values)))
        except ValueError:
            label = ''
        #self.setLabel(text=label)
        return strns

class CustomViewBox(pg.ViewBox):
    def __init__(self, *args, **kwds):
        pg.ViewBox.__init__(self, *args, **kwds)
        self.setMouseMode(self.RectMode)
        
    ## reimplement right-click to zoom out
    def mouseClickEvent(self, ev):
        if ev.button() == QtCore.Qt.RightButton:
            self.autoRange()
            
    def mouseDragEvent(self, ev):
        if ev.button() == QtCore.Qt.RightButton:
            ev.ignore()
        else:
            pg.ViewBox.mouseDragEvent(self, ev)


class GitStatics(object):
    def __init__(self, *args, **kwargs):
        try:
            self.dbname = kwargs['dbname']
            self.host = kwargs['host']
            self.vb = kwargs['vb']
            self.axis = kwargs['axis']
        except KeyError:
            # Handling both keyErrors in one exception is not correct :-D
            raise Exception("Please insert the correct arguments")

        self.mongo_cursor = self.mongo_connector()
        self.output = self.get_log_info()
        self.collection_name = "log_info"
        self.branch_name = self.get_branch_name()


    def get_branch_name(self):
        command =  "git branch"
        P = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd='/git_directory',shell=True)
        output, err = P.communicate(b"Get the result of git log")
        if err:
            raise Exception("Invalid command")
        matched = re.search(r'\* \(detached from (.*)\)',output)
        try:
            return matched.group(1)
        except AttributeError:
            raise Exception("The result of `git branch command is {} . and it doesn't match with our proper format`")
        #return output

    def get_diff(self, commit_hash):
        command = 'git show --numstat {}'.format(commit_hash)
        P = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd='/git_directory', shell=True)
        output, err = P.communicate(b"Get the result of git log")
        if err:
            return None
            #raise Exception("Invalid command")
        return output
    
    def get_log_info(self):

        command = ['git','log', "--pretty='%H\t%an\t%at\t%cn\t%ct\t%B'"]
        P = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd='/git_directory')
        output, err = P.communicate(b"Get the result of git log")
        if err:
            raise Exception("Invalid command")
        return output

    def mongo_connector(self):
        # Connect to mongoDB and return a connection object.
        try:
            c = MongoClient(host=self.host, port=27017)
        except ConnectionFailure, error:
            sys.stderr.write("Could not connect to MongoDB: {}".format(error))
        else:
            print "Connected successfully"

        return c[self.dbname]

    def insert_to_db(self, commit_hash, author_name, author_time, commiter_name, commiter_time, commit):

        if commit.startswith('merge'):
            self.mongo_cursor[self.collection_name].insert(
                {
                    "branch_name": self.branch_name,
                    "commit_hash": commit_hash.strip("'"),
                    "author_name": author_name,
                    "author_time": author_time,
                    "commiter_name": commiter_name,
                    "commiter_time": commiter_time,
                    "commit": commit,

                }
            )
        else:
            diff = self.get_diff(commit_hash.strip("'"))
            all_diffs = re.findall(r'(?:\b(\d+)\b\t\b(\d+)\b)\t(.*)',diff)
            self.mongo_cursor[self.collection_name].insert(
                {
                    "branch_name": self.branch_name,
                    "commit_hash": commit_hash,
                    "author_name": author_name,
                    "author_time": author_time,
                    "commiter_name": commiter_name,
                    "commiter_time": commiter_time,
                    "commit": commit,
                    "diff": all_diffs

                }
            )


    def indexer(self):
        self.mongo_cursor[self.collection_name].ensure_index(
            [
                ('author_time', ASCENDING),
            ],)
        self.mongo_cursor[self.collection_name].ensure_index(
            [
                ('commiter_name', ASCENDING),
            ],)
        self.mongo_cursor[self.collection_name].ensure_index(
            [
                ('author_name', ASCENDING),
            ],)

    def run(self):
        self.indexer()
        for line in self.output.splitlines():
            attrs = line.split('\t')
            #print self.get_diff(attrs[0].strip("'"))
            #break
            try:
                self.insert_to_db(*attrs)
            except TypeError:
                pass
                

    def get_data(self):
        result = self.mongo_cursor[self.collection_name].find({}).sort([('author_time',1)])
        return result

    def create_plot(self, coord1, coord2, coord3, coord4):
        app = QtGui.QApplication([])

        win = pg.GraphicsWindow(title="pyqtgraph example: Linked Views")
        win.resize(1370,700)

        win.addLabel("Linked Views", colspan=2)
        win.nextRow()

        x3, y3 = coord3

        x3 = ['{}/{}'.format(datetime.fromtimestamp(float(i)).year,datetime.fromtimestamp(float(i)).month) for i in x3]
        xdict = dict(enumerate(x3))
        stringaxis = pg.AxisItem(orientation='bottom')
        stringaxis.setTicks([xdict.items()])
        ydict = dict(enumerate(y3))
        stringaxis2 = pg.AxisItem(orientation='right')
        stringaxis2.setTicks([ydict.items()])
        plot3 = win.addPlot(axisItems={'bottom': stringaxis,'right': stringaxis2},pen='y')
        curve4 = plot3.plot(xdict.keys(),ydict.keys(),pen='y')
        plot3.setLabel('left', "Label to test offset")

        if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
            QtGui.QApplication.instance().exec_()


    def view_box(self, x, y):

        app = QtGui.QApplication([])
        win = pg.GraphicsWindow(title="Basic plotting examples")
        win.resize(1000,600)
        win.setWindowTitle('pyqtgraph example: LogPlotTest')

        x = ['{}/{}'.format(datetime.fromtimestamp(float(i)).year,datetime.fromtimestamp(float(i)).month) for i in x]
        xdict = dict(enumerate(x))
        stringaxis = pg.AxisItem(orientation='bottom')
        stringaxis.setTicks([xdict.items()])

        p5 = win.addPlot(title="Scatter plot, axis labels, log scale",axisItems={'bottom': stringaxis})

        p5.plot(xdict.keys(), y, pen=None, symbol='t', symbolPen=None, symbolSize=10, symbolBrush=(100, 100, 255, 50))
        p5.setLabel('left', "Y Axis", units='A')
        p5.setLabel('bottom', "Y Axis", units='s')

        if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
            QtGui.QApplication.instance().exec_()

    def view_line(self, x, y, y2):
        app = QtGui.QApplication([])
        win = pg.GraphicsWindow(title="Basic plotting examples")
        win.resize(1000,600)
        win.setWindowTitle('pyqtgraph example: LogPlotTest')

        x = ['{}/{}'.format(datetime.fromtimestamp(float(i)).year,datetime.fromtimestamp(float(i)).month) for i in x]
        xdict = dict(enumerate(x))
        stringaxis = pg.AxisItem(orientation='bottom')
        stringaxis.setTicks([xdict.items()])

        p5 = win.addPlot(title="Scatter plot, axis labels, log scale",axisItems={'bottom': stringaxis})

        p5.plot(xdict.keys(), y, pen='r')
        #p5.plot(xdict.keys(), y2, pen='y')
        p5.setLabel('left', "Y Axis", units='A')
        p5.setLabel('bottom', "Y Axis", units='s')
        if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
            QtGui.QApplication.instance().exec_()

    def veiw_custom(self, times, inserts):
        coords = zip(times, inserts)

        app = pg.mkQApp()
        pw = pg.PlotWidget(viewBox=self.vb, axisItems={'bottom': self.axis}, enableMenu=False,
            title="Git log changes",clickable=True)

        def mouseMoved(pos):
                display_text = pw.TextItem(text='salooom',color=(176,23,31),anchor=pos)
                pw.addItem(display_text)
        pw.plot(times, inserts, symbol='o')
        pw.show()
        pw.setWindowTitle('Git Log: customPlot')

        r = pg.PolyLineROI([(0,0), (10, 10)])
        pw.addItem(r)
        pw.scene().sigMouseClicked.connect(mouseMoved)
        if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
            QtGui.QApplication.instance().exec_()

    def extract_data(self):
        all_data = self.get_data()
        for item in all_data:
            if not item['commit'].startswith('merge'):
                try:
                    insert, delete = [sum(map(int,i)) for i in zip(*item['diff'])[:2]]
                except ValueError:
                    pass
            yield item['commiter_name'], item['commiter_time'], insert, delete

    def graph_viewer(self):
        all_data = self.extract_data()
        names, times, inserts, deletes = map(list, izip(*all_data))
        #self.create_plot((names,inserts),(times,inserts),(times,names),(times,deletes))
        #self.view_box(times,inserts)
        #self.view_line(times,inserts,deletes)
        self.veiw_custom(map(float,times), inserts)

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    CVB = CustomViewBox()
    axis = DateAxis(orientation='bottom')
    GS = GitStatics(host='localhost', dbname='GitStat',vb=CVB,axis=axis)
    GS.graph_viewer()