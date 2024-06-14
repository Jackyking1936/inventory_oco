#%%
# from fubon_neo.sdk import FubonSDK, Order
# from fubon_neo.constant import TimeInForce, OrderType, PriceType, MarketType, BSAction

# %%
import sys
import pickle
import json
import pandas as pd
from pathlib import Path
from fubon_neo.sdk import FubonSDK, Order
from fubon_neo.constant import TimeInForce, OrderType, PriceType, MarketType, BSAction
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QLineEdit, QGridLayout, QVBoxLayout, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QPlainTextEdit

from PySide6.QtGui import QBrush, QColor, QTextCursor
from PySide6.QtCore import QMutex, Qt

class LoginForm(QWidget):
	def __init__(self):
		super().__init__()
		self.setWindowTitle('Login Form')
		self.resize(500, 200)

		layout = QGridLayout()

		# label_name = QLabel('<font size="4"> Username </font>')
		label_your_id = QLabel('Your ID:')
		self.lineEdit_id = QLineEdit()
		self.lineEdit_id.setPlaceholderText('Please enter your id')
		layout.addWidget(label_your_id, 0, 0)
		layout.addWidget(self.lineEdit_id, 0, 1)

		# label_password = QLabel('<font size="4"> Password </font>')
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

		button_login = QPushButton('Login')
		button_login.clicked.connect(self.check_password)
		layout.addWidget(button_login, 5, 0, 1, 2)
		# layout.setRowMinimumHeight(2, 75)

		self.setLayout(layout)
		my_file = Path("./info.pkl")
		if my_file.is_file():
			with open('info.pkl', 'rb') as f:
				user_info_dict = pickle.load(f)
				self.lineEdit_id.setText(user_info_dict['id'])
				self.lineEdit_password.setText(user_info_dict['pwd'])
				self.lineEdit_cert_path.setText(user_info_dict['cert_path'])
				self.lineEdit_cert_pwd.setText(user_info_dict['cert_pwd'])
				self.lineEdit_acc.setText(user_info_dict['target_account'])

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
				msg.setText("No account match")
				msg.exec_()
		else:
			msg.setText(accounts.message)
			msg.exec_()

