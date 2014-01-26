import sys
import datetime
import logging
from app import Client
from gi.repository import Gtk, Gdk, Gio

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

    def editing_done(self, entry, path):
        self.emit('edited', path, entry.get_text())


def dict_cell_data_func(column, cell, model, iter, col_key):
    # http://faq.pygtk.org/index.py?req=edit&file=faq13.029.htp
     text = model.get_value(iter, col_key[0])[col_key[1]]
     cell.set_property("text", text)

   model = gtk.ListStore(object)
   tree_view = gtk.TreeView(model)
   renderer = gtk.CellRendererText()
   column = gtk.TreeViewColumn("Foo", renderer)
   column.set_cell_data_func(renderer, dict_cell_data_func, (0, 'foo'))
   tree_view.append_column(column)

   obj = {'foo': 'foo text'}
   model.append([obj])
class ResultWindow(Gtk.Box):
    def __init__(self,client):
        Gtk.Box.__init__(self)
        self.client = client
        self.liststore = Gtk.ListStore(str,str,float,str,str,str,str)
        self.treeview = Gtk.TreeView(model=self.liststore)
        self.add_editable_column('date',0)
        self.add_editable_column('client',1)
        self.add_editable_column('amount',2)
        self.add_editable_column('category',3)
        self.add_editable_column('comment',4)
        self.add_editable_column('info',5)
        self.add_editable_column('tags',6)
        self.update()
        self.add(self.treeview)

    def update(self):
        l = ['date','client','amount','category','comment','info','tags']
        for doc in self.client.get('')['_items']:
            self.liststore.append([doc.get(key,'') for key in l])


    def add_editable_column(self,name,col):
        renderer_editabletext = Gtk.CellRendererText()
        renderer_editabletext.set_property("editable", True)
        column_editabletext = Gtk.TreeViewColumn(
            name,renderer_editabletext, text=col)
        self.treeview.append_column(column_editabletext)
        #renderer_editabletext.connect("edited", getattr(self,'on_%s_edited'%name))



class TransactionWidget(Gtk.Box):
    def __init__(self,client):
        Gtk.Box.__init__(self)
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


        self.connect("delete-event", Gtk.main_quit)

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
        d['payee'] = self.payee.get_text()
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
        resp = self.client.put('',d)
        if resp['status_code'] == 200:
            self.infobar.set_message_type(Gtk.MessageType.INFO)
            self._set_initial_values()
        elif resp['status_code'] == 400:
            self.infobar.set_message_type(Gtk.MessageType.ERROR)
            self.infolabel.set_text('\n'.join(
                ['{0}: {1}'.format(k,v) for k,v in resp['issues'].items()]))

    def on_payees_changed(self,value):
        pass

    def on_accounts_changed(self,value):
        pass

class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        Gtk.Window.__init__(self, title="Accounter", application=app)
        self.set_default_size(400, 200)

        # a grid to attach the toolbar
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5)
        paned = Gtk.Paned()
        notebook = Gtk.Notebook()
        transaction_widget = TransactionWidget(app.client)
        notebook.append_page(transaction_widget,Gtk.Label('Add',xalign=0))
        paned.add1(notebook)
        search_widget = ResultWindow(app.client)
        paned.add2(search_widget)
        # a toolbar created in the method create_toolbar (see below)
        toolbar = self.create_toolbar()
        # with extra horizontal space
        toolbar.set_hexpand(True)
        # show the toolbar
        toolbar.show()
        # attach the toolbar to the grid
        box.add(toolbar)
        box.pack_start(paned,True,True,0)
        # add the grid to the window
        self.add(box)

    # a method to create the toolbar
    def create_toolbar(self):
        # a toolbar
        toolbar = Gtk.Toolbar()

        # which is the primary toolbar of the application
        toolbar.get_style_context().add_class(Gtk.STYLE_CLASS_PRIMARY_TOOLBAR);

        # create a button for the "new" action, with a stock image
        new_button = Gtk.ToolButton.new_from_stock(Gtk.STOCK_NEW)
        # label is shown
        new_button.set_is_important(True)
        # insert the button at position in the toolbar
        toolbar.insert(new_button, 0)
        # show the button
        new_button.show()
        # set the name of the action associated with the button.
        # The action controls the application (app)
        new_button.set_action_name("app.new")

        # button for the "open" action
        open_button = Gtk.ToolButton.new_from_stock(Gtk.STOCK_OPEN)
        open_button.set_is_important(True)
        toolbar.insert(open_button, 1)
        open_button.show()
        open_button.set_action_name("app.open")

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

    def do_activate(self):
        win = MainWindow(self)
        win.show_all()

    def do_startup(self):
        Gtk.Application.do_startup(self)

        # create the actions that control the window and connect their signal to a
        # callback method (see below):

        # new
        new_action = Gio.SimpleAction.new("new", None)
        new_action.connect("activate", self.new_callback)
        app.add_action(new_action)

        # open
        open_action = Gio.SimpleAction.new("open", None)
        open_action.connect("activate", self.open_callback)
        app.add_action(open_action)

    # callback method for new
    def new_callback(self, action, parameter):
        print "You clicked \"New\"."

    # callback method for open
    def open_callback(self, action, parameter):
        print "You clicked \"Open\"."

app = Application()

css = """
.error {
    background-color: #FF6600;
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
#client = Client()
#win = TransactionWindow(client)
#Gtk.main()

