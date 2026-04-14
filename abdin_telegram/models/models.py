# -*- coding: utf-8 -*-
import base64
import telebot
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class Telegram(models.AbstractModel):
    _name = 'abdin_telegram'
    _description = 'Telegram Bot'

    def send_by_bot(self,
                    chat_id,
                    msg="Hello",
                    before="",
                    after="\n\n <i>Posted by Odoo.</i>",
                    name_ext='attachment.pdf',
                    attachment=None,
                    **kwargs):

        api_key = self.env['ir.config_parameter'].sudo().get_param('telebot_api_key', '')
        bot = telebot.TeleBot(api_key)

        try:
            from bs4 import BeautifulSoup
            from bs4 import NavigableString, Tag
            import re
            # always remove strating and tailing <p> & <span> tags and multi spaces from message.body
            msg = re.sub('^</?span>|</?span>$|^</?p>|</?p>$', '', msg)
            msg = re.sub(' +', ' ', msg)

            # replace ["div", "h6", "br"] with new lines
            soup = BeautifulSoup(msg, "html.parser")

            # IF HTML THEN REMOVE ALL NEW LINES
            for child in soup.children:
                if isinstance(child, NavigableString):
                    child.replace_with(child.replace('\n', '').replace('\r', ''))

            # REPLACE ALL [DIV H6 BR] WITH NEW LINE
            for el in soup.find_all(["div", "h6", "br"]):
                el.replace_with(el.text + "\n")

            # REPLACE ALL [SPAN B STRONG] WITH @@@ ... ###
            for el in soup.find_all(["span", "b", "strong"]):
                el.replace_with("~~~b" + el.text + "b~~~")

            # REPLACE ALL [I] WITH ~~~i ... i~~~
            for el in soup.find_all(["i"]):
                el.replace_with("~~~i" + el.text + "i~~~")

            msg = soup.get_text()

            # IF ANY TAGS REMAINS TURN IT TO STRINGS
            msg = msg.replace('<', '&lt;').replace('>', '&gt;')

            # RETURN ~~~b ... b~~~ BACK TO <B> ... </B>
            msg = re.sub('~~~b(.*?)b~~~', r' <b>\g<1></b> ', msg)

            # RETURN ~~~i ... i~~~ BACK TO <I> ... </I>
            msg = re.sub('~~~i(.*?)i~~~', r' <i>\g<1></i> ', msg)

            new_msg = "%s %s %s" % (before, msg, after)
            bot.send_message(chat_id, new_msg, parse_mode='HTML')
            if attachment:
                # Decode the data
                file_data = base64.b64decode(attachment)

                # Send the file via bot
                bot.send_document(chat_id, (name_ext, file_data))
            # _logger.info(new_msg)

        except Exception as ex:
            template = "An exception of type {0} occurred. Arguments:\n{1!r}"
            message = template.format(type(ex).__name__, ex.args)
            _logger.warning(message)
            return message

    @api.model
    def get_chat_id(self, chat_id):
        return int(self.env["ir.config_parameter"].sudo().get_param(chat_id, -1002128909908, ))
