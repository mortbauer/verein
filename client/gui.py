#coding=utf-8
import sys
import datetime
import logging
from app import Client
from gi.repository import Gtk, Gdk, Gio, GLib

liststore_clients = Gtk.ListStore(str)
liststore_clients.append(['martin'])


liststore_categories = Gtk.ListStore(str)
liststore_categories.append(['test'])

class CellRendererAutoComplete(Gtk.CellRendererText):
    # http://stackoverflow.com/a/13769663/1607448
    """ Text entry cell which accepts a Gtk.EntryCompletion object """

    __gtype_name__ = 'CellRendererAutoComplete'

    def __init__(self, completion):
        self.completion = completion
        Gtk.CellRendererText.__init__(self)

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

    def editing_done(self):
        self.emit('edited', path, entry.get_text())


class DictTreeView(Gtk.TreeView):
    def __init__(self,liststore):
        super(self.__class__,self).__init__(liststore)

    def add_column(self,name,key,Renderer=Gtk.CellRendererText):
        renderer = Renderer()
        renderer.set_property("editable", True)
        column = Gtk.TreeViewColumn(name,renderer)
        column.set_resizable(True)
        column.set_reorderable(True)
        column.set_cell_data_func(renderer,self.dict_cell_data_func,(0,key))
        super(self.__class__,self).append_column(column)

    @staticmethod
    def dict_cell_data_func(column, cellrenderer, model, iterator, col_key):
        # http://faq.pygtk.org/index.py?req=edit&file=faq13.029.htp
        text = model.get_value(iterator, col_key[0])[col_key[1]]
        cellrenderer.set_property("text", str(text))

class ResultWidget(Gtk.ScrolledWindow):
    def __init__(self,liststore):
        super(self.__class__,self).__init__()
        treeview = DictTreeView(liststore)
        treeview.set_vexpand(True)
        treeview.set_hexpand(True)


        data_model = [
            {'key':'date','name':'Durchführungsdatum'},
            {'key':'client','name':'Auftraggeber'},
            {'key':'amount','name':'Betrag'},
            {'key':'account','name':'Konto'},
        ]

        for column in data_model:
            treeview.add_column(column['name'],column['key'])

        self.add(treeview)



