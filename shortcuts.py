import datetime


class CST(datetime.tzinfo):

    def utcoffset(self, dt):
        return datetime.timedelta(hours=8)

    def tzname(self, dt):
        return 'Beijing Time'

    def dst(self, dt):
        return datetime.timedelta(hours=8)


BEIJING_TIME = CST()
BEGINNING_OF_2015 = datetime.datetime(2015, 1, 1, 0, 0, 0, 0, BEIJING_TIME)
BEGINNING_OF_2016 = datetime.datetime(2016, 1, 1, 0, 0, 0, 0, BEIJING_TIME)
BEGINNING_OF_2017 = datetime.datetime(2017, 1, 1, 0, 0, 0, 0, BEIJING_TIME)


def MESSAGES_IN_2015(thread):
    return filter(lambda message: message.timestamp >= BEGINNING_OF_2015 and message.timestamp < BEGINNING_OF_2016, thread.messages)


def SENT_MESSAGES_IN_2015(thread):
    return filter(lambda message: message.sent, MESSAGES_IN_2015(thread))


def MESSAGES_IN_2016(thread):
    return filter(lambda message: message.timestamp >= BEGINNING_OF_2016 and message.timestamp < BEGINNING_OF_2017, thread.messages)


def SENT_MESSAGES_IN_2016(thread):
    return filter(lambda message: message.sent, MESSAGES_IN_2016(thread))
