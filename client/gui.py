#coding=utf-8
import sys
import datetime
import dateutil.parser
import logging
from collections import OrderedDict
from copy import deepcopy
from app import Client
from gi.repository import Gtk, Gdk, Gio, GLib, GObject

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(funcName)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# TODO look for example at the project sta Treealigner on ow to separate the ui
# and the logic

css = """
.error {
    background-color: #8B0000;
}
.warning {
    background-color: #FF8C00;
}
.info {
    background-color: #BCEE68;
}

@binding-set gtk-vi-text-view
{
    bind "F9" { "toggle-pane" ()};
}
"""

style_provider = Gtk.CssProvider()
style_provider.load_from_data(css)

Gtk.StyleContext.add_provider_for_screen(
    Gdk.Screen.get_default(),
    style_provider,
    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
)

DATE = '%d.%m.%Y'
DATETIME = '%d.%m.%Y-%H:%M:%S'
ISSUE_COLOR = Gdk.RGBA(0.5,0.5,0.5)

data_model = OrderedDict((
    ('date',{'name':'Durchführungsdatum',
            'from_view':lambda x:datetime.datetime.strftime(
                dateutil.parser.parse(x,dayfirst=True),DATE),
             'editable':True}),
    ('client',{'name':'Auftraggeber','editable':True}),
    ('amount',{'name':'Betrag','from_view':float,'to_view':str,'editable':True}),
    ('account',{'name':'Konto','editable':True}),
    ('category',{'name':'Kategorie','editable':True}),
    ('comment',{'name':'Kommentar','editable':True}),
    ('tags',{'name':'Tags',
            'to_view':lambda x:', '.join(x),
            'from_view':lambda x:x.split(',') if ',' in x else x.split(),
             'editable':True}),
    ('_edit_time',{'name':'bearbeitet','editable':False}),
    ('_edit_by',{'name':'bearbeitet von','editable':False}),
    ('_id',{'name':'id','editable':False}),
))

def make_search_start_end(text,from_view=None):
    if '~' in text:
        start,end = text.split('~',1)
        if from_view:
            if start:
                start = from_view(start)
            if end:
                end = from_view(end)
        if start and end:
            return {'$gte':start,'$lt':end}
        elif start:
            return {'$gte':start}
        elif end:
            return {'$lt':end}
    else:
        if from_view:
            text = from_view(text)
        return text

def handle_errors(infolabel,infobar,resp):
    if 200 <= resp[0] and resp[0] <= 300:
        return resp[1]
    else:
        info = resp[1].get('message','')
        infolabel.set_text(info)
        infobar.set_message_type(Gtk.MessageType.WARNING)

class BaseWidget(Gtk.Box):
    def __init__(self,*args):
        super(Gtk.Box,self).__init__(orientation=Gtk.Orientation.VERTICAL,spacing=5)
        self.infobar = Gtk.InfoBar()
        self.infolabel = Gtk.Label()
        self.infobar.get_content_area().add(self.infolabel)
        for arg in args:
            self.add(arg)
        self.add(self.infobar)

    def handle_errors(self,(status,resp)):
        if 200 <= status and status <= 300:
            return resp
        else:
            info = resp.get('message','')
            self.infolabel.set_text(info)
            self.infobar.set_message_type(Gtk.MessageType.WARNING)

class CellRendererAutoComplete(Gtk.CellRendererText):
    # http://stackoverflow.com/a/13769663/1607448
    """ Text entry cell which accepts a Gtk.EntryCompletion object """

    __gtype_name__ = 'CellRendererAutoComplete'

    def __init__(self, liststore,key):
        super(CellRendererAutoComplete,self).__init__()
        self.key = key
        if isinstance(liststore,Gtk.ListStore):
            self.completion = Gtk.EntryCompletion()
            self.completion.set_model(liststore)
            self.completion.set_text_column(0)

        else:
            raise Exception('must be of type Gtk.ListStore, got %s'%type(liststore))


    def do_start_editing(
               self, event, treeview, path, background_area, cell_area, flags):
        if not self.get_property('editable'):
            return
        entry = Gtk.Entry()
        entry.set_text(treeview.get_model()[path][0].get(self.key,''))
        entry.set_completion(self.completion)
        entry.connect('editing-done', self.editing_done, path)
        entry.show()
        entry.grab_focus()
        return entry

    def editing_done(self,entry,path):
        self.emit('edited', path, entry.get_text())

