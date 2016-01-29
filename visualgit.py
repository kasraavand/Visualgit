from subprocess import Popen, PIPE
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure
from pyqtgraph.Qt import QtGui, QtCore
from operator import itemgetter, attrgetter
from datetime import datetime
from itertools import izip
from collections import OrderedDict, defaultdict
import pyqtgraph as pg
import argparse
import time
import sys
import re

class DateAxis(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        """
        .. py:attribute:: tickStrings()

           :param values: 
           :type values: 
           :param scale: 
           :type scale: 
           :param spacing: 
           :type spacing: 
           :rtype: UNKNOWN

        .. note:: 

        .. todo:: 
        """
        strns = []
        rng = max(values)-min(values)
        #if rng < 120:
        #    return pg.AxisItem.tickStrings(self, values, scale, spacing)
        if rng < 3600*24:
            string = '%H:%M:%S'
            label1 = '%Y/%m %d -'
            label2 = ' %m %d, %Y'
        elif rng >= 3600*24 and rng < 3600*24*30:
            string = '%Y/%m/%d'
            label1 = '%Y/%m'
            label2 = '%m, %Y'
        elif rng >= 3600*24*30 and rng < 3600*24*30*24:
            string = '%Y/%m'
            label1 = '%Y -'
            label2 = ' %Y'
        elif rng >= 3600*24*30*24:
            string = '%Y'
            label1 = ''
            label2 = ''
        for x in values:
            try:
                strns.append(time.strftime(string, time.localtime(x)))
            except ValueError:  ## Windows can't handle dates before 1970
                strns.append('')
        try:
            label = time.strftime(label1, time.localtime(min(values)))+\
            time.strftime(label2, time.localtime(max(values)))
        except ValueError:
            label = ''
        #self.setLabel(text=label)
        return strns
class CustomViewBox(pg.ViewBox):
    def __init__(self, *args, **kwds):
        """
        .. py:attribute:: __init__()

           :rtype: UNKNOWN

        .. note:: 

        .. todo:: 
        """
        pg.ViewBox.__init__(self, *args, **kwds)
        self.setMouseMode(self.RectMode)
    ## reimplement right-click to zoom out
    def mouseClickEvent(self, ev):
        """
        .. py:attribute:: mouseClickEvent()

           :param ev: 
           :type ev: 
           :rtype: None

        .. note:: 

        .. todo:: 
        """
        if ev.button() == QtCore.Qt.RightButton:
            self.autoRange()
    def mouseDragEvent(self, ev):
        """
        .. py:attribute:: mouseDragEvent()


           :param ev: 
           :type ev: 
           :rtype: UNKNOWN

        .. note:: 

        .. todo:: 
        """
        if ev.button() == QtCore.Qt.RightButton:
            ev.ignore()
        else:
            pg.ViewBox.mouseDragEvent(self, ev)
class GitStatics(object):
    def __init__(self, *args, **kwargs):
        """
        .. py:attribute:: __init__()
         
           :rtype: UNKNOWN

        .. note:: 

        .. todo:: 
        """
        try:
            self.dbname = kwargs['dbname']
            self.host = kwargs['host']
            self.vb = kwargs['vb']
            self.axis = kwargs['axis']
            self.git_path = kwargs['git_path']
            self.branch_name = kwargs['branch_name']
            self.start_year = kwargs['start_year']
            self.args = kwargs['args']
            self.set_args()

        except KeyError as e:
            raise Exception("Please insert a correct argument name.\n{}".foramt(e))
        self.mongo_cursor = self.mongo_connector()
        self.output = self.get_log_info()
        self.collection_name = "log_info"
        self.branch_name = self.get_branch_name()
        self.tag_names = self.get_tag_names().split('\n')
        self.tag_extracter_regex = re.compile(
            r'(:?(?P<changed>(\d+)) files changed)?(:?, (?P<insertations>(\d+)) insertions\(\+\))?(?:, (?P<deletions>(\d+)) deletions\(-\))?')
    
    def set_args(self):
        attrs = attrgetter('B', 't', 'm', 'y', 'x', 'ct', 'dt', 'e', 'i', 's')(self.args)
        self.sub_branch_name, self.time_type, self.time_mode, self.y_axis_type, self.x_axis_type,\
        self.count_type, self.diff_type, self.excludes, self.includes, self.start_time = attrs
        try:
            self.start_time = int(self.start_time)
        except ValueError:
            raise Exception("Please enter a integer value for start_year (more than 0).")

    def get_branch_name(self):
        """
        .. py:attribute:: get_branch_name()

           :rtype: UNKNOWN

        .. note:: 

        .. todo:: 
        """
        command =  "git branch"
        P = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd=self.git_path,shell=True)
        output, err = P.communicate(b"Get the result of git log")
        if err:
            raise Exception("Invalid command")
        matched = re.search(r'\* (?:\(detached from )?(.*)\)?',output)
        try:
            return matched.group(1)
        except AttributeError:
            raise Exception("The result of git branch command is {}.\
             And it doesn't match with our proper format".format(matched))
        #return output
    def get_diff(self, commit_hash):
        """
        .. py:attribute:: get_diff()


           :param commit_hash: 
           :type commit_hash: 
           :rtype: UNKNOWN

        .. note:: 

        .. todo:: 
        """
        command = 'git show --numstat {}'.format(commit_hash)
        P = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd=self.git_path, shell=True)
        output, err = P.communicate(b"Get the result of git log")
        if err:
            return None
            #raise Exception("Invalid command")
        return output
    def get_tag_names(self):
        """
        .. py:attribute:: get_tag_names()


           :rtype: UNKNOWN

        .. note:: 

        .. todo:: 
        """
        command = 'git tag'
        P = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd=self.git_path, shell=True)
        output, err = P.communicate(b"Get the result of git log")
        return output
    def fileter_tag_names(self, filt):
        """
        .. py:attribute:: fileter_tag_names()


           :param filt: 
           :type filt: 
           :rtype: UNKNOWN

        .. note:: 

        .. todo:: 
        """
        if filt == "master":
            return [i for i in self.tag_names if i.isdigit()]
        elif filt == "invoice_on_demand":
            return [i for i in self.tag_names if i.startswith("invoice_on_demand")]
        elif filt == "invoice":
            return [i for i in self.tag_names if i.startswith("C_invoice")]
        elif filt == "c" or filt == "C":
            return [i for i in self.tag_names if re.match(r"C_\d+",i)]
    def tag_diff(self, tag_type):
        """
        .. py:attribute:: tag_diff()


           :param tag_type: 
           :type tag_type: 
           :rtype: UNKNOWN

        .. note:: 

        .. todo:: 
        """
        if tag_type == "master": 
            tags = self.fileter_tag_names("master")
        elif tag_type == "invoice_on_demand":
            tags = self.fileter_tag_names("invoice_on_demand")
        elif tag_type == "invoice":
            tags = self.fileter_tag_names("invoice")
        elif tag_type == "c" or tag_type == "C":
            tags = self.fileter_tag_names("C")
        else:
            raise Exception(
                "Tag name *{}* in not defined. You need to use one of the following names:\n\
                [master, invoice_on_demand, invoice, C]".format(tag_type)
                )
        try:
            tags = sorted(tags, key=lambda x: int(re.search(r'\d+$', x).group(0)))
        except AttributeError:
            raise Exception("AttributeError : There is an invalid tag name in {} tag.".format(tag_type))
        else:
            for pre,front in zip(tags, tags[1:]):
                command = "git diff {} {} --shortstat".format(pre, front)
                P = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd=self.git_path, shell=True)
                output, err = P.communicate(b"Get the result of git log")
                if err:
                    yield "{}_{}".format(pre, front), 0, 0, 0
                else:
                    try:
                        numbers_dict = self.tag_extracter_regex.search(output.strip()).groupdict()
                    except:
                        yield "{}_{}".format(pre, front), 0, 0, 0
                    else:
                        yield ["{}_{}".format(pre, front)] + [i if i else 0 for i in itemgetter(
                            "changed","insertations","deletions")(numbers_dict)]
    def get_log_info(self):
        """
        .. py:attribute:: get_log_info()

           :rtype: UNKNOWN

        .. note:: 

        .. todo:: 
        """
        if self.sub_branch_name:
            command = ['git','log', self.branch_name+'/'+sub_branch, "--pretty='%H\t%an\t%at\t%cn\t%ct\t%s'"]
        else:
            command = ['git','log', self.branch_name, "--pretty='%H\t%an\t%at\t%cn\t%ct\t%s'"]
        P = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd=self.git_path)
        output, err = P.communicate(b"Get the result of git log")
        if err:
            raise Exception("Invalid command.\n{}".format(err))
        return output

    def mongo_connector(self):
        """
        .. py:attribute:: mongo_connector()

           :rtype: UNKNOWN

        .. note:: 

        .. todo:: 
        """
        # Connect to mongoDB and return a connection object.
        try:
            c = MongoClient(host=self.host, port=27017)
        except ConnectionFailure, error:
            sys.stderr.write("Could not connect to MongoDB: {}".format(error))
        else:
            print "Connected successfully"
        return c[self.dbname]
    def insert_to_db(self, commit_hash, author_name, author_time, commiter_name, commiter_time, commit):
        """
        .. py:attribute:: insert_to_db()

           :param commit_hash: 
           :type commit_hash: 
           :param author_name: 
           :type author_name: 
           :param author_time: 
           :type author_time: 
           :param commiter_name: 
           :type commiter_name: 
           :param commiter_time: 
           :type commiter_time: 
           :param commit: 
           :type commit: 
           :rtype: UNKNOWN

        .. note:: 

        .. todo:: 
        """


    def indexer(self):
        """
        .. py:attribute:: indexer()

           :rtype: UNKNOWN

        .. note:: 

        .. todo:: 
        """
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
        """
        .. py:attribute:: run()

           :rtype: UNKNOWN

        .. note:: 

        .. todo:: 
        """
        revert_commits = {}
        all_lines = [line.split('\t') for line in self.output.split("\n")]
        try:
            for commit_hash, author_name, author_time, commiter_name, commiter_time, commit in all_lines:
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
        except (TypeError, ValueError) as e:
            pass
        self.indexer()

    def get_data(self):
        """
        .. py:attribute:: get_data()

           :rtype: UNKNOWN

        .. note:: 

        .. todo:: 
        """
        result = self.mongo_cursor[self.collection_name].find({}).sort([('author_time',1)])
        return result

    def extract_data_count(self):
        """
        .. py:attribute:: extract_data_count()

         
           :param timestamp: 
           :type boolean: 
           :rtype: UNKNOWN

        .. note:: 

        .. todo:: 
        """
        all_data = self.get_data()
        result_dict = defaultdict(list)
        if self.excludes:
            cond1 = lambda x: x not in self.excludes
        else:
            cond1 = lambda x: True
        if self.includes:
            cond2 = lambda x: x in self.include
        else:
            cond2 = lambda x: True
        for item in all_data:
            name = item['{}_name'.format(self.y_axis_type)]
            if not item['commit'].startswith('merge') and cond1(name) and cond2(name):
                try:
                    time = item[self.time_type] 
                except KeyError:
                    raise Exception("Please pass a correct time_type.([commiter_time, author_time])")
                else:
                    year = datetime.fromtimestamp(float(time)).year
                    month = datetime.fromtimestamp(float(time)).month
                if year >= self.start_time:
                    names_and_times = item['author_name'], item['author_time'], item['commiter_name'],item['commiter_time']
                    if self.count_type == 'name':
                        result_dict[name].append(names_and_times)
                    else:
                        result_dict[year, month, 1].append(names_and_times)
        return result_dict

    def extract_data_diff(self):
        """
        .. py:attribute:: extract_data_in_del()

           :param start_year: 
           :type start_year: 
           :rtype: UNKNOWN

        .. note:: 

        .. todo:: 
        """
        all_data = self.get_data()
        result_dict = defaultdict(list)
        if self.excludes:
            cond1 = lambda x: x in self.excludes
        else:
            cond1 = lambda x: True
        if self.includes:
            cond2 = lambda x: x in self.include
        else:
            cond2 = lambda x: True
        for item in all_data:
            name = item['{}_name'.format(self.y_axis_type)]
            if not item['commit'].startswith('merge') and cond1(name) and cond2(name):
                time = item[self.time_type] 
                try:
                    insert, delete = [sum(map(int,i)) for i in zip(*item['diff'])[:2]]
                except ValueError:
                    pass
                else:
                    year = datetime.fromtimestamp(float(time)).year
                    month = datetime.fromtimestamp(float(time)).month
                if year >= self.start_time:
                    names_and_times = insert, delete, time
                    result_dict[year,month,1].append(names_and_times)
        return result_dict



