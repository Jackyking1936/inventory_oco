#%%
# from fubon_neo.sdk import FubonSDK, Order
# from fubon_neo.constant import TimeInForce, OrderType, PriceType, MarketType, BSAction

# %%
import sys
import pickle
import pandas as pd
from pathlib import Path
from fubon_neo.sdk import FubonSDK, Order
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QLineEdit, QGridLayout, QVBoxLayout, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QPlainTextEdit

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
					
				else:
					msg.setText("No account match")
					msg.exec_()
		else:
			msg.setText(accounts.message)
			msg.exec_()

class MainApp(QWidget):
	def __init__(self):
		super().__init__()

		self.table_header = ['股票名稱', '股票代號', '類別', '庫存股數', '庫存均價', '現價', '停損', '停利', '損益試算', '獲利率%']

		self.setWindowTitle("Inventory with OCO")
		self.resize(1200, 800)

		layout = QVBoxLayout()

		# label=QLabel("Main APP", self)
		self.tablewidget = QTableWidget(0, len(self.table_header))
		self.tablewidget.setHorizontalHeaderLabels([f'{item}' for item in self.table_header])
		# self.tablewidget.resizeColumnsToContents()
		self.log_text = QPlainTextEdit()
		self.log_text.setReadOnly(True)

		layout.addWidget(self.tablewidget)
		layout.addWidget(self.log_text)
		self.setLayout(layout)

		self.log_text.appendPlainText("login success, 現在使用帳號: {}".format(active_account.account))
		self.log_text.appendPlainText("抓取庫存資訊...")

		self.inventories = {}
		self.unrealized_pnl = {}
		self.table_init()
		header = self.tablewidget.horizontalHeader()       
		header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
	
	def table_init(self):
		inv_res = sdk.accounting.inventories(active_account)
		if inv_res.is_success:
			self.log_text.appendPlainText("庫存抓取成功")
			inv_data = inv_res.data
			for inv in inv_data:
				self.inventories[(inv.stock_no, str(inv.order_type))] = inv
		else:
			self.log_text.appendPlainText("庫存抓取失敗")

		upnl_res = sdk.accounting.unrealized_gains_and_loses(active_account)
		if upnl_res.is_success:
			self.log_text.appendPlainText("未實現損益抓取成功")
			upnl_data = upnl_res.data
			for upnl in upnl_data:
				self.unrealized_pnl[(upnl.stock_no, str(upnl.order_type))] = upnl
		else:
			self.log_text.appendPlainText("未實現損益抓取失敗")

		sdk.init_realtime() # 建立行情連線
		self.reststock = sdk.marketdata.rest_client.stock

		i=0
		for key, value in self.inventories.items():
			ticker_res = self.reststock.intraday.ticker(symbol=key[0])
			print(ticker_res['name'])
			row = self.tablewidget.rowCount()
			self.tablewidget.insertRow(row)

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
				elif self.table_header[j] == '損益試算':
					cur_upnl = 0
					if self.unrealized_pnl[key].unrealized_profit > self.unrealized_pnl[key].unrealized_loss:
						cur_upnl = self.unrealized_pnl[key].unrealized_profit
					else:
						cur_upnl = -(self.unrealized_pnl[key].unrealized_loss)
					item = QTableWidgetItem(str(cur_upnl))
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
		
		self.log_text.appendPlainText('庫存資訊初始化完成')	

		# print(self.inventories[i].stock_no)


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
