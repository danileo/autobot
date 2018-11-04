#!/usr/bin/env python

# google cloud services
import sys, os
sys.path.append(os.path.join(os.path.abspath('.'), 'env/lib/site-packages'))
from flask import Flask, request
from google.cloud import datastore

# python utility modules
import configparser
import random, math

# telegram
import telegram
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters

# linear programming solver
import pulp

# additional local modules
import mod_milano

# verify if we are testing locally or not
IS_DEV = (__name__ == '__main__')

# start webpages handler
app = Flask(__name__)

# config init
config=configparser.ConfigParser()
config.read('config.ini')
TELEGRAM_TOKEN=config['DEFAULT']['telegram_token']
HOOK_ADDRESS=config['DEFAULT']['hook_address']
BOT_URL=config['DEFAULT']['bot_url']
DATASTORE_PROJECT=config['DEFAULT']['datastore_project']

# Telegram init
global bot
bot = telegram.Bot(token=TELEGRAM_TOKEN)
global dispatcher
dispatcher = Dispatcher(bot, None, workers=0)
if IS_DEV:
	class UpdateMock:
		class Message:
			chat_id = 0
		message = Message()
	def send_message_mock(chat_id, text, parse_mode=None, disable_web_page_preview=None, disable_notification=False,
		reply_to_message_id=None, reply_markup=None, timeout=None, **kwargs):
		print("RETURNED MESSAGE: "+text)
	bot.send_message = send_message_mock

# google datastore init
if IS_DEV:
    import mock
    import google.auth.credentials
    credentials = mock.Mock(spec=google.auth.credentials.Credentials)
    dsclient = datastore.Client(DATASTORE_PROJECT, credentials=credentials)
else:
    dsclient = datastore.Client(DATASTORE_PROJECT)


##########################
## DATASTORE OPERATIONS ##
##########################

def put_pref_ds(person_id,name,pref,num_seats=5):
	# The Cloud Datastore key for the new entity
	rec_key = dsclient.key('Person', person_id)

	# Prepares the new entity
	rec = datastore.Entity(key=rec_key)
	rec['name'] = name
	rec['preference'] = pref
	rec['seats'] = num_seats

	# Saves the entity
	dsclient.put(rec)

def get_results():
	query=dsclient.query(kind='Person')
	query.add_filter('preference','=','CAR')
	cars_list=list(query.fetch())
	num_cars=len(cars_list)
	cars_list_divided=[[] for i in range(0,10)]
	for car in cars_list:
		cars_list_divided[car['seats']-1].append(car)
	num_cars_divided=[len(c) for c in cars_list_divided]
	
	query=dsclient.query(kind='Person')
	query.add_filter('preference','=','LIFT')
	lifts_list=list(query.fetch())
	num_lifts=len(lifts_list)
	
	query=dsclient.query(kind='Person')
	query.add_filter('preference','=','POSSIBLY_LIFT')
	poss_lifts_list=list(query.fetch())
	num_poss_lifts=len(poss_lifts_list)
	
	available_seats=sum([(i+1)*n for i,n in enumerate(num_cars_divided)])
	
	if(available_seats<num_cars+num_lifts):
		missing_seats=num_cars+num_lifts-available_seats
		if(missing_seats>1):
			msg="Non ci sono abbastanza auto: rimangono "+str(missing_seats)+" persone a piedi."
		else:
			msg="Non ci sono abbastanza auto: rimane una persona a piedi."
		return msg
	
	elif(available_seats<=num_cars+num_lifts+num_poss_lifts):
		num_seats_left=available_seats-num_cars-num_lifts
		
		if(num_seats_left>=num_poss_lifts):
			people_poss_lifts=poss_lifts_list
		else:
			people_poss_lifts=random.sample(poss_lifts_list,num_seats_left)
		
		msg="Auto necessarie: "+(", ".join([u['name'] for u in cars_list]))+"."
		if(len(people_poss_lifts)>0):
			msg+="\nCiclisti che hanno il posto in auto: "+(", ".join([u['name'] for u in people_poss_lifts]))+"."
		return msg
	
	else:
		prob=pulp.LpProblem("",pulp.LpMinimize)
		xvars=[]
		for k in range(1,11):
			xvars.append(pulp.LpVariable(chr(ord('a')+k),0,num_cars_divided[k-1],pulp.LpInteger))
		prob += xvars[0]+xvars[1]+xvars[2]+xvars[3]+xvars[4]+xvars[5]+xvars[6]+xvars[7]+xvars[8]+xvars[9]
		prob += 1*xvars[0]+2*xvars[1]+3*xvars[2]+4*xvars[3]+5*xvars[4]+6*xvars[5]+7*xvars[6]+8*xvars[7]+9*xvars[8]+10*xvars[9] >= num_cars+num_lifts+num_poss_lifts
		prob.solve()
		num_cars_needed=[ round(v.varValue) for v in prob.variables() ]
		
		chosen_cars=[]
		for i in range(0,len(num_cars_needed)):
			chosen_cars.extend(random.sample(cars_list_divided[i],num_cars_needed[i]))
		
		msg="Auto necessarie: "+(", ".join([u['name'] for u in chosen_cars]))+"."
		msg+="\nTutti hanno il posto in auto."
		return msg


