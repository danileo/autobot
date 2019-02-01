#!/usr/bin/env python

# python utility modules
import configparser
import random

import sys
import os
sys.path.append(os.path.join(os.path.abspath('.'), 'env/lib/site-packages'))

# google cloud services
from google.cloud import datastore
import google.auth.exceptions
from flask import Flask, request

# telegram
import telegram
from telegram.ext import Dispatcher, CommandHandler, MessageHandler
from telegram.ext.filters import Filters

# linear programming solver
import pulp

# additional local modules
import mod_milano

# start webpages handler
app = Flask(__name__)

# config init
config = configparser.ConfigParser()
config.read('config.ini')
TELEGRAM_TOKEN = config['DEFAULT']['telegram_token']
HOOK_ADDRESS = config['DEFAULT']['hook_address']
BOT_URL = config['DEFAULT']['bot_url']

# Telegram init
bot = telegram.Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# google datastore init
try:
	dsclient = datastore.Client()
except google.auth.exceptions.DefaultCredentialsError as exc:
	pass


##########################
#  DATASTORE OPERATIONS  #
##########################

def put_pref_ds(chat_id, person_id, name, pref, num_seats=5):
	anc_key = dsclient.key('Chat', chat_id)
	anc = datastore.Entity(key=anc_key)
	dsclient.put(anc)

	# The Cloud Datastore key for the new entity
	rec_key = dsclient.key('Chat', chat_id, 'Person', person_id)

	# Prepares the new entity
	rec = datastore.Entity(key=rec_key)
	rec['name'] = name
	rec['preference'] = pref
	rec['seats'] = num_seats

	# Saves the entity
	dsclient.put(rec)


def get_results(chat_id):
	ancestor = dsclient.key('Chat', chat_id)
	query = dsclient.query(kind='Person', ancestor=ancestor)
	query.add_filter('preference', '=', 'CAR')
	cars_list = list(query.fetch())
	num_cars = len(cars_list)
	cars_list_divided = [[] for i in range(0, 10)]
	for car in cars_list:
		cars_list_divided[car['seats'] - 1].append(car)
	num_cars_divided = [len(c) for c in cars_list_divided]

	query = dsclient.query(kind='Person', ancestor=ancestor)
	query.add_filter('preference', '=', 'LIFT')
	lifts_list = list(query.fetch())
	num_lifts = len(lifts_list)

	query = dsclient.query(kind='Person', ancestor=ancestor)
	query.add_filter('preference', '=', 'POSSIBLY_LIFT')
	poss_lifts_list = list(query.fetch())
	num_poss_lifts = len(poss_lifts_list)

	available_seats = sum(
		[(i + 1) * n for i, n in enumerate(num_cars_divided)])

	if num_cars + num_lifts + num_poss_lifts == 0:
		return "Non sono stati registrati partecipanti."

	if available_seats < num_cars + num_lifts:
		missing_seats = num_cars + num_lifts - available_seats
		if missing_seats > 1:
			msg = "Non ci sono abbastanza auto: rimangono " + \
				str(missing_seats) + " persone a piedi."
		else:
			msg = "Non ci sono abbastanza auto: rimane una persona a piedi."
		return msg

	elif available_seats <= num_cars + num_lifts + num_poss_lifts:
		num_seats_left = available_seats - num_cars - num_lifts

		if num_seats_left >= num_poss_lifts:
			people_poss_lifts = poss_lifts_list
		else:
			people_poss_lifts = random.sample(poss_lifts_list, num_seats_left)

		msg = "Auto necessarie: " + \
			(", ".join([u['name'] for u in cars_list])) + "."
		passengers = people_poss_lifts+lifts_list
		if passengers:
			msg += "\n" + str(len(passengers)) + " persone hanno il posto in auto: "
			msg += (", ".join([u['name'] for u in passengers]))
			msg += "."
		return msg

	else:
		prob = pulp.LpProblem("", pulp.LpMinimize)
		xvars = []
		for k in range(1, 11):
			xvars.append(
				pulp.LpVariable(chr(ord('a') + k), 0,
								num_cars_divided[k - 1], pulp.LpInteger))
		prob += xvars[0] + xvars[1] + xvars[2] + xvars[3] + xvars[4] + \
			xvars[5] + xvars[6] + xvars[7] + xvars[8] + xvars[9]
		prob += 1 * xvars[0] + 2 * xvars[1] + 3 * xvars[2] +\
			4 * xvars[3] + 5 * xvars[4] + 6 * xvars[5] + \
			7 * xvars[6] + 8 * xvars[7] + 9 * xvars[8] + 10 * \
			xvars[9] >= num_cars + num_lifts + num_poss_lifts
		prob.solve()
		num_cars_needed = [round(v.varValue) for v in prob.variables()]

		chosen_cars = []
		for i in range(0, len(num_cars_needed)):
			chosen_cars.extend(random.sample(
				cars_list_divided[i], num_cars_needed[i]))

		msg = "Auto necessarie: " + \
			(", ".join([u['name'] for u in chosen_cars])) + "."
		drivers_not_driving = [u for u in cars_list if u not in chosen_cars]
		passengers = drivers_not_driving+poss_lifts_list+lifts_list
		msg += "\nTutti hanno il posto in auto (" + str(len(passengers)) + " persone): "
		msg += (", ".join([u['name'] for u in passengers]))
		msg += "."
		return msg