class DictTreeView(Gtk.TreeView):
    __gsignals__ = {
            'edited': (GObject.SIGNAL_RUN_LAST, None,(object,object))
        }

    def __init__(self,liststore):
        super(DictTreeView,self).__init__(liststore)
        self.columns = {}

    def add_column(self,name,key,liststore=None,
                   editable=True,from_view=None,to_view=None):
        if not liststore:
            renderer = Gtk.CellRendererText()
        else:
            renderer = CellRendererAutoComplete(liststore,key)
        renderer.set_property("editable", editable)
        self.columns[key] = column = Gtk.TreeViewColumn(name,renderer)
        column.set_resizable(True)
        column.set_reorderable(True)
        column.set_cell_data_func(renderer,self.dict_cell_data_func,(0,key,to_view))
        if editable:
            renderer.connect('edited',self.on_cells_edited,key,from_view)
        super(DictTreeView,self).append_column(column)

    @staticmethod
    def dict_cell_data_func(column, cellrenderer, model, iterator, data):
        # http://faq.pygtk.org/index.py?req=edit&file=faq13.029.htp
        value = model.get_value(iterator, data[0]).get(data[1],'')
        status = model.get_value(iterator, data[0]).get('status','')
        if status:
            cellrenderer.set_property("background-rgba", ISSUE_COLOR)
            cellrenderer.set_property("background-set",True)
        else:
            cellrenderer.set_property("background-set",False)
        try:
            text = data[2](value) if data[2] else str(value)
            cellrenderer.set_property("text", text)
        except:
            logger.error('failed to format {0}'.format(value))

    def on_cells_edited(self,widget,path,text,key,from_view=None):
        try:
            value = from_view(text) if from_view else text
            if self.get_model()[path][0].get(key) != value:
                self.get_model()[path][0][key] = value
                self.emit('edited',path,key)
        except:
            logger.error('failed to process {0}'.format(text))

class FilterWindow(Gtk.ScrolledWindow):
    def __init__(self,app):
        super(FilterWindow,self).__init__()
        treeview = DictTreeView(app.liststore_search)
        treeview.connect('edited',app.on_edited)
        treeview.set_vexpand(True)
        treeview.set_hexpand(True)

        for key,model in data_model.items():
            treeview.add_column(
                model['name'],key,from_view=model.get('from_view'),
                to_view=model.get('to_view'),editable=model['editable'],
                liststore=getattr(app,'liststore_%s'%key,None)
            )

        treeview.add_column('Status','status',editable=False)
        self.add(treeview)

class FilterWidget(Gtk.Box):
    def __init__(self,app):
        super(FilterWidget,self).__init__(orientation=Gtk.Orientation.VERTICAL,spacing=5)

        for key,model in data_model.items():
            self.add_entry(
                key,model['name'],
                liststore=getattr(app,'liststore_%s'%key,None),
            )

    def add_entry(self,key,labeltext,liststore=None):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        entry = Gtk.Entry(xalign=0)
        label = Gtk.Label(labeltext, xalign=0)
        label.set_margin_left(10)
        if liststore:
            completion = Gtk.EntryCompletion()
            completion.set_model(liststore)
            completion.set_text_column(0)
            entry.set_completion(completion)
        vbox.pack_start(label, True, True, 0)
        vbox.pack_start(entry, True, True, 0)
        setattr(self,'entry_%s'%key,entry)
        self.add(vbox)

    @property
    def data(self):
        data = {}
        for key,model in data_model.items():
            value = getattr(self,'entry_%s'%key).get_text()
            if value:
                try:
                    data[key] = make_search_start_end(
                        value,model.get('from_view',None))
                except:
                    logger.error('couldn\'t process {0}'.format(value))
        return data

