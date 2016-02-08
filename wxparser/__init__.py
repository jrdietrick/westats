import datetime
import json
import re
import sqlite3
import unicodedata


class UTC(datetime.tzinfo):

    def utcoffset(self, dt):
        return datetime.timedelta(0)

    def tzname(self, dt):
        return 'UTC'

    def dst(self, dt):
        return datetime.timedelta(0)


utc = UTC()


def _aware_time_to_unix_timestamp(aware_time):
    return (aware_time - datetime.datetime(1970, 1, 1, 0, 0, 0, 0, utc)).total_seconds()


def _find_exactly_one(iterable, filter_callable):
    candidates = filter(filter_callable, iterable)
    if len(candidates) == 0:
        raise Exception('Not found!')
    if len(candidates) > 1:
        raise Exception('Ambiguous!')
    return candidates[0]


def _slugify(value):
    value = unicodedata.normalize('NFKD', unicode(value)).encode('ascii', 'ignore').decode('ascii')
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    return re.sub('[-\s]+', '-', value)


class UserData(object):

    def __init__(self, categories):
        self.categories = categories

    @classmethod
    def initialize(cls, parser_instance):
        try:
            userdata_file = open('userdata.json', 'r')
        except IOError:
            return cls._blank_configuration()

        userdata_raw = json.loads(userdata_file.read())
        userdata_file.close()
        assert 'categories' in userdata_raw
        userdata_object = cls._blank_configuration()
        for category in userdata_raw['categories']:
            userdata_object.add_category(Category.deserialize(category, parser_instance))
        return userdata_object

    @classmethod
    def _blank_configuration(cls):
        return cls({})

    def add_category(self, category):
        self.categories[category.slug] = category

    def serialize(self):
        return json.dumps({
            'categories': [category.serialize() for category in self.categories.values()],
        })

    def save(self):
        output_file = open('userdata.json', 'w')
        output_file.write(self.serialize())
        output_file.close()

    def categories_as_list(self):
        return sorted(self.categories.values(), key=lambda category: category.display_name)


class Category(object):

    def __init__(self, display_name):
        self.display_name = display_name
        self.slug = _slugify(self.display_name)
        self.threads = []

    def serialize(self):
        return {
            'display_name': self.display_name,
            'slug': self.slug,
            'threads': [thread.contact.raw_username for thread in self.threads],
        }

    def add_thread(self, thread):
        self.threads.append(thread)
        thread.category = self

    @classmethod
    def deserialize(cls, object_from_json, parser_instance):
        deserialized_object = cls(object_from_json['display_name'])
        assert deserialized_object.slug == object_from_json['slug']
        for raw_username in object_from_json['threads']:
            deserialized_object.add_thread(parser_instance.get_thread_with_raw_username(raw_username))
        return deserialized_object


class UnknownMessageTypeException(Exception):
    pass


class Message(object):

    TYPE_NORMAL              = 1
    TYPE_IMAGE               = 2
    TYPE_ASYNC_VOICE         = 3
    TYPE_CONTACT_CARD        = 4
    TYPE_VIDEO               = 5
    TYPE_STICKER             = 6
    TYPE_LOCATION_PIN        = 7
    TYPE_MUSIC_LINK          = 8
    TYPE_REALTIME_VOICE_CHAT = 9
    TYPE_SIGHT               = 10
    TYPE_SYSTEM_MESSAGE      = 11
    TYPE_EXTERNAL_APP_SHARE  = 12
    TYPE_TRANSFER            = 13
    TYPE_HONGBAO             = 14
    TYPE_UNKNOWN             = 15

    def __init__(self, columns):
        self.timestamp = datetime.datetime.fromtimestamp(float(columns[0]) / 1000, utc)
        self.sent = True if columns[1] else False
        self._process_type(columns[2])

    def _process_type(self, message_type):
        if message_type == 1:
            self.type = Message.TYPE_NORMAL
        elif message_type == 3:
            self.type = Message.TYPE_IMAGE
        elif message_type == 34:
            self.type = Message.TYPE_ASYNC_VOICE
        elif message_type == 42:
            self.type = Message.TYPE_CONTACT_CARD
        elif message_type == 43:
            self.type = Message.TYPE_VIDEO
        elif message_type == 47 or message_type == 1048625:
            self.type = Message.TYPE_STICKER
        elif message_type == 48:
            self.type = Message.TYPE_LOCATION_PIN
        elif message_type == 49:
            self.type = Message.TYPE_MUSIC_LINK
        elif message_type == 50:
            self.type = Message.TYPE_REALTIME_VOICE_CHAT
        elif message_type == 62:
            self.type = Message.TYPE_SIGHT
        elif message_type == 10000 or message_type == 10002:
            self.type = Message.TYPE_SYSTEM_MESSAGE
        elif message_type == 16777265:
            self.type = Message.TYPE_EXTERNAL_APP_SHARE
        elif message_type == 419430449:
            self.type = Message.TYPE_TRANSFER
        elif message_type == 436207665:
            self.type = Message.TYPE_HONGBAO
        else:
            raise UnknownMessageTypeException('Uncategorized message type %d!' % message_type)


