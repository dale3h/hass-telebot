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

EXIT_CODE = None

__version__ = '0.2.1'

# calls the HASS API to get the state of an entity
# need to change this so you can pass in entity type so
#   we can get the right attributes for display
def get_state(entity_id, readable=False):
    print(entity_id)
    entity = remote.get_state(api, entity_id)

    if entity is not None:
        if readable:
            state = format('{} is {}.'.format(
                entity.attributes['friendly_name'],
                entity.state))
        else:
            state = entity.state
        return state
    return None

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

def get_services(refresh=False):
    global services

    try:
        services
    except NameError:
        services = None

    if refresh or services is None:
        services = remote.get_services(api)

    return services

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
        str(chat_id) in config.get('allowed_chat_ids', [])):
        if username.lower() in map(str.lower, config.get('allowed_users', [])):
            try:
                cmd.handle(message)
            except telepot.exception.StopListening:
                global EXIT_CODE
                if EXIT_CODE is None:
                    EXIT_CODE = 0
                pass
        else:
            print('Unauthorized User:', username)
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
        self._denylist = []

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

    def deny(self, insult=False):
        _, _, _, username, _ = parse_command(self.message)

        if insult:
            self.respond(deny_message().format(username))
        else:
            print('Unauthorized User:', username)
            if username.lower() not in self._denylist:
                self._denylist.append(username.lower())
                self.respond(deny_message().format(username))

    def is_admin(self, username=None):
        if username is None:
            _, _, _, username, _ = parse_command(self.message)

        if username.lower() in map(str.lower, config.get('admins', [])):
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

        global EXIT_CODE
        EXIT_CODE = 0

        raise telepot.exception.StopListening

    @command
    def restart(self, message, **kwargs):
        """restart the bot"""
        if not self.is_admin():
            return False

        self.respond('I will be right back!')

        global EXIT_CODE
        _, _, EXIT_CODE, _, _ = parse_command(message)

        raise telepot.exception.StopListening

    @command
    def insult(self, message, **kwargs):
        """get insulted"""
        self.deny(True)

    @command
    def roll(self, message, **kwargs):
        """roll a 6-sided die"""
        self.respond('I rolled a die and got %i.' % random.randint(1, 6))

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
        get_services(True)
        self.respond('Service list refreshed')

    @command
    def domains(self, message, **kwargs):
        """list current domains"""
        services = get_services()

        domain_str = ''
        for service in services:
            domain_str = domain_str + service['domain'] + '\n'
        self.respond(domain_str)

    @command
    def browsedomains(self, message, **kwargs):
        """dynamically browse domains"""
        services = get_services()

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

        fav_entities = config.get('fav_entities', [])
        for s in fav_entities:
            state = get_state(s, True)
            self.respond(state)
            send_location(chat_id, s)

    @command
    def armhome(self, message, **kwargs):
        """arm in home mode"""

        try:
            payload = {'code': config.get('ha_alarm_code')}
            service_call('alarm_control_panel', 'alarm_arm_home', payload)
            self.respond('Home alarm mode should be pending')
        except:
            self.respond('I could not arm the alarm.')

    @command
    def armaway(self, message, **kwargs):
        """arm in away mode"""

        try:
            payload = {'code': config.get('ha_alarm_code')}
            service_call('alarm_control_panel', 'alarm_arm_away', payload)
            self.respond('Away alarm mode should be pending')
        except:
            self.respond('I could not arm the alarm.')

    @command
    def disarm(self, message, **kwargs):
        """disarm the alarm"""

        try:
            payload = {'code': config.get('ha_alarm_code')}
            service_call('alarm_control_panel', 'alarm_disarm', payload)
            self.respond('You are welcome!')
        except:
            self.respond('I could not disarm the alarm.')

    @command
    def alarm(self, message, **kwargs):
        """alarm settings"""

        # check the current state of the alarm so
        #   we can decide what options to show
        alarm_state = get_state(config.get('ha_alarm_entity'))

        if alarm_state is None:
            self.respond('I could not get the current status of the alarm.')
            return

        if alarm_state == 'disarmed':
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

def get_arguments():
    parser = argparse.ArgumentParser(
        description='Telegram Bot for Home Assistant')

    parser.add_argument('--version', action='version', version=__version__)

    parser.add_argument(
        '-c', '--config',
        metavar='path_to_config_dir',
        default='{}/hass-telebot.conf'.format(os.path.dirname(os.path.realpath(__file__))),
        help='Directory that contains the bot configuration')

    arguments = parser.parse_args()
    return arguments

def get_config(config_file=None):
    # Read Config File
    config = ConfigObj(config_file, file_error=True)

    config.setdefault('ha_url', 'localhost')
    config.setdefault('ha_key', '')
    config.setdefault('ha_port', '8123')
    config.setdefault('ha_ssl', False)
    config.setdefault('ha_alarm_entity', '')
    config.setdefault('ha_alarm_code', '')
    config.setdefault('bot_token', '')
    config.setdefault('allowed_chat_ids', [])
    config.setdefault('allowed_users', [])
    config.setdefault('admins', [])
    config.setdefault('fav_entities', [])

    if not isinstance(config.get('allowed_chat_ids'), list):
        config['allowed_chat_ids'] = [config.get('allowed_chat_ids')]
    if not isinstance(config.get('allowed_users'), list):
        config['allowed_users'] = [config.get('allowed_users')]
    if not isinstance(config.get('admins'), list):
        config['admins'] = [config.get('admins')]
    if not isinstance(config.get('fav_entities'), list):
        config['fav_entities'] = [config.get('fav_entities')]

    return config

def load_config():
    global args, config

    try:
        config
    except NameError:
        args = get_arguments()
        config = get_config(args.config)

def load_hass_api():
    """instantiate the API connection to HASS"""
    global api
    api = remote.API(config.get('ha_url'), config.get('ha_key'), config.get('ha_port'), config.get('ha_ssl'))
    validated = remote.validate_api(api)
    if str(validated) != 'ok':
        print('API Validation Failed:', validated)

def load_bot():
    """instantiate the Telegram bot"""
    load_config()
    bot = telepot.Bot(config.get('bot_token'))
    bot.message_loop(handle)
    print('I am listening...')
    return bot

def start_bot(bot_ref, announce_chat_id=None):
    global config, api, bot, cmd

    load_config()
    load_hass_api()

    bot = bot_ref
    cmd = BotCommand(bot)

    if announce_chat_id is not None:
        print('Announcing return to chat ID', announce_chat_id)
        bot.sendMessage(announce_chat_id, 'Okay, I am back now :)')

    while EXIT_CODE is None:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            print()
            try:
                sys.exit(0)
            except SystemExit:
                os._exit(0)

    if EXIT_CODE != 0:
        print('Restarting bot...')
        return EXIT_CODE

    return None
