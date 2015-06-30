##########################################
# Copyright 2012-2014 Ceruti Francesco & contributors
#
# This file is part of LiSP (Linux Show Player).
##########################################

from PyQt5 import QtCore
from PyQt5.QtGui import QPainter, QPolygon, QPainterPath
from PyQt5.QtWidgets import QGroupBox, QLineEdit, QLabel, QWidget, \
    QHBoxLayout, QTreeWidget, QTreeWidgetItem, QGridLayout, QDialog, \
    QDialogButtonBox, QPushButton
import jack

from lisp.gst.elements.jack_sink import JackSink
from lisp.ui.settings.section import SettingsSection


class JackSinkSettings(SettingsSection):
    NAME = "Jack Sink"
    ELEMENT = JackSink

    def __init__(self, size, Id, parent=None):
        super().__init__(size, parent)

        self.id = Id

        self.serverGroup = QGroupBox(self)
        self.serverGroup.setTitle('Jack')
        self.serverGroup.setGeometry(0, 0, self.width(), 100)
        self.serverGroup.setLayout(QHBoxLayout())

        self.serverLineEdit = QLineEdit(self.serverGroup)
        self.serverLineEdit.setToolTip('Name of the server to connect with')
        self.serverLineEdit.setText('default')
        self.serverGroup.layout().addWidget(self.serverLineEdit)

        self.serverLineEditLabel = QLabel('Sever name', self.serverGroup)
        self.serverLineEditLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.serverGroup.layout().addWidget(self.serverLineEditLabel)

        self.connectionsGroup = QGroupBox(self)
        self.connectionsGroup.setTitle('Connections')
        self.connectionsGroup.setGeometry(0, 120, self.width(), 80)
        self.connectionsGroup.setLayout(QHBoxLayout())

        self.connectionsEdit = QPushButton('Edit connections', self)
        self.connectionsEdit.clicked.connect(self.__edit_connections)
        self.connectionsGroup.layout().addWidget(self.connectionsEdit)

        self.__jack_client = jack.Client('LinuxShowPlayer_SettingsControl')
        self.connections = JackSink.get_default_connections(self.__jack_client)

    def closeEvent(self, event):
        self.__jack_client.close()
        super().closeEvent(event)

    def get_configuration(self):
        conf = {}
        if not (
            self.serverGroup.isCheckable() and not self.serverGroup.isChecked()):
            server = self.serverLineEdit.text()
            conf['server'] = server if server.lower() != 'default' else None
            conf['connections'] = self.connections

        return {self.id: conf}

    def set_configuration(self, conf):
        if self.id in conf:
            conf = conf[self.id]

            self.serverLineEdit.setText(
                'default' if conf['server'] is None else conf['server'])
            self.connections = conf['connections'].copy()

    def enable_check(self, enable):
        self.serverGroup.setCheckable(enable)
        self.serverGroup.setChecked(False)

    def __edit_connections(self):
        dialog = JackConnectionsDialog(self.__jack_client, parent=self)
        dialog.set_connections(self.connections.copy())
        dialog.exec_()

        if dialog.result() == dialog.Accepted:
            self.connections = dialog.connections


class ClientItem(QTreeWidgetItem):
    def __init__(self, client_name):
        super().__init__([client_name])

        self.name = client_name
        self.ports = {}

    def add_port(self, port_name):
        port = PortItem(port_name)

        self.addChild(port)
        self.ports[port_name] = port


class PortItem(QTreeWidgetItem):
    def __init__(self, port_name):
        super().__init__([port_name[:port_name.index(':')]])

        self.name = port_name


class ConnectionsWidget(QWidget):
    """ Code ported from QjackCtl (http://qjackctl.sourceforge.net) """

    def __init__(self, output_widget, input_widget, parent=None, **kwargs):
        super().__init__(parent)

        self._output_widget = output_widget
        self._input_widget = input_widget
        self.connections = []

    def draw_connection_line(self, painter, x1, y1, x2, y2, h1, h2):
        # Account for list view headers.
        y1 += h1
        y2 += h2

        # Invisible output ports don't get a connecting dot.
        if y1 > h1:
            painter.drawLine(x1, y1, x1 + 4, y1)

        # Setup control points
        spline = QPolygon(4)
        cp = int((x2 - x1 - 8) * 0.4)
        spline.setPoints(x1 + 4, y1,
                         x1 + 4 + cp, y1,
                         x2 - 4 - cp, y2,
                         x2 - 4, y2)
        # The connection line
        path = QPainterPath()
        path.moveTo(spline.at(0))
        path.cubicTo(spline.at(1), spline.at(2), spline.at(3))
        painter.strokePath(path, painter.pen())

        # painter.drawLine(x1 + 4, y1, x2 - 4, y2)

        # Invisible input ports don't get a connecting dot.
        if y2 > h2:
            painter.drawLine(x2 - 4, y2, x2, y2)

    def paintEvent(self, QPaintEvent):
        yc = self.y()
        yo = self._output_widget.y()
        yi = self._input_widget.y()

        x1 = 0
        x2 = self.width()
        h1 = self._output_widget.header().sizeHint().height()
        h2 = self._input_widget.header().sizeHint().height()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        for output, out_conn in enumerate(self.connections):
            y1 = int(self.item_y(self._output_widget.topLevelItem(output)) + (
            yo - yc))

            for client in range(self._input_widget.topLevelItemCount()):
                client = self._input_widget.topLevelItem(client)

                for port in client.ports:
                    if port in self.connections[output]:
                        y2 = int(self.item_y(client.ports[port]) + (yi - yc))
                        self.draw_connection_line(painter, x1, y1, x2, y2, h1,
                                                  h2)

        painter.end()

    @staticmethod
    def item_y(item):
        tree_widget = item.treeWidget()
        parent = item.parent()

        if parent is not None and not parent.isExpanded():
            rect = tree_widget.visualItemRect(parent)
        else:
            rect = tree_widget.visualItemRect(item)

        return rect.top() + rect.height() / 2