class TransactionWidget(Gtk.Window):
    def __init__(self,client):
        super(self.__class__,self).__init__()
        self.client = client

        #listbox = Gtk.Box()
        listbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5)
        self.add(listbox)

        # info bar
        self.infobar = Gtk.InfoBar()
        self.infolabel = Gtk.Label()
        content = self.infobar.get_content_area()
        content.add(self.infolabel)
        listbox.add(self.infobar)
        self.infobar.connect('response',self.on_response)

        # date
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        label = Gtk.Label("Datum", xalign=0)
        vbox.pack_start(label, True, True, 0)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=50)
        vbox.pack_start(hbox, True, True, 0)

        self.date = Gtk.Entry(xalign=0)
        self.date.set_text(datetime.datetime.strftime(datetime.datetime.now(),'%d.%m.%Y'))
        hbox.pack_start(self.date, True, True, 0)

        calendar = Gtk.Button('C')
        calendar.props.valign = Gtk.Align.CENTER
        hbox.pack_start(calendar, False, True, 0)

        listbox.add(vbox)

        # splits

        self.splits = Gtk.ListStore(float, str,str)
        self.splits.append([0.0, "",""])
        treeview = Gtk.TreeView(model=self.splits)

        renderer_editabletext = Gtk.CellRendererText()
        renderer_editabletext.set_property("editable", True)
        column_editabletext = Gtk.TreeViewColumn(
            "Amount",renderer_editabletext, text=0)
        treeview.append_column(column_editabletext)
        renderer_editabletext.connect("edited", self.on_splits_amount_edited)

        category_completition = Gtk.EntryCompletion()
        category_completition.set_model(liststore_categories)
        category_completition.set_text_column(0)
        category_completition.set_inline_completion(True)

        renderer_editabletext = CellRendererAutoComplete(category_completition)
        renderer_editabletext.set_property("editable", True)
        column_editabletext = Gtk.TreeViewColumn(
            "Category",renderer_editabletext, text=1)
        treeview.append_column(column_editabletext)
        renderer_editabletext.connect("edited", self.on_splits_category_edited)

        renderer_editabletext = Gtk.CellRendererText()
        renderer_editabletext.set_property("editable", True)
        column_editabletext = Gtk.TreeViewColumn(
            "Comment",renderer_editabletext, text=2)
        treeview.append_column(column_editabletext)
        renderer_editabletext.connect("edited", self.on_splits_comment_edited)

        listbox.add(treeview)

        # payee
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.payee = Gtk.Entry(xalign=0)
        label = Gtk.Label("Client", xalign=0)
        client_completition = Gtk.EntryCompletion()
        client_completition.set_model(liststore_clients)
        client_completition.set_text_column(0)
        #client_completition.set_inline_completion(True)
        self.payee.set_completion(client_completition)
        vbox.pack_start(label, True, True, 0)
        vbox.pack_start(self.payee, True, True, 0)
        listbox.add(vbox)

        # account
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.account = Gtk.Entry(xalign=0)
        label = Gtk.Label("Account", xalign=0)
        vbox.pack_start(label, True, True, 0)
        vbox.pack_start(self.account, True, True, 0)
        listbox.add(vbox)

        # tags
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.tags = Gtk.Entry(xalign=0)
        label = Gtk.Label("Tags", xalign=0)
        vbox.pack_start(label, True, True, 0)
        vbox.pack_start(self.tags, True, True, 0)
        listbox.add(vbox)

        # comment
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.comment = Gtk.Entry(xalign=0)
        label = Gtk.Label("Comment", xalign=0)
        vbox.pack_start(label, True, True, 0)
        vbox.pack_start(self.comment, True, True, 0)
        listbox.add(vbox)

        # enter
        button= Gtk.Button('Enter')
        button.connect('clicked',self.on_entered)
        listbox.add(button)

    def _set_initial_values(self):
        self.date.set_text(datetime.datetime.strftime(datetime.datetime.now(),'%d.%m.%Y'))
        self.splits.clear()
        self.splits.append([0.0, "",""])
        self.payee.set_text('')
        self.account.set_text('')
        self.comment.set_text('')
        self.infolabel.set_text('')

    def on_splits_amount_edited(self,widget,path,text):
        try:
            value = float(text)
        except:
            logging.info('couldn\'t convert amount to float')
        self.splits[path][0] = value
        if value != 0.0:
            self._apend_row()
        else:
            self._remove_row(path)

    def on_splits_category_edited(self,widget,path,text):
        self.splits[path][1] = text
        if text == '':
            self._remove_row(path)

    def on_splits_comment_edited(self,widget,path,text):
        self.splits[path][2] = text
        if text == '':
            self._remove_row(path)

    def _apend_row(self):
        if self.splits[-1][0] != 0:
            self.splits.append([0.0,'',''])

    def _remove_row(self,path):
        if int(path) < len(self.splits)-1:
            row = self.splits[path]
            if row[0] == 0 and row[1] == '' and row[2] == '':
                self.splits.remove(self.splits._getiter(path))

    def on_response(self,widget,event):
        widget.hide()

    def on_entered(self,button):
        d = {}
        d['date'] = self.date.get_text()
        d['client'] = self.payee.get_text()
        d['tags'] = self.tags.get_text().split(',')
        d['account'] = self.account.get_text()
        d['splits'] = splits = []
        for i in range(len(self.splits)-1):
            splits.append(
                {'amount':self.splits[i][0],
                 'category':self.splits[i][1],
                 'comment':self.splits[i][2]
                 }
            )
        d['comment'] = self.comment.get_text()
        status_code, resp = self.client.put('',d)
        if status_code == 200:
            self.infobar.set_message_type(Gtk.MessageType.INFO)
            self._set_initial_values()
        elif status_code == 400:
            self.infobar.set_message_type(Gtk.MessageType.WARNING)
            self.infolabel.set_text('\n'.join(
                ['{0}: {1}'.format(k,v) for k,v in resp['issues'].items()]))
        else:
            self.infobar.set_message_type(Gtk.MessageType.ERROR)
            self.infolabel.set_text(resp['message'])

    def on_payees_changed(self,value):
        pass

    def on_accounts_changed(self,value):
        pass