def get_name(user):
	user_name = user.first_name
	if user.last_name is not None:
		user_name += " " + user.last_name
	elif user.username is not None:
		user_name += " " + user.username
	return user_name


def delete_records(chat_id):
	ancestor = dsclient.key('Chat', chat_id)
	query = dsclient.query(kind='Person', ancestor=ancestor)
	query.keys_only()
	records = query.fetch()
	keys = [r.key for r in records]
	dsclient.delete_multi(keys)


def delete_all_records():
	query = dsclient.query(kind='Person')
	query.keys_only()
	records = query.fetch()
	keys = [r.key for r in records]
	dsclient.delete_multi(keys)


#############################
#  CALLBACKS FOR WEBSERVER  #
#############################

@app.route(HOOK_ADDRESS, methods=['POST'])
def webhook_handler():
	if request.method == "POST":
		# retrieve the message in JSON and then transform it to Telegram object
		update = telegram.Update.de_json(request.get_json(force=True), bot)
		dispatcher.process_update(update)
	return 'ok'


@app.route('/set_webhook', methods=['GET', 'POST'])
def set_webhook():
	s = bot.setWebhook(BOT_URL + HOOK_ADDRESS)
	if s:
		return "webhook setup ok"
	else:
		return "webhook setup failed"


@app.route('/deleteprefs')
def deleteprefs():
	delete_all_records()
	return 'Records deleted.'


@app.route('/')
def index():
	return '.'


###############################
#  TELEGRAM COMMAND HANDLERS  #
###############################

def start(bot, update):
	bot.send_message(chat_id=update.message.chat_id,
					 text="I'm a bot, please talk to me!")


def sollecita(bot, update):
	sentences = ["<NAME>, VUOI CHE MUORO!? (di fame)",
				 "Tic toc, <NAME>, TIC TOC!",
				 "<NAME>, das war ein Befehl! Die Abfahrt war ein Befehl! Wer sind Sie, dass Sie es wagen, sich meinen Befehlen zu widersetzen? So weit ist es also gekommen...",
				 "Te dò un sciafon che te impituro sù pel muro. Che ore sono, <NAME>!?",
				 "You have the timeliness of a seasick crocodile, <NAME>. Now, given the choice between the two of you, I'd take the seasick crocodile!",
				 "Gentile <NAME>, MUOVI QUEL CULO! Un abbraccio."]
	sentencesTutti = ["VOLETE CHE MUORO!? (di fame)",
				 "Tic toc, gente, TIC TOC!",
				 "Das war ein Befehl! Die Abfahrt war ein Befehl! Wer sind Sie, dass Sie es wagen, sich meinen Befehlen zu widersetzen? So weit ist es also gekommen...",
				 "Ve dò un sciafon che ve impituro sù pel muro. Che ore sono!?",
				 "You have the timeliness of a seasick crocodile. Now, given the choice between the two of you, I'd take the seasick crocodile!",
				 "Gentilissimi, MUOVETE QUEL CULO! Un abbraccio."]
	origmsg = update.message.text.strip()
	if origmsg.find(" ") > 0:
		msg = origmsg[origmsg.find(" ") + 1:]
		msg = msg.strip()
		if msg=="tutti":
			sentence = random.choice(sentencesTutti)
		else:
			sentence = random.choice(sentences)
			sentence = sentence.replace("<NAME>", msg)
		bot.send_message(chat_id=update.message.chat_id, text=sentence)


def macchina(bot, update):
	user = update.message.from_user
	user_name = get_name(user)
	chat_id = update.message.chat_id

	origmsg = update.message.text.strip()
	if origmsg.find(" ") > 0:
		num_seats = int(origmsg[origmsg.find(" ") + 1:])
	else:
		num_seats = 5

	put_pref_ds(chat_id, user.id, user_name, "CAR", num_seats=num_seats)
	msg = (user_name + " ha la macchina.")
	bot.send_message(chat_id=chat_id, text=msg)


def posto(bot, update):
	user = update.message.from_user
	user_name = get_name(user)
	chat_id = update.message.chat_id

	put_pref_ds(chat_id, user.id, user_name, "LIFT")
	msg = ("A " + user_name + " serve un passaggio.")
	bot.send_message(chat_id=chat_id, text=msg)