class TransactionWidget(BaseWidget):
    def __init__(self,app):
        super(TransactionWidget,self).__init__()
        self.app = app

        # date
        self.add(self.add_entry('date',data_model['date']['name']))

        # splits
        self.liststore = Gtk.ListStore(object)
        treeview = DictTreeView(self.liststore)
        treeview.connect('edited',self.on_edited)
        #treeview.set_activate_on_single_click(True)

        for key in ('amount','category','comment'):
            model = data_model[key]
            treeview.add_column(
                model['name'],key,from_view=model.get('from_view'),
                to_view=model.get('to_view'),editable=model['editable'],
                liststore=getattr(app,'liststore_%s'%key,None)
            )

        self.add(treeview)

        # all other entries
        for key in ('client','account','tags','comment'):
            model = data_model[key]
            self.add(self.add_entry(
                key,model['name'],
                liststore=getattr(app,'liststore_%s'%key,None)
            ))

        # enter
        button= Gtk.Button('Enter')
        button.connect('clicked',self.on_entered)
        self.add(button)

        self.set_initial_values()
        self.show_all()

    def add_entry(self,key,labeltext,liststore=None):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        entry = Gtk.Entry(xalign=0)
        label = Gtk.Label(labeltext, xalign=0)
        if liststore:
            completion = Gtk.EntryCompletion()
            completion.set_model(liststore)
            completion.set_text_column(0)
            entry.set_completion(completion)
        vbox.pack_start(label, True, True, 0)
        vbox.pack_start(entry, True, True, 0)
        setattr(self,'entry_%s'%key,entry)
        return vbox

    def on_edited(self,store,path,key):
        self._remove_row(path)
        self._apend_row()

    def set_initial_values(self):
        self.entry_date.set_text(
            datetime.datetime.strftime(datetime.datetime.now(),DATE))
        self.liststore.clear()
        self.liststore.append([{'amount':0.0,'category':'','comment':''}])
        self.entry_client.set_text('')
        self.entry_account.set_text('')
        self.entry_comment.set_text('')
        self.entry_tags.set_text('')
        self.infolabel.set_text('')
        self.infobar.set_message_type(Gtk.MessageType.INFO)

    def _apend_row(self):
        row = self.liststore[-1][0]
        if row['amount'] or row['category'] or row['comment']:
            self.liststore.append([{'amount':0.0,'category':'','comment':''}])

    def _remove_row(self,path):
        if int(path) < len(self.liststore)-1:
            row = self.liststore[path][0]
            if row['amount'] == 0 and row['category'] == '' and row['comment'] == '':
                self.liststore.remove(self.liststore._getiter(path))

    def on_entered(self,button):
        d = {}
        d['date'] = self.entry_date.get_text()
        d['client'] = self.entry_client.get_text()
        d['tags'] = self.entry_tags.get_text().split(',')
        d['account'] = self.entry_account.get_text()
        d['comment'] = self.entry_comment.get_text()
        docs = []
        for i in range(len(self.liststore)-1):
            row = self.liststore[i][0]
            doc = deepcopy(d)
            doc['amount'] = row['amount']
            doc['category'] = row['category']
            if doc['comment'] and row['comment']:
                doc['comment'] = ', '.join(doc['comment'],row['comment'])
            else:
                doc['comment'] = max(row['comment'],doc['comment'])
            docs.append(doc)
        if not docs:
            docs = d

        resp = self.handle_errors(self.app.client.post('',docs))

        if resp and resp['status'] == 'OK':
            self.set_initial_values()
        elif resp:
            issues = {}
            for item in resp['_items']:
                if item['status'] == 'OK':
                    continue
                issues.update(item['issues'])
            self.infolabel.set_text(', '.join('%s: %s'%(k,v) for k,v in issues.items()))
            self.infobar.set_message_type(Gtk.MessageType.WARNING)