class JackConnectionsDialog(QDialog):
    def __init__(self, jack_client, parent=None, **kwargs):
        super().__init__(parent)

        self.resize(600, 400)

        self.setLayout(QGridLayout())
        # self.layout().setContentsMargins(0, 0, 0, 0)

        self.output_widget = QTreeWidget(self)
        self.output_widget.setHeaderLabels(['Output ports'])

        self.input_widget = QTreeWidget(self)
        self.input_widget.setHeaderLabels(['Input ports'])

        self.connections_widget = ConnectionsWidget(self.output_widget,
                                                    self.input_widget,
                                                    parent=self)
        self.output_widget.itemExpanded.connect(self.connections_widget.update)
        self.output_widget.itemCollapsed.connect(self.connections_widget.update)
        self.input_widget.itemExpanded.connect(self.connections_widget.update)
        self.input_widget.itemCollapsed.connect(self.connections_widget.update)

        self.input_widget.itemSelectionChanged.connect(
            self.__input_selection_changed)
        self.output_widget.itemSelectionChanged.connect(
            self.__output_selection_changed)

        self.layout().addWidget(self.output_widget, 0, 0)
        self.layout().addWidget(self.connections_widget, 0, 1)
        self.layout().addWidget(self.input_widget, 0, 2)

        self.layout().setColumnStretch(0, 2)
        self.layout().setColumnStretch(1, 1)
        self.layout().setColumnStretch(2, 2)

        self.connectButton = QPushButton('Connect', self)
        self.connectButton.clicked.connect(self.__disconnect_selected)
        self.connectButton.setEnabled(False)
        self.layout().addWidget(self.connectButton, 1, 1)

        self.dialogButtons = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        self.dialogButtons.accepted.connect(self.accept)
        self.dialogButtons.rejected.connect(self.reject)
        self.layout().addWidget(self.dialogButtons, 2, 0, 1, 3)

        self.__jack_client = jack_client
        self.__selected_in = None
        self.__selected_out = None

        self.connections = []
        self.update_graph()

    def set_connections(self, connections):
        self.connections = connections
        self.connections_widget.connections = self.connections
        self.connections_widget.update()

    def update_graph(self):
        input_ports = self.__jack_client.get_ports(is_audio=True, is_input=True)

        self.output_widget.clear()
        for port in range(8):
            self.output_widget.addTopLevelItem(
                QTreeWidgetItem(['output_' + str(port)]))

        self.input_widget.clear()
        clients = {}
        for port in input_ports:
            client_name = port.name[:port.name.index(':')]

            if client_name not in clients:
                clients[client_name] = ClientItem(client_name)
                self.input_widget.addTopLevelItem(clients[client_name])

            clients[client_name].add_port(port.name)

    def __input_selection_changed(self):
        if len(self.input_widget.selectedItems()) > 0:
            self.__selected_in = self.input_widget.selectedItems()[0]
        else:
            self.__selected_in = None

        self.__check_selection()

    def __output_selection_changed(self):
        if len(self.output_widget.selectedItems()) > 0:
            self.__selected_out = self.output_widget.selectedItems()[0]
        else:
            self.__selected_out = None

        self.__check_selection()

    def __check_selection(self):
        if self.__selected_in is not None and self.__selected_out is not None:
            output = self.output_widget.indexOfTopLevelItem(self.__selected_out)

            self.connectButton.clicked.disconnect()
            self.connectButton.setEnabled(True)

            if self.__selected_in.name in self.connections[output]:
                self.connectButton.setText('Disconnect')
                self.connectButton.clicked.connect(self.__disconnect_selected)
            else:
                self.connectButton.setText('Connect')
                self.connectButton.clicked.connect(self.__connect_selected)
        else:
            self.connectButton.setEnabled(False)

    def __connect_selected(self):
        output = self.output_widget.indexOfTopLevelItem(self.__selected_out)
        self.connections[output].append(self.__selected_in.name)
        self.connections_widget.update()
        self.__check_selection()

    def __disconnect_selected(self):
        output = self.output_widget.indexOfTopLevelItem(self.__selected_out)
        self.connections[output].remove(self.__selected_in.name)
        self.connections_widget.update()
        self.__check_selection()