class Thread(object):

    groupchat_regex = re.compile('\d+@chatroom')

    def __init__(self, cursor, contact):
        self.contact = contact
        self.cursor = cursor

    @property
    def is_group_chat(self):
        return True if self.groupchat_regex.match(self.contact.raw_username) else False

    @property
    def message_count(self):
        if not getattr(self, '_message_count', None):
            self._message_count = int(next(self.cursor.execute('SELECT COUNT(*) FROM message WHERE talker=?', [self.contact.raw_username]))[0])
        return self._message_count

    def message_count_between(self, from_timestamp, to_timestamp):
        rows = self.cursor.execute('SELECT COUNT(*) FROM message WHERE talker=? AND createTime >= ? AND createTime < ?',
                                   [
                                       self.contact.raw_username,
                                       int(_aware_time_to_unix_timestamp(from_timestamp)) * 1000,
                                       int(_aware_time_to_unix_timestamp(to_timestamp)) * 1000,
                                   ])
        return int(next(rows)[0])

    def message_sent_count_between(self, from_timestamp, to_timestamp):
        rows = self.cursor.execute('SELECT COUNT(*) FROM message WHERE talker=? AND createTime >= ? AND createTime < ? AND isSend=1',
                                   [
                                       self.contact.raw_username,
                                       int(_aware_time_to_unix_timestamp(from_timestamp)) * 1000,
                                       int(_aware_time_to_unix_timestamp(to_timestamp)) * 1000,
                                   ])
        return int(next(rows)[0])

    @property
    def messages(self):
        if not getattr(self, '_messages', None):
            self._parse_messages()
        return self._messages

    def _parse_messages(self):
        self._messages = []
        for row in self.cursor.execute('SELECT createTime, isSend, type, content FROM message WHERE talker=? ORDER BY createTime', [self.contact.raw_username]):
            try:
                self._messages.append(Message(row))
            except UnknownMessageTypeException:
                pass


class Contact(object):

    def __init__(self, columns):
        self.raw_username = columns[0]
        if columns[1]:
            self.username = columns[1]
        else:
            self.username = self.raw_username
        self.display_name = columns[2]
        self.display_name_safe = json.dumps(self.display_name)

    def __repr__(self):
        return '<%s %s>' % (self.username, self.display_name_safe)


class Parser(object):

    def __init__(self, filename):
        self.filename = filename
        self.database_handle = sqlite3.connect(self.filename)
        self.cursor = self.database_handle.cursor()
        self.threads = [Thread(self.cursor, contact) for contact in self._parse_contacts()]

    def _parse_contacts(self):
        return [Contact(row) for row in self.cursor.execute('SELECT username, alias, nickname FROM rcontact')]

    def get_thread_with_raw_username(self, raw_username):
        return _find_exactly_one(self.threads, lambda thread: raw_username == thread.contact.raw_username)

    def get_group_chat_with_name(self, name, exact=False):
        if exact:
            return _find_exactly_one(self.group_threads, lambda thread: name.lower() == thread.contact.display_name.lower())
        return _find_exactly_one(self.group_threads, lambda thread: name.lower() in thread.contact.display_name.lower())

    def get_thread_with_username(self, username):
        return _find_exactly_one(self.threads, lambda thread: username.lower() in thread.contact.username.lower())

    @property
    def individual_threads(self):
        return [thread for thread in self.threads if not thread.is_group_chat]

    @property
    def group_threads(self):
        return [thread for thread in self.threads if thread.is_group_chat]
