import sys
import pickle
import json
import pandas as pd
from pathlib import Path

from fubon_neo.sdk import FubonSDK, Order
from fubon_neo.constant import TimeInForce, OrderType, PriceType, MarketType, BSAction

from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QLineEdit, QGridLayout, QVBoxLayout, QHBoxLayout, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QPlainTextEdit, QFileDialog
from PySide6.QtGui import QTextCursor, QIcon
from PySide6.QtCore import Qt, Signal, QObject, QMutex

from threading import Timer

class LoginForm(QWidget):

    def __init__(self):
        super().__init__()
        my_icon = QIcon()
        my_icon.addFile('inventory.ico')

        self.setWindowIcon(my_icon)
        self.setWindowTitle('Login Form')
        self.resize(500, 200)

        layout_all = QVBoxLayout()

        label_warning = QLabel('本範例僅供教學參考，使用前請先了解相關內容')
        layout_all.addWidget(label_warning)

        layout = QGridLayout()

        label_your_id = QLabel('Your ID:')
        self.lineEdit_id = QLineEdit()
        self.lineEdit_id.setPlaceholderText('Please enter your id')
        layout.addWidget(label_your_id, 0, 0)
        layout.addWidget(self.lineEdit_id, 0, 1)

        label_password = QLabel('Password:')
        self.lineEdit_password = QLineEdit()
        self.lineEdit_password.setPlaceholderText('Please enter your password')
        self.lineEdit_password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(label_password, 1, 0)
        layout.addWidget(self.lineEdit_password, 1, 1)

        label_cert_path = QLabel('Cert path:')
        self.lineEdit_cert_path = QLineEdit()
        self.lineEdit_cert_path.setPlaceholderText('Please enter your cert path')
        layout.addWidget(label_cert_path, 2, 0)
        layout.addWidget(self.lineEdit_cert_path, 2, 1)

        label_cert_pwd = QLabel('Cert Password:')
        self.lineEdit_cert_pwd = QLineEdit()
        self.lineEdit_cert_pwd.setPlaceholderText('Please enter your cert password')
        self.lineEdit_cert_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(label_cert_pwd, 3, 0)
        layout.addWidget(self.lineEdit_cert_pwd, 3, 1)

        label_acc = QLabel('Account:')
        self.lineEdit_acc = QLineEdit()
        self.lineEdit_acc.setPlaceholderText('Please enter your account')
        self.lineEdit_cert_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(label_acc, 4, 0)
        layout.addWidget(self.lineEdit_acc, 4, 1)

        folder_btn = QPushButton('')
        folder_btn.setIcon(QIcon('folder.png'))
        layout.addWidget(folder_btn, 2, 2)

        login_btn = QPushButton('Login')
        layout.addWidget(login_btn, 5, 0, 1, 2)

        layout_all.addLayout(layout)
        self.setLayout(layout_all)

        folder_btn.clicked.connect(self.showDialog)
        login_btn.clicked.connect(self.check_password)

        my_file = Path("./info.pkl")
        if my_file.is_file():
            with open('info.pkl', 'rb') as f:
                user_info_dict = pickle.load(f)
                self.lineEdit_id.setText(user_info_dict['id'])
                self.lineEdit_password.setText(user_info_dict['pwd'])
                self.lineEdit_cert_path.setText(user_info_dict['cert_path'])
                self.lineEdit_cert_pwd.setText(user_info_dict['cert_pwd'])
                self.lineEdit_acc.setText(user_info_dict['target_account'])


    def showDialog(self):
        # Open the file dialog to select a file
        file_path, _ = QFileDialog.getOpenFileName(self, '請選擇您的憑證檔案', 'C:\\', 'All Files (*)')

        if file_path:
            self.lineEdit_cert_path.setText(file_path)
    
    def check_password(self):
        global active_account, sdk
        msg = QMessageBox()

        fubon_id = self.lineEdit_id.text()
        fubon_pwd = self.lineEdit_password.text()
        cert_path = self.lineEdit_cert_path.text()
        cert_pwd = self.lineEdit_cert_pwd.text()
        target_account = self.lineEdit_acc.text()
        
        user_info_dict = {
            'id':fubon_id,
            'pwd':fubon_pwd,
            'cert_path':cert_path,
            'cert_pwd':cert_pwd,
            'target_account':target_account
        }      

        accounts = sdk.login(fubon_id, fubon_pwd, Path(cert_path).__str__(), cert_pwd)
        if accounts.is_success:
            for cur_account in accounts.data:
                if cur_account.account == target_account:
                    active_account = cur_account
                    with open('info.pkl', 'wb') as f:
                        pickle.dump(user_info_dict, f)
                    
                    self.close()
                    self.main_app = MainApp()
                    self.main_app.show()
                    
            if active_account == None:
                sdk.logout()
                msg.setWindowTitle("登入失敗")
                msg.setText("找不到您輸入的帳號")
                msg.exec()
        else:
            msg.setWindowTitle("登入失敗")
            msg.setText(accounts.message)
            msg.exec()