class StatsWidget(BaseWidget):
    def __init__(self,app):
        super(StatsWidget,self).__init__(self.create_toolbar())
        self.app = app
        hbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        keys = Gtk.ListStore(str)
        for key in ('client','account','category'):
            keys.append([key])
        hbox.add(self.add_entry('name','Name',box=Gtk.HBox()))
        hbox.add(self.add_entry('keys','Keys',liststore=keys,box=Gtk.HBox()))
        hbox.add(self.add_entry('timestep','Zeitschritt',liststore=keys,box=Gtk.HBox()))
        self.pane = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.widget_search = FilterWidget(app)
        hbox.add(self.widget_search)
        button = Gtk.Button('New')
        hbox.add(button)
        self.pane.pack1(hbox,shrink=False)
        self.notebook = notebook = Gtk.Notebook()
        notebook.set_scrollable(True)
        self.pane.add2(notebook)
        self.add(self.pane)
        self.add_tab()

    def create_toolbar(self):
        # a toolbar
        toolbar = Gtk.Toolbar(hexpand=True)

        # which is the primary toolbar of the application
        toolbar.get_style_context().add_class(Gtk.STYLE_CLASS_PRIMARY_TOOLBAR);

        button = Gtk.ToolButton.new_from_stock(Gtk.STOCK_ADD)
        button.set_is_important(True)
        toolbar.add(button)
        button.connect('clicked',self.add_tab)

        button = Gtk.ToolButton.new_from_stock(Gtk.STOCK_SAVE)
        button.set_is_important(True)
        toolbar.add(button)

        button = Gtk.ToolButton.new_from_stock(Gtk.STOCK_REFRESH)
        button.set_is_important(True)
        toolbar.add(button)

        button = Gtk.ToolButton.new_from_stock(Gtk.STOCK_FIND)
        button.set_is_important(True)
        toolbar.add(button)

        return toolbar

    def add_tab(self,*args):
        import json
        data = json.loads(open('/home/martin/devel/python/accounting/testdata.txt','r').read())
        self.notebook.append_page(StatsResultsWidget(self.app,data),Gtk.Label('hello'))
        self.notebook.show_all()

    def add_entry(self,key,labeltext,liststore=None,box=None):
        if not box:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        entry = Gtk.Entry(xalign=0)
        entry.set_hexpand(True)
        label = Gtk.Label(labeltext, xalign=0)
        label.set_margin_left(10)
        if liststore:
            completion = Gtk.EntryCompletion()
            completion.set_model(liststore)
            completion.set_text_column(0)
            entry.set_completion(completion)
        box.pack_start(label, True, True, 0)
        box.pack_start(entry, True, True, 0)
        setattr(self,'entry_%s'%key,entry)
        return box

class StatsResultsWidget(Gtk.ScrolledWindow):
    def __init__(self,app,data):
        super(StatsResultsWidget,self).__init__()
        treestore = treestore = Gtk.TreeStore(object)
        treeview = DictTreeView(treestore)

        times = {}
        months = set()
        for doc in data:
            parent = treestore.append(None,[{'_id':doc['_id']['account']}])
            amounts = zip(doc['month'],doc['amount'],doc['client'])
            months.update(doc['month'])
            for client in set(doc['client']):
                newdoc = {m:a for m,a,c in amounts if c == client}
                newdoc['client'] = client
                child = treestore.append(parent,[newdoc])

        treeview.add_column('category','_id',editable=False)
        treeview.add_column('client','client',editable=False)
        for key in months:
            treeview.add_column(key,key,editable=False)

        self.add(treeview)

class StatsTab(Gtk.Box):
    def __init__(self,app):
        super(StatsTab,self).__init__(orientation=Gtk.Orientation.VERTICAL)

        hbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        keys = Gtk.ListStore(str)
        for key in ('client','account','category'):
            keys.append([key])
        hbox.add(self.add_entry('keys','Keys',liststore=keys,box=Gtk.HBox()))
        hbox.add(self.add_entry('timestep','Zeitschritt',liststore=keys,box=Gtk.HBox()))
        self.add(hbox)
        self.pane = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.widget_search = FilterWidget(app)
        self.pane.pack1(self.widget_search,shrink=False)
        import json
        data = json.loads(open('/home/martin/devel/python/accounting/testdata.txt','r').read())
        self.pane.add2(StatsResultsWidget(app,data))
        self.add(self.pane)

    def add_entry(self,key,labeltext,liststore=None,box=None):
        if not box:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        entry = Gtk.Entry(xalign=0)
        label = Gtk.Label(labeltext, xalign=0)
        label.set_margin_left(10)
        if liststore:
            completion = Gtk.EntryCompletion()
            completion.set_model(liststore)
            completion.set_text_column(0)
            entry.set_completion(completion)
        box.pack_start(label, True, True, 0)
        box.pack_start(entry, True, True, 0)
        setattr(self,'entry_%s'%key,entry)
        return box



