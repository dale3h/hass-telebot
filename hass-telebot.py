#!/usr/bin/python3

import time
import random
import datetime
import telepot
import argparse
from configobj import ConfigObj
import homeassistant.remote as remote

# these are for restarting the script
import os
import sys
import psutil
import logging

FORCE_RESTART = False
FORCE_SHUTDOWN = False
RESTART_CHAT_ID = None

def restart_program(chat_id=None):
    """Restarts the current program, with file objects and descriptors
       cleanup
    """

    try:
        p = psutil.Process(os.getpid())
        for handler in p.connections():
            os.close(handler.fd)
    except (Exception, e):
        logging.error(e)

    python = sys.executable
    args = sys.argv

    while len(args) < 3:
        args.append('')
    args[2] = '--announce=' + (str(chat_id) if chat_id is not None else '')

    os.execl(python, python, *args)

# calls the HASS API to get the state of an entity
# need to change this so you can pass in entity type so
#   we can get the right attributes for display
def get_state(entity_id, readable):
    print(entity_id)
    entity = remote.get_state(api, entity_id)
    if (readable == 'true'):
        state = format('{} is {}.'.format(entity.attributes['friendly_name'],
                                          entity.state))
    else:
        state = entity.state
    print(state)
    return state

# sends the location from any entity
def send_location(chat_id, entity_id):
    print(entity_id)
    entity = remote.get_state(api, entity_id)
    if (entity.state != 'home' and
            'latitude' in entity.attributes and
            'longitude' in entity.attributes):
        latitude = float(entity.attributes['latitude'])
        longitude = float(entity.attributes['longitude'])

        bot.sendLocation(chat_id=chat_id,
                         latitude=latitude, longitude=longitude)

# calls a HASS service
def service_call(domain, service, payload):
    remote.call_service(api, domain, service, payload)

def refresh_services():
    services = remote.get_services(api)
    for service in services:
        print(service['domain'])
#         print(service['services'])

def handle(message):
    (content_type, chat_type, chat_id,
        username, command) = parse_command(message)

    print('Content Type:', content_type,
          '| Chat Type:', chat_type,
          '| Chat ID:', chat_id,
          '| Username:', username,
          '| Command:', command)

    print('Message:', message)

    # we only want to process text messages from our specified chat
    if (content_type == 'text' and
        command[0] == '/' and
        str(chat_id) in allowed_chat_ids):
        if username.lower() in map(str.lower, allowed_users):
            cmd.handle(message)
        else:
            print('Unauthorized User:', username)
            bot.sendMessage(chat_id, deny_message().format(username))
    else:
        print('Unauthorized Chat ID:', chat_id)

def parse_command(message):
    content_type, chat_type, chat_id = telepot.glance(message)

    username = message['from']['username']
    command = message['text'].split('@', 1)[0]

#     if command[0] != '/':
#         return None

    return (content_type, chat_type, chat_id,
            username, command)

def deny_message():
    return random.choice([
        "You cannot control me @{}!",
        "Don't tell me what to do @{}!",
        "You are definitely not my father, @{}.",
        "@{} go fetch my master and try again.",
        "Go to hell @{}!",
        "Someone please help @{} find my owner.",
        "@{} is a window licker.",
        "@{} is a mouth breather.",
        "I wonder how many times @{} was dropped on their head as a child."
    ])