class Ploter(GitStatics):
    def __init__(self, *args, **kwargs):
        super(Ploter, self).__init__(*args, **kwargs)
        self.Epoch = datetime(1970, 1, 1, 0, 0)


    def main_ploter(self):
        if self.x_axis_type == 'count':
            self.cal_commit_count()
        else:
            self.cal_commit_diff()


    def veiw_commit(self, X, Y):
        """
        .. py:attribute:: veiw_custom()


           :param X: 
           :type X: 
           :param Y: 
           :type Y: 
           :rtype: UNKNOWN

        .. note:: 

        .. todo:: 
        """
        if isinstance(X[0],tuple):
            X = sorted([time.mktime(datetime(*i).timetuple()) for i in X])
        else:
            X = sorted(map(float, X))
        coords = zip(X, Y)
        app = pg.mkQApp()
        pw = pg.PlotWidget(viewBox=self.vb, axisItems={'bottom': self.axis}, enableMenu=False,
            title="PROJECT_NAME git log changes",clickable=True)
        def mouseMoved(pos):
                display_text = pg.TextItem(text='salooom',color=(176,23,31),anchor=pos)
                pw.addItem(display_text)
        pw.plot(X, Y, symbol='o')
        pw.show()
        pw.setWindowTitle('PROJECT_NAME Git Log: customPlot')
        r = pg.PolyLineROI([(0,0), (10,10)])
        pw.addItem(r)
        pw.scene().sigMouseClicked.connect(mouseMoved)
        if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
            QtGui.QApplication.instance().exec_()

    def cal_commit_diff(self):
        """
        .. py:attribute:: veiw_custom_monthly_diff()

           :rtype: UNKNOWN

        .. note:: 

        .. todo:: 
        """
        all_data = self.extract_data_diff()
        print self.diff_type
        if self.diff_type == 'insert':
            diff_index = 0
        else:
            diff_index = 1
        aggregated_result = zip(*[(time,sum(map(int,zip(*values)[diff_index]))) for time, values in all_data.iteritems()])
        self.veiw_commit(*aggregated_result)
    def cal_commit_count(self):
        """
        .. py:attribute:: veiw_custom_monthly_commit_count()

         
           :rtype: UNKNOWN

        .. note:: 

        .. todo:: 
        """
        all_data = self.extract_data_count()
        aggregated_result = zip(*[(k,len(v)) for k,v in all_data.iteritems()])
        self.veiw_commit(*aggregated_result)

    def quadruple_ploter(self, *args, **kwargs):

        try:
            lable1, lable2, lable3, lable4 = kwargs['lables']
            (x1, y1), (x2, y2), (x3, y3), (x4, y4) = kwargs['coordinates']
        except KeyError:
            raise Exception("Enter a correct key word argument(lables or coordinates).")

        win = pg.GraphicsWindow(title="PROJECT_NAME git statics")
        win.resize(800, 600)

        win.addLabel("Linked Views", colspan=2)
        win.nextRow()

        p1 = win.addPlot(x=x1, y=y1, name="Plot1", title=lable1, pen='b')
        p2 = win.addPlot(x=x2, y=y2, name="Plot2", title=label2, pen='y')
        p3 = win.addPlot(x=x3, y=y3, name="Plot3", title=lable3, row=2, col=0, pen='r')
        p4 = win.addPlot(
            x=x4,
            y=y4,
            name="Plot4",
            title=lable4,
            row=2,
            col=1,
            pen='g')

    def view_box(self, x, y, plot_type='', author_name=''):
        """
        .. py:attribute:: view_box()

           :param x: 
           :type x: 
           :param y: 
           :type y: 
           :param plot_type: 
           :type plot_type: 
           :param author_name: 
           :type author_name: 
           :rtype: UNKNOWN

        .. note:: 

        .. todo:: 
        """
        win = pg.GraphicsWindow(title="Basic plotting examples")
        win.resize(1000,600)
        win.setWindowTitle('PROJECT_NAME: LogPlotTest')
        xdict = OrderedDict(enumerate(['{}/{}'.format(i, j) for i,j in sorted(x)]))
        stringaxis = pg.AxisItem(orientation='bottom')
        stringaxis.setTicks([xdict.items()])
        p5 = win.addPlot(title="Commit {} per month \n author_name : {}".format(plot_type, author_name),axisItems={'bottom': stringaxis})
        p5.plot(
            xdict.keys(),
            y,
            pen='r',
            symbol='t',
            symbolPen=None,
            symbolSize=10,
            symbolBrush=(100, 100, 255, 50)
            )
        p5.setLabel('left', "Commit {}".format(plot_type), units='line')
        p5.setLabel('bottom', "Date", units='')
        if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
            QtGui.QApplication.instance().exec_()
    def tag_viewer(self, tag_name):
        """
        .. py:attribute:: tag_viewer()


           :param self: 
           :type self: 
           :param tag_name: 
           :type tag_name: 
           :rtype: UNKNOWN

        .. note:: 

        Example

        .. code-block:: python
        	

        .. todo:: 
        """
        win = pg.GraphicsWindow(title="Basic plotting examples")
        win.resize(1000,600)
        win.setWindowTitle('PROJECT_NAME: LogPlotTest')
        all_tag_names, file_changes, insertations, deletations = zip(*self.tag_diff(tag_name))
        xdict = dict(enumerate(all_tag_names))
        stringaxis = pg.AxisItem(orientation='bottom')
        stringaxis.setTicks([xdict.items()])
        p5 = win.addPlot(title="tag *{}* insertions".format(tag_name),axisItems={'bottom': stringaxis})
        p5.plot(
            xdict.keys(),
            map(float, insertations),
            pen='r',
            symbol='t',
            symbolPen=None,
            symbolSize=10,
            symbolBrush=(100, 100, 255, 50)
            )
        p5.setLabel('left', "Insertions", units='line')
        p5.setLabel('bottom', "Y Axis", units='s')
        if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
            QtGui.QApplication.instance().exec_()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Visualize PROJECT_NAME git-log results in any way you like ;)")
    # Adding arguments
    parser.add_argument("-B", "-branch_name", help="Based on your \
        available sub branches you can pass the those names to plot.", default='')
    parser.add_argument("-t", "-time_type", help="author_time or commiter_time", 
        choices=['author_time', 'commiter_time'], default='author_time')
    parser.add_argument("-m", "-time_mode", help="The format of time representation\
    can be one of the {yearly, monthly, per_commit}", choices=['yearly', 'monthly', 'per_commit'],
    default='monthly')
    parser.add_argument("-y", "-y_axis_type", help="Y axis type, which can be author or \
        commiter.", choices=['author', 'commiter'], default='author')
    parser.add_argument("-x", "-x_axis_type", help="X axis type (based on commit),\
        which can be count or diff", choices=['count','diff'],default='count')
    parser.add_argument("-dt", "-diff_type", help="Type of commit diff which can be,\
        insert or delete", choices=['insert','delete'], default='insert')
    parser.add_argument("-ct", "-count_type", help="categorize the counts based on date or \
        names", choices=['date','name'], default='date')
    parser.add_argument("-e", "-excludes", help="Names that must be exclude from log result", default='')
    parser.add_argument("-i", "-includes", help="Names that must be include to log result", default='')
    parser.add_argument("-s", "-start_time", help="The start time of ploting", default=2008)
    args = parser.parse_args()

    app = QtGui.QApplication(sys.argv)
    CVB = CustomViewBox()
    axis = DateAxis(orientation='bottom')
    PL = Ploter(
        host='localhost',
        dbname='GitStat',
        vb=CVB,
        axis=axis,
        args=args,
        git_path='/home/user_name/PROJECT_NAME',
        branch_name='ehsan/C',
        start_year = 2014)
    #PL.tag_viewer("invoice_on_demand")
    #PL.run()
    PL.main_ploter()
