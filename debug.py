import main

from google.cloud import datastore
import google.auth.credentials
import mock

credentials = mock.Mock(spec=google.auth.credentials.Credentials)
main.dsclient = datastore.Client(credentials=credentials)

class UpdateMock:
	class Message:
		chat_id = 1

		class FromUser:
			first_name = ""
			last_name = ""
			id = 1
		from_user = FromUser()
		text = ""
	message = Message()

def send_message_mock(
	chat_id, text, parse_mode=None,
	disable_web_page_preview=None, disable_notification=False,
	reply_to_message_id=None, reply_markup=None, timeout=None, **kwargs):
		print("RETURNED MESSAGE: " + text)
main.bot.send_message = send_message_mock

print("The app is started in debug mode.")
update = UpdateMock()
main.start(main.bot, update)

update.message.from_user.first_name = "hola"
update.message.from_user.last_name = "macchina"
update.message.text = "/auto 3"
main.macchina(main.bot, update)

update.message.text = "/postoguest tizio"
main.postoguest(main.bot, update)

main.status(main.bot, update)