class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super(MainWindow,self).__init__(title="Accounter", application=app)
        self._search_window_visible = True
        self.set_default_size(1400, 800)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5)
        box.add(self.create_toolbar())
        box.add(app.infobar)
        self.pane = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.widget_search = FilterWidget(app)
        self.pane.pack1(self.widget_search,shrink=False)
        self.pane.add2(FilterWindow(app))
        box.add(self.pane)
        self.add(box)

    def toggle_search(self,*args):
        if self._search_window_visible:
            self.widget_search.set_visible(False)
            self._search_window_visible = False
        else:
            self.pane.set_position(self._pane_position_old)
            self.widget_search.set_visible(True)
            self._search_window_visible = True


    # a method to create the toolbar
    def create_toolbar(self):
        # a toolbar
        toolbar = Gtk.Toolbar(hexpand=True)

        # which is the primary toolbar of the application
        toolbar.get_style_context().add_class(Gtk.STYLE_CLASS_PRIMARY_TOOLBAR);

        button = Gtk.ToolButton.new_from_stock(Gtk.STOCK_ADD)
        button.set_is_important(True)
        toolbar.add(button)
        button.set_action_name("app.add")

        button = Gtk.ToolButton.new_from_stock(Gtk.STOCK_SAVE)
        button.set_is_important(True)
        toolbar.add(button)
        button.set_action_name("app.save")

        button = Gtk.ToolButton.new_from_stock(Gtk.STOCK_REFRESH)
        button.set_is_important(True)
        toolbar.add(button)
        button.set_action_name("app.update")

        button = Gtk.ToolButton.new_from_stock(Gtk.STOCK_FIND)
        button.set_is_important(True)
        toolbar.add(button)
        button.set_action_name("app.search")

        button = Gtk.ToolButton.new_from_stock(Gtk.STOCK_FIND)
        button.set_is_important(True)
        toolbar.add(button)
        button.set_action_name("app.stats")

        button = Gtk.ToolButton.new_from_stock(Gtk.STOCK_DIALOG_AUTHENTICATION)
        button.set_is_important(True)
        toolbar.add(button)
        button.set_action_name("app.login")

        return toolbar

class LoginWidget(BaseWidget):
    def __init__(self,app):
        super(LoginWidget,self).__init__()
        topbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5)
        box.set_size_request(200,150)
        box.set_margin_left(50)
        box.set_margin_right(50)
        # username
        self.username_entry = Gtk.Entry()
        self.username_entry.set_placeholder_text('username')
        box.add(self.username_entry)
        # password
        self.password_entry = Gtk.Entry()
        self.password_entry.set_placeholder_text('password')
        self.password_entry.set_visibility(False)
        box.add(self.password_entry)
        # sign in
        button = Gtk.Button('Sign in')
        button.set_size_request(200,50)
        button.connect('clicked',self.login_callback,app)
        box.add(button)
        topbox.add(box)
        self.add(topbox)
        self.show_all()

    def login_callback(self,button,app):
        resp = self.handle_errors(
            app.client.signin(
                self.username_entry.get_text(),
                self.password_entry.get_text())
        )
        if resp:
            self.get_parent().close()