class MainApp(QWidget):
	def __init__(self):
		super().__init__()

		# 庫存表表頭
		self.table_header = ['股票名稱', '股票代號', '類別', '庫存股數', '庫存均價', '現價', '停損', '停利', '損益試算', '獲利率%']

		self.setWindowTitle("Inventory with OCO")
		self.resize(1200, 600)

		# 製作上下排列layout上為庫存表，下為log資訊
		layout = QVBoxLayout()

		self.tablewidget = QTableWidget(0, len(self.table_header))
		self.tablewidget.setHorizontalHeaderLabels([f'{item}' for item in self.table_header])
		self.log_text = QPlainTextEdit()
		self.log_text.setReadOnly(True)

		layout.addWidget(self.tablewidget)
		layout.addWidget(self.log_text)
		self.setLayout(layout)

		self.print_log("login success, 現在使用帳號: {}".format(active_account.account))
		self.print_log("建立行情連線...")
		sdk.init_realtime() # 建立行情連線
		self.print_log("行情連線建立OK")
		self.reststock = sdk.marketdata.rest_client.stock

		# 初始化庫存表資訊
		self.stop_loss_dict = {}
		self.take_profit_dict = {}
		self.inventories = {}
		self.unrealized_pnl = {}
		self.row_idx_map = {}
		self.col_idx_map = dict(zip(self.table_header, range(len(self.table_header))))
		self.mutex = QMutex()
		self.table_init()
		# self.tablewidget.hideRow(0)
		
		# 信號與槽
		self.tablewidget.itemClicked[QTableWidgetItem].connect(self.onItemClicked)

		# 建立即時行情監控
		self.subscribed_ids = {}
		sdk.set_on_filled(self.on_filled)
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
	
	def table_init(self):
		self.print_log("抓取庫存資訊...")
		inv_res = sdk.accounting.inventories(active_account)
		if inv_res.is_success:
			self.print_log("庫存抓取成功")
			inv_data = inv_res.data
			for inv in inv_data:
				if inv.today_qty != 0:
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
		i=0
		for key, value in self.inventories.items():
			ticker_res = self.reststock.intraday.ticker(symbol=key[0])
			print(ticker_res['name'])
			row = self.tablewidget.rowCount()
			self.tablewidget.insertRow(row)
			self.row_idx_map[ticker_res['symbol']] = i
			for j in range(len(self.table_header)):
				if self.table_header[j] == '股票名稱':
					item = QTableWidgetItem(ticker_res['name'])
					self.tablewidget.setItem(i, j, item)
				elif self.table_header[j] == '股票代號':
					item = QTableWidgetItem(ticker_res['symbol'])
					self.tablewidget.setItem(i, j, item)
				elif self.table_header[j] == '類別':
					# print(str(self.inventories[i].order_type))
					item = QTableWidgetItem(str(value.order_type).split('.')[-1])
					self.tablewidget.setItem(i, j, item)
				elif self.table_header[j] == '庫存股數':
					item = QTableWidgetItem(str(value.today_qty))
					self.tablewidget.setItem(i, j, item)
				elif self.table_header[j] == '庫存均價':
					item = QTableWidgetItem(str(round(self.unrealized_pnl[key].cost_price+0.00000001, 2)))
					self.tablewidget.setItem(i, j, item)
				elif self.table_header[j] == '現價':
					item = QTableWidgetItem(str(ticker_res['previousClose']))
					self.tablewidget.setItem(i, j, item)
				elif self.table_header[j] == '停損':
					item = QTableWidgetItem()
					item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled|Qt.ItemIsUserCheckable)
					item.setCheckState(Qt.Unchecked)
					self.tablewidget.setItem(i, j, item)
				elif self.table_header[j] == '停利':
					item = QTableWidgetItem()
					item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled|Qt.ItemIsUserCheckable)
					item.setCheckState(Qt.Unchecked)
					self.tablewidget.setItem(i, j, item)
				elif self.table_header[j] == '損益試算':
					cur_upnl = 0
					if self.unrealized_pnl[key].unrealized_profit > self.unrealized_pnl[key].unrealized_loss:
						cur_upnl = self.unrealized_pnl[key].unrealized_profit
					else:
						cur_upnl = -(self.unrealized_pnl[key].unrealized_loss)
					item = QTableWidgetItem(str(cur_upnl))
					# item.setForeground(QBrush(QColor(255, 0, 0)))
					# item.setBackground(QBrush(QColor(0, 255, 0)))
					self.tablewidget.setItem(i, j, item)
				elif self.table_header[j] == '獲利率%':
					cur_upnl = 0
					if self.unrealized_pnl[key].unrealized_profit > self.unrealized_pnl[key].unrealized_loss:
						cur_upnl = self.unrealized_pnl[key].unrealized_profit
					else:
						cur_upnl = -(self.unrealized_pnl[key].unrealized_loss)
					stock_cost = value.today_qty*self.unrealized_pnl[key].cost_price
					return_rate = cur_upnl/stock_cost*100
					item = QTableWidgetItem(str(round(return_rate+0.0000001, 2))+'%')
					self.tablewidget.setItem(i, j, item)
				
			i+=1
		
		self.print_log('庫存資訊初始化完成')

		# 調整股票名稱欄位寬度
		header = self.tablewidget.horizontalHeader()       
		header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

	def closeEvent(self, event):
        # do stuff
		self.print_log("disconnect websocket...")
		self.stock.disconnect()
		can_exit = True
		if can_exit:
			event.accept() # let the window close
		else:
			event.ignore()

	def handle_message(self, message):
		msg = json.loads(message)
		event = msg["event"]
		data = msg["data"]
		# print(data)
		
		# subscribed事件處理
		if event == "subscribed":
			id = data["id"]
			symbol = data["symbol"]
			self.print_log('訂閱成功'+symbol)
			self.subscribed_ids[symbol] = id
		
		elif event == "unsubscribed":
			for key, value in self.subscribed_ids.items():
				if value == data["id"]:
					self.subscribed_ids.pop(key)
					self.print_log(key+"...成功移除訂閱")
    
		# data事件處理
		elif event == "data":
			symbol = data["symbol"]
			cur_price = data["price"]
			
			self.mutex.lock()

			cur_price_item = self.tablewidget.item(self.row_idx_map[symbol], self.col_idx_map['現價'])
			cur_price_item.setText(str(cur_price))

			avg_price_item = self.tablewidget.item(self.row_idx_map[symbol], self.col_idx_map['庫存均價'])
			avg_price = avg_price_item.text()
			# print(avg_price)

			share_item = self.tablewidget.item(self.row_idx_map[symbol], self.col_idx_map['庫存股數'])
			share = share_item.text()
			# print(share)

			cur_pnl = (cur_price-float(avg_price))*float(share)
			pnl_item = self.tablewidget.item(self.row_idx_map[symbol], self.col_idx_map['損益試算'])
			pnl_item.setText(str(int(round(cur_pnl, 0))))
			# print(cur_pnl)

			return_rate = cur_pnl/(float(avg_price)*float(share))*100
			return_rate_item = self.tablewidget.item(self.row_idx_map[symbol], self.col_idx_map['獲利率%'])
			return_rate_item.setText(str(round(return_rate+0.0000001, 2))+'%')
			# print(return_rate)
			print(symbol, cur_price)

			if symbol in self.stop_loss_dict:
				if cur_price <= self.stop_loss_dict[symbol]:
					self.print_log(symbol+"...停損市價單發送...")
					sl_qty = self.tablewidget.item(self.row_idx_map[symbol], self.col_idx_map['庫存股數'])
					sl_res = self.sell_market_order(symbol, sl_qty, "inv_SL")
					if sl_res.is_success:
						self.print_log(symbol+"...停損市價單發送成功，單號: "+sl_res.data.order_no)
					else:
						self.print_log(symbol+"...停損市價單發送失敗...")
						self.print_log(sl_res.message)

			elif symbol in self.take_profit_dict:
				if cur_price >= self.stop_loss_dict[symbol]:
					self.print_log(symbol+"...停利市價單發送...")
					tp_qty = self.tablewidget.item(self.row_idx_map[symbol], self.col_idx_map['庫存股數'])
					tp_res = self.sell_market_order(symbol, tp_qty, "inv_TP")
					if tp_res.is_success:
						self.print_log(symbol+"...停利市價單發送成功，單號: "+tp_res.data.order_no)
					else:
						self.print_log(symbol+"...停利市價單發送失敗...")
						self.print_log(tp_res.message)
					
			self.mutex.unlock()

	def sell_market_order(stock_symbol, sell_qty, sl_or_tp):
		order = Order(
			buy_sell = BSAction.Sell,
			symbol = stock_symbol,
			price =  None,
			quantity =  int(sell_qty),
			market_type = MarketType.Common,
			price_type = PriceType.Market,
			time_in_force = TimeInForce.ROD,
			order_type = OrderType.Stock,
			user_def = sl_or_tp # optional field
		)

		order_res = sdk.stock.place_order(active_account, order)
		return order_res

	def on_filled(self, err, content):
		self.mutex.lock()
		inv_item = self.tablewidget.item(self.row_idx_map[content.stock_no], self.col_idx_map['庫存股數'])
		inv_qty = inv_item.text()
		remain_qty = float(inv_qty)-float(content.filled_qty)
		if remain_qty == 0:
			if content.user_def == "inv_SL":
				self.print_log("停損出場 "+content.stock_no+": "+content.filled_qty+"股, 成交價:"+str(content.filled_price))
				# stop monitor and unsubscribe
				self.stop_loss_dict.pop(content.stock_no)
				self.take_profit_dict.pop(content.stock_no)
				self.stock.unsubscribe({
					'id':self.subscribed_ids[content.stock_no]
				})
				# hide table row
				self.tablewidget.item(inv_item.row(), self.col_idx_map['停損']).setCheckState(Qt.Unchecked)
				self.tablewidget.item(inv_item.row(), self.col_idx_map['停利']).setCheckState(Qt.Unchecked)
				self.tablewidget.hideRow(inv_item.row())

			elif content.user_def == "inv_TP":
				self.print_log("停利出場 "+content.stock_no+": "+content.filled_qty+"股, 成交價:"+str(content.filled_price))
				self.stop_loss_dict.pop(content.stock_no)
				self.take_profit_dict.pop(content.stock_no)
				# stop monitor and unsubscribe
				self.stop_loss_dict.pop(content.stock_no)
				self.take_profit_dict.pop(content.stock_no)
				self.stock.unsubscribe({
					'id':self.subscribed_ids[content.stock_no]
				})
				# hide table row
				self.tablewidget.item(inv_item.row(), self.col_idx_map['停損']).setCheckState(Qt.Unchecked)
				self.tablewidget.item(inv_item.row(), self.col_idx_map['停利']).setCheckState(Qt.Unchecked)
				self.tablewidget.hideRow(inv_item.row())
				
		elif remain_qty > 0:
			remain_qty_str = str(int(round(remain_qty, 0)))
			if content.user_def == "inv_SL":
				self.print_log("停損出場 "+content.stock_no+": "+content.filled_qty+"股, 成交價:"+str(content.filled_price)+", 剩餘: "+remain_qty_str+"股")
			elif content.user_def == "inv_TP":
				self.print_log("停利出場 "+content.stock_no+": "+content.filled_qty+"股, 成交價:"+str(content.filled_price)+", 剩餘: "+remain_qty_str+"股")
			inv_item.setText(remain_qty_str)

		self.mutex.unlock()


	def handle_connect(self):
		self.print_log('market data connected')

	def handle_disconnect(self, code, message):
		self.print_log(f'market data disconnect: {code}, {message}')

	def handle_error(self, error):
		self.print_log(f'market data error: {error}')

	def print_log(self, log_info):
		self.log_text.appendPlainText(log_info)
		self.log_text.moveCursor(QTextCursor.End)

	def onItemClicked(self, item):
		if item.checkState() == Qt.Checked:
			# print(item.row(), item.column())
			# 停損相關GUI設定
			if item.column() == 6:
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
			elif item.column() == 7:
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

sdk = FubonSDK()
active_account = None

if not QApplication.instance():
    app = QApplication(sys.argv)
else:
    app = QApplication.instance()

app.setStyleSheet("QWidget{font-size: 12pt;}")
form = LoginForm()
form.show()

sys.exit(app.exec_())
# print(app.exec_())
# %%
