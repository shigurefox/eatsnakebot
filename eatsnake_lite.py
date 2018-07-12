#!/usr/bin/env python3
## coding=UTF-8
#
# Eatsnakebot: a simple Telegram bot variation of AFX_bot in Python
# Copyright (C) 2017 Shigurefox. <shigurefox@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import http
import json
import logging
import os
import random
import requests
import sqlite3
import string
import time
import telegram
import urllib
from collections import OrderedDict
from locdbhelper import locDBHelper


class Eatsnakebot:
    """
    This object represents a working Telegram bot.

    """
    def __init__(self,
                 conf_file_name = None,
                 **kwargs):
        # Base. ;)
        self.LAST_UPDATE_ID = None
        self.NOW_HANDLING_UPDATE_ID = None
        self.logger = logging.getLogger()
        self.bot = None
        self.config = None
        self.strs = None
        self.loc_list = []

        # Bot state
        self.is_running = True
        self.is_accepting_photos = False

        # Parse command line params
        self.log_fmt_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        arg_parser = argparse.ArgumentParser(description = 'Eatsnakebot, a simple Telegram bot in Python.')
        arg_parser.add_argument('-l', '--logfile', help='Logfile Name', action='store_true')

        args = arg_parser.parse_args()

        self.init_configuration(conf_file_name)
        self.init_l10n_strings()

        if args.logfile:
            logging.basicConfig( level=logging.DEBUG, format=self.log_fmt_str, filename=args.logfile)
        else:
            logging.basicConfig( level=logging.DEBUG, format=self.log_fmt_str)
        self.logger = logging.getLogger('NTUEatsnakebot')
        self.logger.setLevel(logging.DEBUG)

        # Telegram Bot Authorization Token
        self.bot = telegram.Bot(self.config['bot_token'])
        self.api_url = "https://api.telegram.org/bot{}/".format(self.config['bot_token'])
        self.register_callbacks()
        self.recognition_list = [132592798]


    def init_configuration(self,
                           file_name):
        """
        Initialize configuration.

        Arguments:
            file_name (str):
                Name of configuration file.
        """
        # Load Configuration
        if not file_name:
            file_name = os.path.join(path, "config.json")

        try:
            with open(file_name, 'r', encoding = 'utf8') as f:
                self.config = json.loads(f.read())

            # Check Configuration
            configs_check = ['strings_json', 'bot_token', 'loc_db', 'adm_ids']
            for c in configs_check:
                self.check_config_entry(c)

            list_configs_check = ['operational_chats', 'restricted_chats']
            for c in list_configs_check:
                self.check_config_entry_of_list(c)

            self.init_locdb()
            self.logger.debug('bot initialization successful')
        except FileNotFoundError:
            self.logger.exception('config file not found!')
            raise
        except ValueError:
            self.logger.exception('config read error or item missing!')
            raise
        except:
            raise

    def init_l10n_strings(self,
                          file_name = None):
        """
        Initialize L10N strings.

        Arguments:
            file_name (Optional[str]):
                Name of L10N strings file.
        """
        # Load L10N Strings (forced now)
        if not file_name:
            file_name = self.config['strings_json']
            if not file_name:
                raise Exception('L10N file not specified in neither config nor argument!')

        try:
            with open(self.config['strings_json'], 'r', encoding = 'utf8') as f:
                self.strs = json.loads(f.read())
        except:
            logging.exception('L10N Strings read error!')
            raise

    def check_config_entry(self,
                           name):
        """
        Check whether the config is sane.
        """
        if not self.config[name]:
            logging.error('config[\'{0}\'] is missing!'.format(name))
            raise ValueError

    def check_config_entry_of_list(self,
                                   name):
        """
        Check whether the list in config is sane, or init a empty one.
        """
        if not self.config[name]:
            self.config[name] = []

    def run(self):
        """
        Run the bot: start the loop to fetch updates and handle.
        """
        self.get_latest_update_id()
        self.recoverStatus = False

        while True:
            # This will be our global variable to keep the latest update_id when requesting
            # for updates. It starts with the latest update_id if available.
            try:
                if self.recoverStatus:
                    # try to reinit...
                    self.bot = telegram.Bot(self.config['bot_token'])
                    self.get_latest_update_id()
                    self.recoverStatus = False

                self.get_mesg()
            except KeyboardInterrupt:
                exit()
            except http.client.HTTPException:
                logging.exception('!!! EXCEPTION HAS OCCURRED !!!')
                self.recover()
            except urllib.error.HTTPError:
                logging.exception('!!! EXCEPTION HAS OCCURRED !!!')
                self.recover()
            except Exception as ex:
                logging.exception('!!! EXCEPTION HAS OCCURRED !!!')
                self.recover()

    def recover(self):
        """
        Recover the bot in next loop.
        """
        self.recoverStatus = True
        if self.NOW_HANDLING_UPDATE_ID:
            self.LAST_UPDATE_ID = self.NOW_HANDLING_UPDATE_ID + 1
        else:
            self.LAST_UPDATE_ID = self.LAST_UPDATE_ID + 1

    def get_mesg(self):
        """
        Fetch updates from server for further processes.
        """
        # Request updates after the last updated_id
        for update in self.bot.getUpdates(offset = self.LAST_UPDATE_ID, timeout = 10):
            self.logger.info('Update: ' + str(update));
            # chat_id is required to reply any message
            if update.edited_message:
                # Does NOT reply to edited messages
                nothing_todo = 1
            else:
                chat_id = update.message.chat_id
                message = update.message.text
                mesg_id = update.message.message_id
                user_id = update.message.from_user.id
                self.NOW_HANDLING_UPDATE_ID = update.update_id
                self.logger.debug('Now handling update: {0}'.format(self.NOW_HANDLING_UPDATE_ID))

                try:
                    if message:
                        # YOU SHALL NOT PASS!
                        # Only authorized group chats and users (admins) can access this bot.
                        if not self.do_augmented_auth(update.message.chat.id):
                            if '__FOR_RECOGNITION__' in message and not update.message.chat.id in self.recognition_list:
                                self.send_generic_mesg(chat_id, 'Please contact moderator to add following id into ACL.')
                                self.send_generic_mesg(chat_id, str(update.message.chat.id))
                                self.recognition_list.append(update.message.chat.id)
                            else:
                                self.logger.info('Access denied from: ' + str(update.message.chat.id))

                        # Status querying.
                        elif self.strs['q_status_kw'] in message:
                            if self.is_running:
                                self.send_generic_mesg(chat_id, self.strs['qr_status_t'], mesg_id)
                            else:
                                self.send_generic_mesg(chat_id, self.strs['qr_status_f'], mesg_id)

                        # Only admins can re-enable bot.
                        elif not self.is_running and message.startswith(self.strs['s_status_t_kw']) and self.do_adm_auth(user_id):
                            self.send_generic_mesg(chat_id, self.strs['sr_status_t_ok'], mesg_id)
                            self.init_locdb()
                            self.is_running = True

                        # Handle adm commands/common commands/eatsnake requests
                        elif self.is_running and self.do_operational_auth(update.message.chat.id):
                            # So, eatsnake?
                            if self.execute_callbacks(self.bot_callbacks, update):
                                nothing_todo = 1
                            # other...
                            else:
                                self.handle_response(update)
                        elif self.is_running:
                            self.logger.debug('Not handling updates.')
                        else:
                            self.logger.debug('Not running...')

                except:
                    if chat_id != None and mesg_id != None:
                        self.send_generic_mesg(chat_id, self.append_more_smiles('好像哪裡怪怪der '), mesg_id)
                    self.logger.exception('')

                # Updates global offset to get the new updates
                self.LAST_UPDATE_ID = self.NOW_HANDLING_UPDATE_ID + 1


    def get_latest_update_id(self):
        """
        Get latest update id from Telegram server.
        """
        try:
            updates = self.bot.getUpdates(timeout = 10)
            self.logger.debug('update length: {0}'.format(len(updates)))
            if len(updates) == 1:
                self.LAST_UPDATE_ID = updates[-1].update_id
            else:
                while(len(updates) > 1):
                    self.LAST_UPDATE_ID = updates[-1].update_id
                    updates = self.bot.getUpdates(offset=self.LAST_UPDATE_ID+1, timeout = 10)
                    self.logger.debug('update length: {0}'.format(len(updates)))
        except:
            self.logger.exception('!!! Get Last update ID Error !!!')

    def init_locdb(self):
        """
        Read all entries from self.loc_db.
        """
        self.logger.debug('Initializing geolocation database...')
        self.loc_db = locDBHelper(self.config['loc_db'])
        # c = self.loc_db.cur

        # TODO: use cursor to set type filters


    def send_generic_mesg(self,
                          chat_id,
                          text,
                          reply_to_message_id = None):
        """
        For sending simple messages only including text (in most cases.)
        """
        self.bot.sendMessage(chat_id = chat_id, text = text, reply_to_message_id = reply_to_message_id)

    def match_eatsnake(self,
                       update):
        mesg = update.message.text.lower()
        eatsnakekws = self.strs['q_eatsnake_kws']
        return True if any(x in mesg for x in eatsnakekws) else False

    def handle_eatsnake(self,
                        update):
        """
        Handles eatsnake requests.

        Args:
            update (telegram.update):
                Update object to handle.
        Returns:
            True when the command is handled, otherwise False.
        """
        chat_id = update.message.chat_id
        mesg = update.message.text
        mesg_id = update.message.message_id
        user_id = update.message.from_user.id

        # Put it into l10n file or dbhelper later?
        attr = [('name', "店家名稱"), ('pricerange', "價位"), ('mincharge', "低消"),
                ('address', "地址"), ('optime', "營業時間"), ('tags', "關鍵字"), ('other', "其他")]
        attr = OrderedDict(attr)

        # Generate a choice
        outmesg = "吃這間如何？ " + '\U0001F40D'
        choice = self.loc_db.get_choice()
        for x in attr:
            if choice[x] and choice[x] != '':
                outmesg += '\n' + attr[x] + '：' + str(choice[x])

        # Maybe not neat enough, but not gonna it for now :(
        lat = choice['latitude'] if choice['latitude'] else 25.017356
        lng = choice['longitude'] if choice['longitude'] else 121.539755

        self.send_generic_mesg(chat_id, outmesg, mesg_id)
        self.bot.sendLocation(chat_id = chat_id, latitude = lat, longitude = lng)

        # Hardcoded extras...
        if user_id == 77414661:
            self.send_generic_mesg(chat_id, "看看你的肚子，還吃？", mesg_id)

    def do_adm_auth(self,
                    id):
        """
        Returns:
            Presence of id in self.config['adm_ids'].
        """
        return id in self.config['adm_ids']

    def do_operational_auth(self,
                            id):
        """
        Returns:
            Presence of id in self.config['operational_chats'],
                              self.config['adm_ids']
        """
        return id in self.config['operational_chats'] \
               or id in self.config['adm_ids']

    def do_augmented_auth(self,
                          id):
        """
        Returns:
            Presence of id in self.config['operational_chats'],
                              self.config['adm_ids'],
                              self.config['restricted_chats'],
        """
        return id in self.config['operational_chats'] \
               or id in self.config['adm_ids'] \
               or id in self.config['restricted_chats'] \

    def append_more_smiles(self,
                           str,
                           rl = 1,
                           ru = 3):
        """
        Returns:
            str with smiles in amount of random(rl, ru) appended on the tail.
        """
        return str + '\U0001F603' * random.randint(rl, ru)

    def handle_adm_cmd(self,
                       update):
        """
        Handles all administrative commands.

        Args:
            update (telegram.update):
                Update object to handle.
        """
        chat_id = update.message.chat_id
        mesg = update.message.text.strip()
        mesg_id = update.message.message_id

        cmd_toks = [x.strip() for x in mesg.split(' ')]
        while '' in cmd_toks:
            cmd_toks.remove('')

        cmd_entity = cmd_toks[1].lower()
        self.logger.debug('cmd_entity: ' + cmd_entity)
        try:
            if cmd_entity == 'awoo':
                self.send_generic_mesg(chat_id, "Awoo? owo", mesg_id)
            elif cmd_entity == 'add':
                # Add new entries to database
                # TODO: make it a loop
                self.logger.debug("Adding a new entry.")
                name = cmd_toks[2]
                prange = cmd_toks[3]
                mch = cmd_toks[4]
                addr = cmd_toks[5]
                lat = cmd_toks[6]
                lng = cmd_toks[7]
                #if len(cmd_toks) > 8:
                #    tags = ""
                #    tags += cmd_toks[i] for i in range(8, len(cmd_toks))
                #args = (name, prange, mch, addr, lat, lng)
                if self.loc_db.add_item(name, prange, mch, addr, lat, lng):
                    self.send_generic_mesg(chat_id, self.strs['r_adm_add_ok'], mesg_id)
                else:
                    self.send_generic_mesg(chat_id, self.strs['r_adm_add_ng'], mesg_id)
            elif cmd_entity == 'rm':
                # Remove entry
                try:
                    self.logger.debug("Removing entry.")
                    if cmd_toks[2]:
                        self.loc_db.remove_item(cmd_toks[2])
                        self.send_generic_mesg(chat_id, self.strs['r_adm_rm_ok'], mesg_id)
                    else:
                        self.send_generic_mesg(chat_id, self.strs['r_adm_rm_ng'], mesg_id)
                except:
                    self.send_generic_mesg(chat_id, self.strs['r_adm_rm_ng'], mesg_id)
            elif cmd_entity == 'help':
                # Show help message
                try:
                    if cmd_toks[2]:
                        self.send_generic_mesg(chat_id, "Usage: " + self.strs['i_usg_adm_{}'.format(cmd_toks[2])], mesg_id)
                except:
                    outmesg = self.strs['i_usg_adm_help'] + '\nSupported commands: ' + self.strs['i_adm_cmdlist']
                    self.send_generic_mesg(chat_id, outmesg, mesg_id)
            else:
                # Unknown command
                outmesg = self.strs['r_adm_unknown'] + '\nSupported commands: ' + self.strs['i_adm_cmdlist']
                self.send_generic_mesg(chat_id, outmesg, mesg_id)
        except:
            self.logger.debug("Encountered an error while handling adm command: {}.".format(cmd_entity))
            self.send_generic_mesg(chat_id, self.strs['i_adm_error'], mesg_id)

    def handle_cmd(self,
                   update):
        """
        Handles all common commands.

        Args:
            update (telegram.update):
                Update object to handle.
        Returns:
            True when the command is handled, otherwise False.
        """
        chat_id = update.message.chat_id
        restricted = not self.do_operational_auth(chat_id)
        mesg = update.message.text
        mesg_id = update.message.message_id
        mesg_low = mesg.lower().replace('@NTUEatsnakebot', '')

        if chat_id > 0:
            cmd_toks = [x.strip() for x in mesg.split(' ')]
            while '' in cmd_toks:
                cmd_toks.remove('')

            if mesg == '/crash':
                raise Exception('Crash!')
        else:
            outmesg = "No commands yet are supported for group chats."
            self.send_generic_mesg(chat_id, outmesg, mesg_id)
            return False

    def handle_response(self,
                      update):
        """
        Handles all typical responses.

        Args:
            update (telegram.update):
                Update object to handle.
        Returns:
            True when the command is handled, otherwise False.
        """
        chat_id = update.message.chat_id
        try:
            mesg = update.message.text
        except:
            mesg = update.edited_message.text
        mesg_id = update.message.message_id
        user_id = update.message.from_user.id
        mesg_low = mesg.lower()

        snakesticker = "CAADBAADQQsAArdZUgKNmzWicXfDmAI"

        if chat_id < 0 and '蛇' in mesg:
            self.bot.sendSticker(chat_id, snakesticker, reply_to_message_id = mesg_id)
            return True
        # only do things when receiving eatsnake requests for now...
        return False

    def set_is_running(self,
                       flag):
        """Assign flag to is_running."""
        self.is_running = flag

    def set_is_accepting_photos(self,
                                flag):
        """Assign flag to is_accepting_photos."""
        self.is_accepting_photos = flag

    @staticmethod
    def execute_callbacks(bcblist,
                          update):
        """Run registered callbacks."""
        for bcb in bcblist:
            if bcb.execute(update):
                return True
        return False

    def register_callbacks(self):
        """Register callbacks."""

        # For restricted chats, only restricted commands works.
        self.bot_callbacks_restricted = [
            self.BotCallback('call_cmd_handler_bcb',
                             self,
                             {'q_kw': '/'},
                             False,
                             lambda update: self.handle_cmd(update)),

        ]

        # For regular chats.
        self.bot_callbacks = [
            self.BotCallback('reload_kw_bcb',
                             self,
                             {'q_kw': self.strs['a_reload_kwlist_kw'],
                              'r_ok': self.strs['ar_reload_kwlist_ok'],
                              'r_ng': self.strs['ar_reload_kwlist_ng']},
                             True,
                             lambda update: self.init_locdb()),

            self.BotCallback('set_running_f_bcb',
                             self,
                             {'q_kw': self.strs['s_status_f_kw'],
                              'r_ok': self.strs['sr_status_f_ok'],
                              'r_ng': self.strs['sr_status_f_ng']},
                             True,
                             lambda update: self.set_is_running(False)),

            self.BotCallback('set_imgupload_t_bcb',
                             self,
                             {'q_kw': self.strs['s_imgupload_t_kw'],
                              'r_ok': self.strs['sr_imgupload_t_ok'],
                              'r_ng': self.strs['sr_imgupload_t_ng']},
                             True,
                             lambda update: self.set_is_accepting_photos(True)),

            self.BotCallback('set_imgupload_f_bcb',
                             self,
                             {'q_kw': self.strs['s_imgupload_f_kw'],
                              'r_ok': self.strs['sr_imgupload_f_ok'],
                              'r_ng': self.strs['sr_imgupload_f_ng']},
                             True,
                             lambda update: self.set_is_accepting_photos(False)),

            self.BotCallback('call_adm_cmd_handler_bcb',
                             self,
                             {'q_kw': '/adm'},
                             True,
                             lambda update: self.handle_adm_cmd(update)),

            self.BotCallback('call_cmd_handler_bcb',
                             self,
                             {'q_kw': '/'},
                             False,
                             lambda update: self.handle_cmd(update)),

            self.BotCallback('call_eatsnake_handler_bcb',
                             self,
                             {},
                             False,
                             lambda update: self.handle_eatsnake(update),
                             lambda update: self.match_eatsnake(update)),
        ]

    class BotCallback:
        """
        This object describes a conditional callback.

        Execute handler when given keyword is found in given update.

        Attributes:
            name (str):
                Name of this callback
            bot (Telegram.bot):
                Bot to handle requests
            need_adm (bool):
                Indicates that the handler needs administrator privilege to run.
            strs (dict):
                Dict to record strings.
                'q_kw': Keyword to match in message text.
                'r_ok': Response message when the handler ran successfully.
                'r_ng': Response message when the handler encountered permssion denied.
            handler_callback (func(update)):
                The Handler that will be called.
            cond_callback (Optional[func(update)]):
                The callback function will be called for checking whether to run or not.
        """

        def __init__(self,
                     name,
                     bot,
                     strs,
                     need_adm,
                     handler_callback,
                     cond_callback = None,):
            self.name = name
            self.bot = bot
            self.strs = strs
            self.need_adm = need_adm
            self.handler_callback = handler_callback
            self.cond_callback = cond_callback


        def execute(self, update):
            """Execute defined callback function."""
            mesg = update.message.text
            chat_id = update.message.chat_id
            mesg_id = update.message.message_id
            user_id = update.message.from_user.id
            cond = None

            if 'q_kw' in self.strs.keys():
                cond = mesg.startswith(self.strs['q_kw'])
            else:
                cond = self.cond_callback(update)

            if cond:
                if (self.bot.do_adm_auth(user_id) and self.need_adm) or not self.need_adm:
                    if self.handler_callback:
                        self.handler_callback(update)

                    if 'r_ok' in self.strs.keys():
                        self.bot.send_generic_mesg(chat_id, self.strs['r_ok'], mesg_id)

                    return True
                else:
                    if 'r_ng' in self.strs.keys():
                        self.bot.send_generic_mesg(chat_id, self.strs['r_ng'], mesg_id)

                    return True
            else:
                return False

def main():
    bot = Eatsnakebot("config.json")
    bot.run()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        quit()