class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        Gtk.Window.__init__(self, title="Accounter", application=app)
        self.set_default_size(800, 800)

        # a grid to attach the toolbar
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5)
        #transaction_widget = TransactionWidget(app.client)
        #notebook.append_page(transaction_widget,Gtk.Label('Add',xalign=0))
        #paned.add1(notebook)
        # a toolbar created in the method create_toolbar (see below)
        toolbar = self.create_toolbar()
        # with extra horizontal space
        toolbar.set_hexpand(True)
        # show the toolbar
        toolbar.show()
        # attach the toolbar to the grid
        box.add(toolbar)

        # set infobar
        box.add(app.infobar)

        result_widget = ResultWidget(app.liststore)
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
        toolbar.insert(button, 0)
        button.show()
        button.set_action_name("app.add")

        button = Gtk.ToolButton.new_from_stock(Gtk.STOCK_REFRESH)
        button.set_is_important(True)
        toolbar.insert(button, 0)
        button.show()
        button.set_action_name("app.update")
        return toolbar

    # callback method for fullscreen / leave fullscreen
    def fullscreen_callback(self, action, parameter):
        # check if the state is the same as Gdk.WindowState.FULLSCREEN, which is a bit flag
        is_fullscreen = self.get_window().get_state() & Gdk.WindowState.FULLSCREEN != 0
        if not is_fullscreen:
            self.fullscreen_button.set_stock_id(Gtk.STOCK_LEAVE_FULLSCREEN)
            self.fullscreen()
        else:
            self.fullscreen_button.set_stock_id(Gtk.STOCK_FULLSCREEN)
            self.unfullscreen()


class Application(Gtk.Application):
    def __init__(self):
        Gtk.Application.__init__(self)
        self.client = Client()
        self.liststore = Gtk.ListStore(object)
        self.infolabel = Gtk.Label()
        self.infobar = Gtk.InfoBar()
        content = self.infobar.get_content_area()
        content.add(self.infolabel)

    def do_activate(self):
        win = MainWindow(self)
        self.transaction_win = TransactionWidget(self.client)
        win.show_all()
        #  initial update and setup periodic task
        self.update_callback()
        #update_task = GLib.timeout_add_seconds(10,self.do_update)


    def do_startup(self):
        Gtk.Application.do_startup(self)

        # create the actions that control the window and connect their signal to a
        # callback method (see below):

        # new
        new_action = Gio.SimpleAction.new("add", None)
        new_action.connect("activate", self.transaction_callback)
        app.add_action(new_action)

        # update
        update_action = Gio.SimpleAction.new("update", None)
        update_action.connect("activate", self.update_callback)
        app.add_action(update_action)

    # callback method for new
    def transaction_callback(self, action, parameter):
        self.transaction_win.show_all()

    def update_callback(self,*args):
        status,resp = self.client.get('')
        if status != 200:
            self.infolabel.set_text(resp['message'])
            self.infobar.set_message_type(Gtk.MessageType.ERROR)
        else:
            self.infolabel.set_text('')
            self.infobar.set_message_type(Gtk.MessageType.INFO)
            items = resp['_items']
            length = len(self.liststore)
            for i in range(length):
                self.liststore.set_row(self.liststore._getiter(i),[items[i]])
            for doc in items[length:]:
                self.liststore.append([doc])
        # it is important that the function returns True, otherwise it will
        # wait infinitely
        return True

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