def postoguest(bot, update):
	chat_id = update.message.chat_id
	# get the message and check if there is a name
	origmsg = update.message.text.strip()
	if origmsg.find(" ") > 0:
		msg = origmsg[origmsg.find(" ") + 1:]
		msg = msg.strip()
		user_name = msg
		put_pref_ds(chat_id, user_name, user_name, "LIFT")
		replyMsg = ("A " + user_name + " serve un passaggio.")
		bot.send_message(chat_id=chat_id, text=replyMsg)
	else:
		replyMsg = "Mi serve il nome dell'ospite"
		bot.send_message(chat_id=chat_id, text=replyMsg)


def pref_posto(bot, update):
	user = update.message.from_user
	user_name = get_name(user)
	chat_id = update.message.chat_id

	put_pref_ds(chat_id, user.id, user_name, "POSSIBLY_LIFT")
	msg = (user_name + " preferisce avere un passaggio.")
	bot.send_message(chat_id=chat_id, text=msg)


def bicicletta(bot, update):
	user = update.message.from_user
	user_name = get_name(user)
	chat_id = update.message.chat_id

	put_pref_ds(chat_id, user.id, user_name, "BIKE")
	msg = (user_name + " va in bicicletta.")
	bot.send_message(chat_id=chat_id, text=msg)


def status(bot, update):
	chat_id = update.message.chat_id
	bot.send_message(chat_id=chat_id, text=get_results(chat_id))


def reset(bot, update):
	chat_id = update.message.chat_id
	delete_records(chat_id)
	bot.send_message(chat_id=chat_id, text="Preferenze cancellate!")


def bot_help(bot, update):
	txt = "/auto o /macchina per indicare che si ha l'auto.\n"
	txt += "/posto per prenotare un posto.\n"
	txt += "/biciomacchina (o qualsiasi delle quattro combinazioni tra bici e (auto OR macchina) intervallate dalla lettera \"o\") per indicare che si preferirebbe un passaggio in auto ma si ha la bicicletta.\n"
	txt += "/bici per indicare che si va in bicicletta."
	txt += "/guest NomeGuest per aggiungere un ospite che vuole andare in macchina"

	bot.send_message(chat_id=update.message.chat_id, text=txt)


def milano(bot, update):
	verbs = mod_milano.get_milano()
	verb = ""
	while verb == "":
		verb = random.choice(verbs)
		if verb[-3:] == "ere":
			verb = verb[:-3] + "i"
		elif verb[-3:] == "ire":
			verb = verb[:-2] + "sci"
		elif verb[-3:] == "are":
			verb = verb[:-2]
		else:
			verb = ""
	msg = verb + "milano"
	bot.send_message(chat_id=update.message.chat_id, text=msg)


def murialdo(bot, update):
	insults = ["Quando Dio diede l'intelligenza all'umanità tu dov'eri? Al cesso!?",
	           "Sei cosi brutto che chi ti guarda vomita.",
	           "Sei cosi ignorante che pure i tuoi amici ti stanno lontano.",
	           "No.",
	           "Non capisco se sei cretino di tuo oppure hai studiato per esserlo.",
	           "Your are not allowed to do that. This incident will be reported.",
	           "Hold it up to the light --- not a brain in sight!",
	           "Take a stress pill and think things over.",
	           "Thou Foul Lump Of Deformity! (Shakespeare, Richard III)",
	           "Davvero? Il tuo QI è circa quello della temperatura ambiente." ]

	msg = random.choice(insults)
	bot.send_message(chat_id=update.message.chat_id, text=msg)


def unknown(bot, update):
	#update.message.reply_animation("CgADBAADoq0AAhEdZAfaW_NYik5pqAI")
	update.message.reply_text("???")


# Hook commands to command handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("sollecita", sollecita))
dispatcher.add_handler(CommandHandler("macchina", macchina))
dispatcher.add_handler(CommandHandler("auto", macchina))
dispatcher.add_handler(CommandHandler("posto", posto))
dispatcher.add_handler(CommandHandler("macchinaobici", pref_posto))
dispatcher.add_handler(CommandHandler("biciomacchina", pref_posto))
dispatcher.add_handler(CommandHandler("autoobici", pref_posto))
dispatcher.add_handler(CommandHandler("bicioauto", pref_posto))
dispatcher.add_handler(CommandHandler("bici", bicicletta))
dispatcher.add_handler(CommandHandler("bicicletta", bicicletta))
dispatcher.add_handler(CommandHandler("status", status))
dispatcher.add_handler(CommandHandler("milano", milano))
dispatcher.add_handler(CommandHandler("help", bot_help))
dispatcher.add_handler(CommandHandler("guest", postoguest))
dispatcher.add_handler(CommandHandler("murialdo", murialdo))
dispatcher.add_handler(CommandHandler("reset", reset))
dispatcher.add_handler(MessageHandler(Filters.command, unknown))