#############################
## CALLBACKS FOR WEBSERVER ##
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
	s = bot.setWebhook(BOT_URL+HOOK_ADDRESS)
	if s:
		return "webhook setup ok"
	else:
		return "webhook setup failed"


@app.route('/')
def index():
	return '.' 


###############################
## TELEGRAM COMMAND HANDLERS ##
###############################

def start(bot,update):
	bot.send_message(chat_id=update.message.chat_id, text="I'm a bot, please talk to me!")

def sollecita(bot,update):
	sentences=["<NAME>, VUOI CHE MUORO!? (di fame)",
			"Tic toc, <NAME>, TIC TOC!",
			"<NAME>, das war ein Befehl! Die Abfahrt war ein Befehl! Wer sind Sie, dass Sie es wagen, sich meinen Befehlen zu widersetzen? So weit ist es also gekommen...",
			"Te dò un sciafon che te impituro sù pel muro. Che ore sono, <NAME>!?",
			"You have the timeliness of a seasick crocodile, <NAME>. Now, given the choice between the two of you, I'd take the seasick crocodile!",
			"Gentile <NAME>, MUOVI QUEL CULO! Un abbraccio."]
	sentence=random.choice(sentences)
	origmsg=update.message.text.strip()
	if(origmsg.find(" ")>0):
		msg=origmsg[origmsg.find(" ")+1:]
		msg=msg.strip()
		sentence=sentence.replace("<NAME>",msg)
		bot.send_message(chat_id=update.message.chat_id, text=sentence)

def get_name(user):
	user_name=user.first_name
	if user.last_name is not None:
		user_name+=" "+user.last_name
	elif user.username is not None:
		user_name+=" "+user.username
	return user_name

def macchina(bot,update):
	user=update.message.from_user
	user_name=get_name(user)
	
	origmsg=update.message.text.strip()
	if(origmsg.find(" ")>0):
		num_seats=int(origmsg[origmsg.find(" ")+1:])
	else:
		num_seats=5
	
	put_pref_ds(user.id,user_name,"CAR",num_seats=num_seats)
	msg=(user_name+" ha la macchina.")
	bot.send_message(chat_id=update.message.chat_id, text=msg)

def posto(bot,update):
	user=update.message.from_user
	user_name=get_name(user)
	
	put_pref_ds(user.id,user_name,"LIFT")
	msg=("A "+user_name+" serve un passaggio.")
	bot.send_message(chat_id=update.message.chat_id, text=msg)

def pref_posto(bot,update):
	user=update.message.from_user
	user_name=get_name(user)
	
	put_pref_ds(user.id,user_name,"POSSIBLY_LIFT")
	msg=(user_name+" preferisce avere un passaggio.")
	bot.send_message(chat_id=update.message.chat_id, text=msg)

def bicicletta(bot,update):
	user=update.message.from_user
	user_name=get_name(user)
	
	put_pref_ds(user.id,user_name,"BIKE")
	msg=(user_name+" va in bicicletta.")
	bot.send_message(chat_id=update.message.chat_id, text=msg)

def status(bot,update):
	bot.send_message(chat_id=update.message.chat_id, text=get_results())

def bot_help(bot,update):
	txt="/auto o /macchina per indicare che si ha l'auto.\n"
	txt+="/posto per prenotare un posto.\n"
	txt+="/biciomacchina (o qualsiasi delle quattro combinazioni tra bici e (auto OR macchina) intervallate dalla lettera \"o\") per indicare che si preferirebbe un passaggio in auto ma si ha la bicicletta.\n"
	txt+="/bici per indicare che si va in bicicletta."
	
	bot.send_message(chat_id=update.message.chat_id, text=txt)

def milano(bot,update):
	verbs = mod_milano.get_milano()
	verb=""
	while verb=="":
		verb=random.choice(verbs)
		if(verb[-3:]=="ere"):
			verb=verb[:-3]+"i"
		elif(verb[-3:]=="ire"):
			verb=verb[:-2]+"sci"
		elif(verb[-3:]=="are"):
			verb=verb[:-2]
		else:
			verb=""
	msg=verb+"milano"
	bot.send_message(chat_id=update.message.chat_id, text=msg)


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

if __name__ == '__main__':
	print("The app is started in debug mode.")
