#!/usr/bin/python3

import os
import sys
from importlib import reload
import telebot

announce_chat_id = None
bot = None

if __name__ == '__main__':
    while True:
        if bot is None:
            bot = telebot.load_bot()

        announce_chat_id = telebot.start_bot(bot, announce_chat_id)

        if announce_chat_id is None:
            print('Shutting down bot...')
            break;

        reload(telebot)
