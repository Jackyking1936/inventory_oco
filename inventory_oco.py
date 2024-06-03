#%%
# from fubon_neo.sdk import FubonSDK, Order
# from fubon_neo.constant import TimeInForce, OrderType, PriceType, MarketType, BSAction

# %%
import sys
import pickle 
from pathlib import Path
from fubon_neo.sdk import FubonSDK, Order
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QLineEdit, QGridLayout, QMessageBox

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
		self.resize(800, 600)
		label=QLabel("Main APP", self)


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