class Application(Gtk.Application):
    def __init__(self):
        super(Application,self).__init__()
        self.client = Client()
        self.liststore_search = Gtk.ListStore(object)
        self.search_data = {}
        self.create_completion_liststores()
        self.infolabel = Gtk.Label()
        self.infobar = Gtk.InfoBar()
        self._history = []
        content = self.infobar.get_content_area()
        content.add(self.infolabel)
        self._edited = False
        self._edited_docs = {}
        self._windows = {
            'transaction':{
                'widgetclass':TransactionWidget,
                'title':'Add Transaction'},
            'login':{
                'widgetclass':LoginWidget,
                'title':'Sign in'},
            'stats':{
                'widgetclass':StatsWidget,
                'title':'Statistics'},
                         }

    def create_completion_liststores(self):
        for key in ('account','client','tags','category'):
            self.add_completition_liststore(key)

    def add_completition_liststore(self,key):
        liststore = Gtk.ListStore(str)
        completion = Gtk.EntryCompletion()
        completion.set_model(liststore)
        completion.set_text_column(0)
        setattr(self,'liststore_%s'%key,liststore)

    def do_activate(self):
        self.window_main = MainWindow(self)
        Gtk.StyleContext.add_provider(
            self.window_main.get_style_context(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_USER
        )
        self.window_main.show_all()
        self.update_callback()
        #update_task = GLib.timeout_add_seconds(10,self.do_update)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        # new
        action = Gio.SimpleAction.new("add", None)
        action.connect("activate", self.show_window_generic,'transaction')
        app.add_action(action)

        # update
        self.update_action = action = Gio.SimpleAction.new("update", None)
        action.connect("activate", self.update_callback)
        app.add_action(action)

        # save
        action = Gio.SimpleAction.new("save", None)
        action.connect("activate", self.save_callback)
        app.add_action(action)

        # login
        action = Gio.SimpleAction.new("login", None)
        action.connect("activate", self.show_window_generic,'login')
        app.add_action(action)

        # search
        action = Gio.SimpleAction.new("search", None)
        action.connect("activate", self.search_callback)
        app.add_action(action)

        # search
        action = Gio.SimpleAction.new("stats", None)
        action.connect("activate", self.show_window_generic,'stats')
        app.add_action(action)

    def show_window_generic(self,*args):
        def hide_window_generic(window,event):
            window.set_visible(False)
            # causes Gtk-CRITICAL messages, shouldn't be needed anyways
            #window.set_sensitive(False)
            return True
        windowname = args[-1]
        if 'window' in self._windows[windowname]:
            window = self._windows[windowname]['window']
            window.set_sensitive(True)
            window.set_visible(True)
            window.present()
        else:
            window = Gtk.Window(title=self._windows[windowname]['title'])
            widget = self._windows[windowname]['widgetclass'](self)
            window.add(widget)
            window.connect('delete-event',hide_window_generic)
            window.show_all()
            self._windows[windowname]['window'] = window
            self._windows[windowname]['widget'] = widget

    def update_callback(self,*args):
        if not self._edited:
            resp = handle_errors(
                self.infolabel,self.infobar,self.client.post(
                    'search/',self.window_main.widget_search.data))
            if resp:
                self.update_liststore_search(resp['_items'])
            resp = handle_errors(
                self.infolabel,self.infobar,self.client.get('accounts/'))
            if resp:
                self.update_liststore_str_generic(
                    self.liststore_account,resp['_items'])
            resp = handle_errors(
                self.infolabel,self.infobar,self.client.get('clients/'))
            if resp:
                self.update_liststore_str_generic(
                    self.liststore_client,resp['_items'])
            resp = handle_errors(
                self.infolabel,self.infobar,self.client.get('categories/'))
            if resp:
                self.update_liststore_str_generic(
                    self.liststore_category,resp['_items'])
            # it is important that the function returns True, otherwise it will
            # wait infinitely if used in Gobject scheduled timeout
            return True

    def update_liststore_str_generic(self,liststore,items):
        liststore.clear()
        for item in items:
            liststore.append([item])

    def update_liststore_search(self,items):
        length = len(self.liststore_search)
        for i in range(min(length,len(items))):
            self.liststore_search.set_row(self.liststore_search._getiter(i),[items[i]])
        if len(items) > length:
            for doc in items[length:]:
                self.liststore_search.append([doc])
        else:
            for i in reversed(range(length)[len(items):]):
                self.liststore_search.remove(self.liststore_search._getiter(i))

    def on_edited(self,treeview,path ,key):
        self._edited = True
        self.infolabel.set_text('unsaved changes')
        self.infobar.set_message_type(Gtk.MessageType.INFO)
        self.update_action.set_enabled(False)
        value = treeview.get_model()[path][0].get(key)
        change = {'path':path,'key':key,'value':value}
        self._history.append(change)
        _id = treeview.get_model()[path][0]['_id']
        self._edited_docs[_id] = path

    def save_callback(self,*args):
        data = []
        for _id,path in self._edited_docs.items():
            doc = self.liststore_search[path][0]
            if 'status' in doc:
                doc.pop('status')
            data.append(doc)
        if not data:
            return
        resp = handle_errors(
            self.infolabel,self.infobar,self.client.post('',data))
        if resp and resp['status'] == 'OK':
            self._edited_docs.clear()
            self._edited = False
            self.infolabel.set_text('')
            self.infobar.set_message_type(Gtk.MessageType.INFO)
            self.update_action.set_enabled(True)
        else:
            self.infolabel.set_text('there where errors')
            self.infobar.set_message_type(Gtk.MessageType.WARNING)
            for doc in resp['_items']:
                _id = doc['_item']['_id']
                if doc['status'] == 'OK':
                    self._edited_docs.pop(_id)
                else:
                    path = self._edited_docs[_id]
                    issues = ', '.join(['%s: %s'%(k,v) for k,v in doc['issues'].items()])
                    self.liststore_search[path][0]['status'] = issues


    def search_callback(self,*args):
        self.window_main.toggle_search()


if __name__ == '__main__':
    app = Application()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)

