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

liststore_clients = Gtk.ListStore(str)
liststore_clients.append(['martin'])


liststore_categories = Gtk.ListStore(str)
liststore_categories.append(['test'])

DATE = '%d.%m.%Y'
DATETIME = '%d.%m.%Y-%H:%M:%S'

data_model = OrderedDict((
    ('date',{'name':'Durchführungsdatum',
            'from_view':lambda x:datetime.datetime.strftime(
                dateutil.parser.parse(x),DATE),
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

def handle_errors(infolabel,infobar,resp):
    if resp[0] == 200:
        infolabel.set_text('')
        infobar.set_message_type(Gtk.MessageType.INFO)
        return resp[1] if resp[1] else True
    else:
        if 'issues' in resp[1]:
            info = ', '.join(['%s: %s'%(k,v) for k,v in resp[1]['issues'].items()])
            mtype = Gtk.MessageType.WARNING
        else:
            info = resp[1].get('message','')
            mtype = Gtk.MessageType.ERROR
        infolabel.set_text(info)
        infobar.set_message_type(mtype)

class CellRendererAutoComplete(Gtk.CellRendererText):
    # http://stackoverflow.com/a/13769663/1607448
    """ Text entry cell which accepts a Gtk.EntryCompletion object """

    __gtype_name__ = 'CellRendererAutoComplete'

    def __init__(self, liststore):
        super(self.__class__,self).__init__()
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
        super(self.__class__,self).__init__(liststore)

    def add_column(self,name,key,renderer=None,
                   editable=True,from_view=None,to_view=None):
        if not renderer:
            renderer = Gtk.CellRendererText()
        renderer.set_property("editable", editable)
        column = Gtk.TreeViewColumn(name,renderer)
        column.set_resizable(True)
        column.set_reorderable(True)
        column.set_cell_data_func(renderer,self.dict_cell_data_func,(0,key,to_view))
        if editable:
            renderer.connect('edited',self.on_cells_edited,key,from_view)
        super(self.__class__,self).append_column(column)

    @staticmethod
    def dict_cell_data_func(column, cellrenderer, model, iterator, data):
        # http://faq.pygtk.org/index.py?req=edit&file=faq13.029.htp
        value = model.get_value(iterator, data[0]).get(data[1],'')
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


class ResultWidget(Gtk.ScrolledWindow):
    def __init__(self,app):
        super(self.__class__,self).__init__()
        treeview = DictTreeView(app.liststore_search)
        treeview.connect('edited',app.on_edited)
        treeview.set_vexpand(True)
        treeview.set_hexpand(True)

        for key,model in data_model.items():
            if hasattr(app,'liststore_%s'%key):
                renderer = CellRendererAutoComplete(getattr(app,'liststore_%s'%key))
            else:
                renderer = Gtk.CellRendererText()
            treeview.add_column(
                model['name'],key,from_view=model.get('from_view'),
                to_view=model.get('to_view'),editable=model['editable'],
                renderer=renderer)

        self.add(treeview)


class TransactionWindow(Gtk.Window):
    def __init__(self,app):
        super(self.__class__,self).__init__(title='Add Transaction')
        self.app = app

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5)
        self.add(box)

        # info bar
        self.infobar = Gtk.InfoBar()
        self.infolabel = Gtk.Label()
        content = self.infobar.get_content_area()
        content.add(self.infolabel)
        box.add(self.infobar)

        # date
        box.add(self.add_entry('date',data_model['date']['name']))

        # splits
        self.liststore = Gtk.ListStore(object)
        treeview = DictTreeView(self.liststore)
        treeview.connect('edited',self.on_edited)

        for key in ('amount','category','comment'):
            model = data_model[key]
            if hasattr(app,'liststore_%s'%key):
                renderer = CellRendererAutoComplete(getattr(app,'liststore_%s'%key))
            else:
                renderer = Gtk.CellRendererText()
            treeview.add_column(
                model['name'],key,from_view=model.get('from_view'),
                to_view=model.get('to_view'),editable=model['editable'],
                renderer=renderer)

        box.add(treeview)

        for key in ('client','account','tags','comment'):
            model = data_model[key]
            box.add(self.add_entry(
                key,model['name'],
                completition_liststore=getattr(app,'liststore_%s'%key,None)))

        # enter
        button= Gtk.Button('Enter')
        button.connect('clicked',self.on_entered)
        box.add(button)

        self.set_initial_values()
        self.show_all()

    def add_entry(self,key,labeltext,completition_liststore=None):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        entry = Gtk.Entry(xalign=0)
        label = Gtk.Label(labeltext, xalign=0)
        if completition_liststore:
            completition = Gtk.EntryCompletion()
            completition.set_model(completition_liststore)
            completition.set_text_column(0)
            entry.set_completion(completition)
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
        self.infolabel.set_text('')

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
        resp = handle_errors(self.infolabel,self.infobar,self.app.client.post('',docs))
        if resp:
            self.set_initial_values()


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super(self.__class__,self).__init__(title="Accounter", application=app)
        self.set_default_size(800, 800)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5)
        toolbar = self.create_toolbar()
        # with extra horizontal space
        toolbar.set_hexpand(True)
        # show the toolbar
        toolbar.show()
        # attach the toolbar to the grid
        box.add(toolbar)
        # set infobar
        box.add(app.infobar)
        # get result widget
        result_widget = ResultWidget(app)
        box.add(result_widget)
        # add the grid to the window
        self.add(box)


    # a method to create the toolbar
    def create_toolbar(self):
        # a toolbar
        toolbar = Gtk.Toolbar()

        # which is the primary toolbar of the application
        toolbar.get_style_context().add_class(Gtk.STYLE_CLASS_PRIMARY_TOOLBAR);

        button = Gtk.ToolButton.new_from_stock(Gtk.STOCK_ADD)
        button.set_is_important(True)
        toolbar.add(button)
        button.show()
        button.set_action_name("app.add")

        button = Gtk.ToolButton.new_from_stock(Gtk.STOCK_SAVE)
        button.set_is_important(True)
        toolbar.add(button)
        button.show()
        button.set_action_name("app.save")

        button = Gtk.ToolButton.new_from_stock(Gtk.STOCK_REFRESH)
        button.set_is_important(True)
        toolbar.add(button)
        button.show()
        button.set_action_name("app.update")

        button = Gtk.ToolButton.new_from_stock(Gtk.STOCK_DIALOG_AUTHENTICATION)
        button.set_is_important(True)
        toolbar.add(button)
        button.show()
        button.set_action_name("app.login")

        return toolbar

class LoginWindow(Gtk.Window):
    def __init__(self,client):
        super(self.__class__,self).__init__(title='Sign In')
        self.set_default_size(300, 100)
        self.set_resizable(False)
        topbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5)
        box.set_size_request(200,150)
        box.set_margin_left(50)
        box.set_margin_right(50)
        # infobar
        self.infobar = Gtk.InfoBar()
        self.infolabel = Gtk.Label()
        content = self.infobar.get_content_area()
        content.add(self.infolabel)
        topbox.add(self.infobar)
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
        button.connect('clicked',self.login_callback,client)
        box.add(button)
        topbox.add(box)
        self.add(topbox)
        self.show_all()

    def login_callback(self,button,client):
        resp = handle_errors(
            self.infolabel,
            self.infobar,
            client.signin(
                self.username_entry.get_text(),self.password_entry.get_text())
        )
        if resp:
            self.close()


class Application(Gtk.Application):
    def __init__(self):
        super(self.__class__,self).__init__()
        self.client = Client()
        self.liststore_search = Gtk.ListStore(object)
        self.liststore_account = Gtk.ListStore(str)
        self.liststore_tags = Gtk.ListStore(str)
        self.liststore_client = Gtk.ListStore(str)
        self.liststore_category = Gtk.ListStore(str)
        self.infolabel = Gtk.Label()
        self.infobar = Gtk.InfoBar()
        self._transaction_window = None
        self._login_window = None
        self._history = []
        content = self.infobar.get_content_area()
        content.add(self.infolabel)
        self._edited = False
        self._edited_docs = {}

    def do_activate(self):
        win = MainWindow(self)
        #  initial update and setup periodic task
        win.show_all()
        self.update_callback()
        #update_task = GLib.timeout_add_seconds(10,self.do_update)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        # new
        new_action = Gio.SimpleAction.new("add", None)
        new_action.connect("activate", self.transaction_callback)
        app.add_action(new_action)

        # update
        self.update_action=update_action = Gio.SimpleAction.new("update", None)
        update_action.connect("activate", self.update_callback)
        app.add_action(update_action)

        # save
        self.save_action=save_action = Gio.SimpleAction.new("save", None)
        save_action.connect("activate", self.save_callback)
        app.add_action(save_action)

        # login
        login_action = Gio.SimpleAction.new("login", None)
        login_action.connect("activate", self.login_callback)
        app.add_action(login_action)

    @property
    def transaction_window(self):
        if not self._transaction_window:
            self._transaction_window = TransactionWindow(self)
            self._transaction_window.connect('delete-event',self.unset_transaction_window)
        return self._transaction_window

    def unset_transaction_window(self,*args):
        self._transaction_window = None

    # callback method for new
    def transaction_callback(self, action, parameter):
        self.transaction_window.show()
        self.transaction_window.present()

    @property
    def login_window(self):
        if not self._login_window:
            self._login_window = LoginWindow(self.client)
            self._login_window.connect('delete-event',self.unset_login_window)
        return self._login_window

    def unset_login_window(self,*args):
        self._login_window = None

    # callback method for new
    def login_callback(self, action, parameter):
        self.login_window.show()
        self.login_window.present()

    def update_callback(self,*args):
        if not self._edited:
            resp = handle_errors(
                self.infolabel,self.infobar,self.client.get(''))
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
            for i in range(length)[len(items):]:
                self.liststore_search.remove(self.liststore_search._getiter(i))

    def on_edited(self,treeview,path,key):
        self._edited = True
        self.infolabel.set_text('unsaved changes')
        self.infobar.set_message_type(Gtk.MessageType.INFO)
        self.update_action.set_enabled(False)
        value = treeview.get_model()[path][0].get(key)
        change = {'path':path,'key':key,'value':value}
        self._history.append(change)
        if not path in self._edited_docs:
            self._edited_docs[path] = [change]
        else:
            self._edited_docs[path].append(change)

    def save_callback(self,*args):
        data = []
        for path in self._edited_docs:
            data.append(self.liststore_search[path][0])
        if data:
            resp = handle_errors(
                self.infolabel,self.infobar,self.client.post('',data))
        if resp and resp.get('status') == 'Ok':
            self._edited_docs.clear()
            self._edited = False
            self.infolabel.set_text('')
            self.infobar.set_message_type(Gtk.MessageType.INFO)
            self.update_action.set_enabled(True)

app = Application()
#FF6600;
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
"""

style_provider = Gtk.CssProvider()
style_provider.load_from_data(css)

Gtk.StyleContext.add_provider_for_screen(
    Gdk.Screen.get_default(),
    style_provider,
    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
)
exit_status = app.run(sys.argv)
sys.exit(exit_status)