class Communicate(QObject):
    # 定義一個帶參數的信號
    print_log_signal = Signal(str)
    update_table_signal = Signal(int, int, str)

# override定時執行的thread函數，用在假裝websocket data
class RepeatTimer(Timer):
    def run(self):
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)

class MainApp(QWidget):
    def __init__(self):
        super().__init__()

        my_icon = QIcon()
        my_icon.addFile('inventory.ico')

        self.setWindowIcon(my_icon)
        self.setWindowTitle("Python自動下單小幫手-庫存停損停利(僅示範現股操作)")
        self.resize(1200, 600)

        self.mutex = QMutex()

        # 製作上下排列layout上為庫存表，下為log資訊
        layout = QVBoxLayout()
        # 庫存表表頭
        self.table_header = ['股票名稱', '股票代號', '類別', '庫存股數', '庫存均價', '現價', '停損', '停利', '損益試算', '獲利率%']

        self.tablewidget = QTableWidget(0, len(self.table_header))
        self.tablewidget.setHorizontalHeaderLabels([f'{item}' for item in self.table_header])

        self.fake_buy = QPushButton('fake buy')
        self.fake_sell = QPushButton('fake sell')
        self.fake_websocket = QPushButton('fake websocket')

        layoutH = QHBoxLayout()
        layoutH.addWidget(self.fake_buy)
        layoutH.addWidget(self.fake_sell)
        layoutH.addWidget(self.fake_websocket)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)

        layout.addWidget(self.tablewidget)
        layout.addLayout(layoutH)
        layout.addWidget(self.log_text)
        self.setLayout(layout)

        self.print_log("login success, 現在使用帳號: {}".format(active_account.account))
        self.print_log("建立行情連線...")
        sdk.init_realtime() # 建立行情連線
        self.print_log("行情連線建立OK")
        self.reststock = sdk.marketdata.rest_client.stock

        # 初始化庫存表資訊
        self.inventories = {}
        self.unrealized_pnl = {}
        self.row_idx_map = {}
        self.epsilon = 0.0000001
        self.col_idx_map = dict(zip(self.table_header, range(len(self.table_header))))
        self.table_init()

        self.stop_loss_dict = {}
        self.take_profit_dict = {}
        self.tablewidget.itemClicked[QTableWidgetItem].connect(self.onItemClicked)

        self.communicator = Communicate()
        self.communicator.print_log_signal.connect(self.print_log)
        self.communicator.update_table_signal.connect(self.table_update)

        # 建立即時行情監控
        self.subscribed_ids = {}
        self.is_ordered = []

        self.stock = sdk.marketdata.websocket_client.stock
        self.stock.on('message', self.handle_message)
        self.stock.on('connect', self.handle_connect)
        self.stock.on('disconnect', self.handle_disconnect)
        self.stock.on('error', self.handle_error)
        self.stock.connect()

        for key, value in self.inventories.items():
            self.print_log("訂閱行情..."+key[0])
            self.stock.subscribe({
                'channel': 'trades',
                'symbol': key[0]
            })
    
    # 更新表格內某一格值的slot function
    def table_update(self, row, col, value):
        self.tablewidget.item(row, col).setText(value)


    def onItemClicked(self, item):
        if item.checkState() == Qt.Checked:
            # print(item.row(), item.column())
            # 停損相關GUI設定
            if item.column() == self.col_idx_map['停損']:
                if item.flags() == Qt.ItemFlag.ItemIsEditable:
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled|Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Unchecked)
                    symbol = self.tablewidget.item(item.row(), self.col_idx_map['股票代號']).text()
                    self.stop_loss_dict.pop(symbol)
                    self.print_log(symbol+"...移除停損，請重新設置")
                    print("stop loss:", self.stop_loss_dict)
                    return
                
                item_str = item.text()
                try:
                    item_price = float(item_str)
                except Exception as e:
                    self.print_log(str(e))
                    self.print_log("請輸入正確價格，停損價格必須小於現價並大於0")
                    item.setCheckState(Qt.Unchecked)
                    print("stop loss:", self.stop_loss_dict)
                    return
            
                cur_price = self.tablewidget.item(item.row(), self.col_idx_map['現價']).text()
                cur_price = float(cur_price)
                if cur_price<=item_price or 0>=item_price:
                    self.print_log("請輸入正確價格，停損價格必須小於現價並大於0")
                    item.setCheckState(Qt.Unchecked)
                else:
                    symbol = self.tablewidget.item(item.row(), self.col_idx_map['股票代號']).text()
                    self.stop_loss_dict[symbol] = item_price
                    item.setFlags(Qt.ItemIsEditable)
                    self.print_log(symbol+"...停損設定成功: "+item_str)
                print("stop loss:", self.stop_loss_dict)
            # 停利相關GUI設定
            elif item.column() == self.col_idx_map['停利']:
                if item.flags() == Qt.ItemFlag.ItemIsEditable:
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled|Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Unchecked)
                    symbol = self.tablewidget.item(item.row(), self.col_idx_map['股票代號']).text()
                    self.take_profit_dict.pop(symbol)
                    self.print_log(symbol+"...移除停利，請重新設置")
                    print("take profit:", self.take_profit_dict)
                    return
                
                item_str = item.text()
                try:
                    item_price = float(item_str)
                except Exception as e:
                    self.print_log(str(e))
                    self.print_log("請輸入正確價格，停利價格必須大於現價")
                    item.setCheckState(Qt.Unchecked)
                    print("take profit:", self.take_profit_dict)
                    return

                cur_price = self.tablewidget.item(item.row(), self.col_idx_map['現價']).text()
                cur_price = float(cur_price)
                if cur_price>=item_price:
                    self.print_log("請輸入正確價格，停利價格必須大於現價")
                    item.setCheckState(Qt.Unchecked)
                else:
                    symbol = self.tablewidget.item(item.row(), self.col_idx_map['股票代號']).text()
                    self.take_profit_dict[symbol] = item_price
                    item.setFlags(Qt.ItemIsEditable)
                    self.print_log(symbol+"...停利設定成功: "+item_str)
                print("take profit:", self.take_profit_dict)


    def handle_message(self, message):
        msg = json.loads(message)
        event = msg["event"]
        data = msg["data"]
        print(event, data)
        
        # subscribed事件處理
        if event == "subscribed":
            id = data["id"]
            symbol = data["symbol"]
            self.communicator.print_log_signal.emit('訂閱成功'+symbol)
            self.subscribed_ids[symbol] = id
        
        elif event == "unsubscribed":
            for key, value in self.subscribed_ids.items():
                if value == data["id"]:
                    self.subscribed_ids.pop(key)
                    self.communicator.print_log_signal.emit(key+"...成功移除訂閱")
        # data事件處理
        elif event == "data":
            self.mutex.lock()
            symbol = data["symbol"]
            cur_price = data["price"]
            
            self.communicator.update_table_signal.emit(self.row_idx_map[symbol], self.col_idx_map['現價'], str(cur_price))

            avg_price_item = self.tablewidget.item(self.row_idx_map[symbol], self.col_idx_map['庫存均價'])
            avg_price = avg_price_item.text()
            # print(avg_price)

            share_item = self.tablewidget.item(self.row_idx_map[symbol], self.col_idx_map['庫存股數'])
            share = share_item.text()
            # print(share)

            cur_pnl = (cur_price-float(avg_price))*float(share)
            self.communicator.update_table_signal.emit(self.row_idx_map[symbol], self.col_idx_map['損益試算'], str(int(round(cur_pnl, 0))))
            # print(cur_pnl)

            return_rate = cur_pnl/(float(avg_price)*float(share))*100
            self.communicator.update_table_signal.emit(self.row_idx_map[symbol], self.col_idx_map['獲利率%'], str(round(return_rate+self.epsilon, 2))+'%')
            # print(return_rate)

            self.mutex.unlock()
            # print(symbol, cur_price)


    def handle_connect(self):
        self.communicator.print_log_signal.emit('market data connected')

    def handle_disconnect(self, code, message):
        self.communicator.print_log_signal.emit(f'market data disconnect: {code}, {message}')

    def handle_error(self, error):
        self.communicator.print_log_signal.emit(f'market data error: {error}')


    # 視窗啟動時撈取對應帳號的inventories和unrealized_pnl初始化表格
    def table_init(self):
        self.print_log("抓取庫存資訊...")
        inv_res = sdk.accounting.inventories(active_account)
        if inv_res.is_success:
            self.print_log("庫存抓取成功")
            inv_data = inv_res.data
            for inv in inv_data:
                if inv.today_qty != 0 and inv.order_type == OrderType.Stock:
                    self.inventories[(inv.stock_no, str(inv.order_type))] = inv
        else:
            self.print_log("庫存抓取失敗")

        self.print_log("抓取未實現損益...")
        upnl_res = sdk.accounting.unrealized_gains_and_loses(active_account)
        if upnl_res.is_success:
            self.print_log("未實現損益抓取成功")
            upnl_data = upnl_res.data
            for upnl in upnl_data:
                self.unrealized_pnl[(upnl.stock_no, str(upnl.order_type))] = upnl
        else:
            self.print_log("未實現損益抓取失敗")

        # 依庫存及未實現損益資訊開始填表
        for key, value in self.inventories.items():
            ticker_res = self.reststock.intraday.ticker(symbol=key[0])
            print(ticker_res['name'])
            row = self.tablewidget.rowCount()
            self.tablewidget.insertRow(row)
            self.row_idx_map[ticker_res['symbol']] = row
            for j in range(len(self.table_header)):
                if self.table_header[j] == '股票名稱':
                    item = QTableWidgetItem(ticker_res['name'])
                    self.tablewidget.setItem(row, j, item)
                elif self.table_header[j] == '股票代號':
                    item = QTableWidgetItem(ticker_res['symbol'])
                    self.tablewidget.setItem(row, j, item)
                elif self.table_header[j] == '類別':
                    item = QTableWidgetItem(str(value.order_type).split('.')[-1])
                    self.tablewidget.setItem(row, j, item)
                elif self.table_header[j] == '庫存股數':
                    item = QTableWidgetItem(str(value.today_qty))
                    self.tablewidget.setItem(row, j, item)
                elif self.table_header[j] == '現價':
                    item = QTableWidgetItem(str(ticker_res['previousClose']))
                    self.tablewidget.setItem(row, j, item)
                elif self.table_header[j] == '停損':
                    item = QTableWidgetItem()
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled|Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Unchecked)
                    self.tablewidget.setItem(row, j, item)
                elif self.table_header[j] == '停利':
                    item = QTableWidgetItem()
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled|Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Unchecked)
                    self.tablewidget.setItem(row, j, item)
                elif self.table_header[j] == '庫存均價':
                    item = QTableWidgetItem(str(round(self.unrealized_pnl[key].cost_price+self.epsilon, 2)))
                    self.tablewidget.setItem(row, j, item)
                elif self.table_header[j] == '損益試算':
                    cur_upnl = 0
                    if self.unrealized_pnl[key].unrealized_profit > self.unrealized_pnl[key].unrealized_loss:
                        cur_upnl = self.unrealized_pnl[key].unrealized_profit
                    else:
                        cur_upnl = -(self.unrealized_pnl[key].unrealized_loss)
                    item = QTableWidgetItem(str(cur_upnl))
                    self.tablewidget.setItem(row, j, item)
                elif self.table_header[j] == '獲利率%':
                    cur_upnl = 0
                    if self.unrealized_pnl[key].unrealized_profit > self.unrealized_pnl[key].unrealized_loss:
                        cur_upnl = self.unrealized_pnl[key].unrealized_profit
                    else:
                        cur_upnl = -(self.unrealized_pnl[key].unrealized_loss)
                    stock_cost = value.today_qty*self.unrealized_pnl[key].cost_price
                    return_rate = cur_upnl/stock_cost*100
                    item = QTableWidgetItem(str(round(return_rate+self.epsilon, 2))+'%')
                    self.tablewidget.setItem(row, j, item)

            
        self.print_log('庫存資訊初始化完成')

        # 調整股票名稱欄位寬度
        header = self.tablewidget.horizontalHeader()      
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        print(self.row_idx_map)
        print(self.col_idx_map)

    ### all slot function
    # 更新最新log到QPlainTextEdit的slot function
    def print_log(self, log_info):
        self.log_text.appendPlainText(log_info)
        self.log_text.moveCursor(QTextCursor.End)

try:
    sdk = FubonSDK()
except ValueError:
    raise ValueError("請確認網路連線")
active_account = None
 
if not QApplication.instance():
    app = QApplication(sys.argv)
else:
    app = QApplication.instance()
 
app.setStyleSheet("QWidget{font-size: 12pt;}")
form = LoginForm()
form.show()
 
sys.exit(app.exec())
