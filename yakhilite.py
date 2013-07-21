import xchat
from datetime import datetime
from contextlib import contextmanager
from collections import defaultdict, deque

__module_name__ = "Yak's Highlight Collector"
__module_version__ = '1.0'
__module_description__ = 'Logs highlights in a separate tab, and also in a useful manner!'
__module_author__ = 'theY4Kman'


EVENT_CHANNEL_MESSAGE = 'Channel Message'
EVENT_CHANNEL_MESSAGE_HIGHLIGHT = 'Channel Msg Hilight'
EVENT_CHANNEL_ACTION = 'Channel Action'
EVENT_CHANNEL_ACTION_HIGHLIGHT = 'Channel Action Hilight'
EVENT_YOUR_MESSAGE = 'Your Message'
EVENT_YOUR_ACTION = 'Your Action'

RED_TAB_COLOR = 3

MY_NICK_COLOR = 15
MY_ACTION_COLOR = 02

CHANNEL_HIGHLIGHT_COLOR = 04
CHANNEL_ACTION_COLOR = 02
CHANNEL_ACTION_HIGHLIGHT_COLOR = 04

LOG_TAG = '\x02\x0306<\x0307<\x0308<\x0304HIGHLIGHT\x0308>\x0307>\x0306>\x0301\t'
# We need this to be unique, so we don't get into a loop of highlight events
# (because we emit them ourselves)
HIGHLIGHT_CHANNEL_PREFIX = '!@'


# NOTE: I don't remember when I wrote these comments (in relation to the code
# as it's written), nor can I vouch for their accuracy.
#
# Event hook arguments:
#
#   EVENT_CHANNEL_MESSAGE
#     word: [nick_with_colors, message[, user_mode_char]]
#           ['\x0322yakbot', 'yo, homie', '@']
#           ['\x0322yakbot', 'yo, homie', '+']
#           ['\x0322yakbot', 'yo, homie']
#
#   EVENT_CHANNEL_MESSAGE_HIGHLIGHT
#     word: [nick_without_colors, message, user_mode_char]
#           ['yakbot', 'yo they4kman', '@']
#
#
# TODO:
#   - Save nick colors of usernames in a dict


@contextmanager
def xchat_ctx(old_ctx, ctx):
    ctx.set()
    yield
    old_ctx.set()
    old_ctx.command('GUI FOCUS')


class DefaultDict(defaultdict):
    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        else:
            ret = self[key] = self.default_factory(key)
            return ret


class ChannelCollector(object):
    """ Manages the highlights, history, and nick colours for a single channel """

    DEFAULT_HISTORY_LENGTH = 4

    def __init__(self, channel, history_length=None):
        self.channel = channel

        self.history_length = history_length if history_length is not None else self.DEFAULT_HISTORY_LENGTH
        self.history = deque(maxlen=self.history_length)
        self.nick_colors = {}
        self.show_more = 0

    def _create_highlight_out(self, channel):
        highlight_channel = HIGHLIGHT_CHANNEL_PREFIX + channel
        xchat.get_context().command('QUERY %s' % highlight_channel)
        return highlight_channel

    def get_highlight_out(self):
        server = xchat.get_info('server')
        channel = xchat.get_context().get_info('channel')
        query = xchat.find_context(server, HIGHLIGHT_CHANNEL_PREFIX + channel)
        if not query:
            query = xchat.find_context(server, self._create_highlight_out(channel))
        return query

    def record_message(self, nick, message, highlight=False, action=False, me=False):
        """ Records a message passed by XChat to history. """
        if nick.startswith('\x03'):
            nick_color = int(nick[1:3])
            nick = nick[3:]
            self.nick_colors[nick] = nick_color

        self.history.appendleft((nick, message, highlight, action, me))

        if highlight:
            self.print_history()
            self.show_more = self.history_length
        elif self.show_more:
            old_ctx = xchat.find_context()
            ctx = self.get_highlight_out()
            with xchat_ctx(old_ctx, ctx):
                self.print_history_line(ctx, *self.history.pop())
            self.show_more -= 1


    def print_history_line(self, ctx, nick, message, highlight, action, me):
        if not highlight and not me and nick in self.nick_colors:
            nick_print = '\x03%02d%s' % (self.nick_colors[nick], nick)
        elif me:
            nick_print = '\x03%02d%s' % (MY_ACTION_COLOR if action else MY_NICK_COLOR, nick)
        else:
            nick_print = nick

        if action:
            if highlight:
                asterisk_color = '\x03%02d' % CHANNEL_ACTION_HIGHLIGHT_COLOR
            else:
                asterisk_color = '\x03%02d' % CHANNEL_ACTION_COLOR
            reset_color = '' if highlight else '\x03'
            message = '%s*\x03\t%s %s%s' % (asterisk_color, nick_print, reset_color, message)
        else:
            if highlight:
                nick_quoted = '\x03%02d<\x02%s\x02>' % (CHANNEL_HIGHLIGHT_COLOR, nick_print)
            else:
                nick_quoted = '\x03<%s\x03>' % nick_print
            message = '%s\t%s\x03' % (nick_quoted, message)

        ctx.prnt(message)

    def print_history(self):
        old_ctx = xchat.find_context()
        ctx = self.get_highlight_out()
        with xchat_ctx(old_ctx, ctx):
            ctx.prnt('\x02### At %s' % (datetime.now().strftime('%Y/%m/%d %H:%M:%S')))

            for line in reversed(self.history):
                self.print_history_line(ctx, *line)
            self.history.clear()

        ctx.command('GUI COLOR %d' % RED_TAB_COLOR)


class HighlightCollector(object):
    def __init__(self, reg_hooks=True):
        # Maps networks to a dict of their active channels against their
        # ChannelCollector objects
        #: @type: dict from str to (dict from str to ChannelCollector)
        self.networks = defaultdict(
            lambda: DefaultDict(lambda channel: ChannelCollector(channel)))

        xchat.prnt('%sYak\'s Highlight Collector loaded! :D' % LOG_TAG)
        if reg_hooks:
            def hook(evt, highlight=False, action=False, me=False):
                xchat.hook_print(evt, self.hook, (highlight, action, me))
            hook(EVENT_CHANNEL_MESSAGE)
            hook(EVENT_CHANNEL_MESSAGE_HIGHLIGHT, True)
            hook(EVENT_CHANNEL_ACTION, action=True)
            hook(EVENT_CHANNEL_ACTION_HIGHLIGHT, True, True)
            hook(EVENT_YOUR_MESSAGE, me=True)
            hook(EVENT_YOUR_ACTION, action=True, me=True)

            xchat.hook_unload(self.on_unload)

    def hook(self, word, word_eol, userdata):
        network = xchat.get_info('server')
        channel = xchat.get_context().get_info('channel')

        if channel.startswith(HIGHLIGHT_CHANNEL_PREFIX):
            return

        nick = word[0]
        message = word[1]
        self.networks[network][channel].record_message(nick, message, *userdata)

    def on_unload(self, userdata):
        xchat.prnt('%sYak\'s Highlight Collector unloaded :(' % LOG_TAG)


if __name__ == '__main__':
    collector = HighlightCollector()