class BotCommand(telepot.Bot):
    def __init__(self, bot):
        self._bot = bot
        self._commands = []

    def command(f):
        f.command_desc = f.__doc__
        return f

    def get_commands(self):
        if not self._commands:
            for command in dir(self):
                method = self.get_command(command)
                if method is not None:
                    self._commands.append(method)
        return self._commands

    def get_command(self, command):
        if command[:2] == '__' or not hasattr(self, command):
            return None

        method = getattr(self, command)
        if (hasattr(method, 'command_desc') and
            callable(getattr(self, command))):
            return method
        return None

    def call_command(self, command, message):
        method = self.get_command(command)
        if method is not None:
            method(message)
        else:
            self.respond('Unrecognized command. Say what?')

    def respond(self, response, **kwargs):
        _, _, chat_id, _, _ = parse_command(self.message)
        self._bot.sendMessage(chat_id, response, **kwargs)

    def deny(self):
        _, _, _, username, _ = parse_command(self.message)
        self.respond(deny_message().format(username))

    def is_admin(self, username=None):
        global admins

        if username is None:
            _, _, _, username, _ = parse_command(self.message)

        if username.lower() in map(str.lower, admins):
            return True
        else:
            self.deny()
        return False

    def handle(self, message):
        self.message = message
        (content_type, chat_type, chat_id,
            username, command) = parse_command(self.message)
        command = command[1:]
        self.call_command(command, self.message)

    @command
    def help(self, message, **kwargs):
        """show command list"""
        command_list = '\n'.join(['/{} - {}'.format(command.__name__, command.command_desc) for command in self.get_commands() if command.__name__ != 'help'])
        self.respond("I can help you control Home Assistant and keep you " + \
                     "updated on the status of your home.\n\nYou can " + \
                     "control me by sending these commands:\n\n" + \
                     command_list)

    @command
    def commandlist(self, message, **kwargs):
        """list of all available commands"""
        command_list = '\n'.join(['{} - {}'.format(command.__name__, command.command_desc) for command in self.get_commands() if command.__name__ != 'commandlist'])
        self.respond("Copy and paste to @Botfather " + \
                     "to set your commands:\n\n" + \
                     command_list)

    @command
    def stop(self, message, **kwargs):
        """stop the bot"""
        if not self.is_admin():
            return False
        self.respond('Goodbye for now!')
        global FORCE_SHUTDOWN
        FORCE_SHUTDOWN = True

    @command
    def restart(self, message, **kwargs):
        """restart the bot"""
        if not self.is_admin():
            return False

        self.respond('I will be right back!')

        global FORCE_RESTART
        global RESTART_CHAT_ID

        FORCE_RESTART = True
        _, _, RESTART_CHAT_ID, _, _ = parse_command(message)

    @command
    def rude(self, message, **kwargs):
        """get a rude response"""
        self.deny()

    @command
    def roll(self, message, **kwargs):
        """roll a 6-sided die"""
        self.respond(random.randint(1, 6))

    @command
    def time(self, message, **kwargs):
        """current time"""
        self.respond(str(datetime.datetime.now()))

    @command
    def start(self, message, **kwargs):
        """friendly welcome message"""
        self.respond('hola!')

    @command
    def refresh(self, message, **kwargs):
        """refresh service list"""
        refresh_services()
        self.respond('Service list refreshed')

    @command
    def domains(self, message, **kwargs):
        """list current domains"""
        if (services is None):
            services = remote.get_services(api)

        domain_str = ''
        for service in services:
            domain_str = domain_str + service['domain'] + '\n'
        self.respond(domain_str)

    @command
    def browsedomains(self, message, **kwargs):
        """dynamically browse domains"""

        keyboard = []
        for service in services:
            key_item = [{'text': service['domain']}]
            keyboard.append(key_item)

        replymarkup = {
            'keyboard': keyboard,
            'resize_keyboard': True,
            'one_time_keyboard': True
        }
        self.respond('Pick a domain....', reply_markup=replymarkup)

    @command
    def states(self, message, **kwargs):
        """see the state of your favorite entities"""

        _, _, chat_id, _, _ = parse_command(self.message)

        for s in fav_entities:
            state = get_state(s, 'true')
            self.respond(state)
            send_location(chat_id, s)

    @command
    def armhome(self, message, **kwargs):
        """arm in home mode"""

        payload = {'code': ha_alarm_code}

        try:
            service_call('alarm_control_panel', 'alarm_arm_home', payload)
            self.respond('Home alarm mode should be pending')
        except:
            self.respond('An unknown error occurred')

    @command
    def armaway(self, message, **kwargs):
        """arm in away mode"""

        payload = {'code': ha_alarm_code}
        service_call('alarm_control_panel', 'alarm_arm_away', payload)
        self.respond('Away alarm mode should be pending')

    @command
    def disarm(self, message, **kwargs):
        """disarm the alarm"""

        payload = {'code': ha_alarm_code}
        service_call('alarm_control_panel', 'alarm_disarm', payload)
        self.respond('You are welcome!')

    @command
    def alarm(self, message, **kwargs):
        """alarm settings"""

        # check the current state of the alarm so
        #   we can decide what options to show
        alarm_state = get_state(ha_alarm_entity, 'false')
        if (alarm_state == 'disarmed'):
            keyboard = [[{'text': '/armhome'}], [{'text': '/armaway'}]]
        else:
            keyboard = [[{'text': '/disarm'}]]

        replymarkup = {
            'keyboard': keyboard,
            'resize_keyboard': True,
            'one_time_keyboard': True
        }
        self.respond('Alarm currently ' + alarm_state +
                     '.\nPlease choose an option:', reply_markup=replymarkup)

    @command
    def menu(self, message, **kwargs):
        """list of other commands"""

        replymarkup = {
            'keyboard': [[{'text': '/alarm'}],
                         [{'text': '/states'}],
                         [{'text': '/roll'}]],
            'resize_keyboard': True,
            'one_time_keyboard': True
        }
        self.respond('Please choose an option...', reply_markup=replymarkup)


# Get command line args
parser = argparse.ArgumentParser()

parser.add_argument('config', help='full path to config file', type=str)
# parser.add_argument('-c', '--config', help='full path to config file', type=str, default='hass-telebot.conf')
parser.add_argument('-a', '--announce', help='chat ID to announce resurrection', type=str)

args = parser.parse_args()

config_file = args.config
announce_chat_id = args.announce

# Read Config File
config = ConfigObj(config_file, file_error=True)

ha_url = config['ha_url']
ha_key = config['ha_key']
ha_port = config['ha_port']
ha_ssl = config['ha_ssl']
ha_alarm_entity = config['ha_alarm_entity']
ha_alarm_code = config['ha_alarm_code']
bot_token = config['bot_token']
allowed_chat_ids = config['allowed_chat_ids']
allowed_users = config['allowed_users']
admins = config['admins']
fav_entities = config['fav_entities']

if not isinstance(allowed_chat_ids, list):
    allowed_chat_ids = [allowed_chat_ids]
if not isinstance(allowed_users, list):
    allowed_users = [allowed_users]
if not isinstance(admins, list):
    admins = [admins]
if not isinstance(fav_entities, list):
    fav_entities = [fav_entities]

# instance the API connection to HASS
api = remote.API(ha_url, ha_key, ha_port, ha_ssl)
validated = remote.validate_api(api)
if str(validated) != 'ok':
    print('API Validation Failed:', validated)

# instance the Telegram bot
bot = telepot.Bot(bot_token)

cmd = BotCommand(bot)
bot.message_loop(handle)
print('I am listening...')

if announce_chat_id:
    print('Announcing restart to chat ID', announce_chat_id)
    bot.sendMessage(announce_chat_id, 'Okay, I am back now :)')

while not FORCE_RESTART:
    if FORCE_SHUTDOWN:
        sys.exit()
    time.sleep(1)

print('Restarting...')
restart_program(RESTART_CHAT_ID)
