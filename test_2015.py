import datetime
import re
from collections import defaultdict
from dateutil.relativedelta import relativedelta

from wxparser import Parser, UserData, Category, _slugify


class CST(datetime.tzinfo):

    def utcoffset(self, dt):
        return datetime.timedelta(hours=8)

    def tzname(self, dt):
        return 'Beijing Time'

    def dst(self, dt):
        return datetime.timedelta(hours=8)


beijing_time = CST()
beginning_of_2015 = datetime.datetime(2015, 1, 1, 0, 0, 0, 0, beijing_time)
beginning_of_2016 = datetime.datetime(2016, 1, 1, 0, 0, 0, 0, beijing_time)
beginning_of_2017 = datetime.datetime(2017, 1, 1, 0, 0, 0, 0, beijing_time)


def build_sent_by_category_by_month_graph(wxp):
    # Build the timespans
    timespans = []
    rolling_date = datetime.datetime(2015, 1, 1, 0, 0, 0, 0, beijing_time)
    while rolling_date < beginning_of_2016:
        next_start = rolling_date + relativedelta(months=1)
        timespans.append((rolling_date, next_start))
        rolling_date = next_start

    raw_data = defaultdict(lambda: [0] * len(timespans))
    for thread in wxp.individual_threads:
        category_slug = thread.category.slug if getattr(thread, 'category', None) else 'other'
        for i in xrange(0, len(timespans)):
            from_timestamp, to_timestamp = timespans[i]
            raw_data[category_slug][i] += len(filter(lambda message: message.sent and message.timestamp >= from_timestamp and message.timestamp < to_timestamp, thread.messages))

    for thread in wxp.group_threads:
        for i in xrange(0, len(timespans)):
            from_timestamp, to_timestamp = timespans[i]
            raw_data['group-chats'][i] += len(filter(lambda message: message.sent and message.timestamp >= from_timestamp and message.timestamp < to_timestamp, thread.messages))

    sorted_keys = list(reversed(sorted(raw_data.keys(), key=lambda slug: sum(raw_data[slug]))))

    series_data = []
    for series in sorted_keys:
        series_data.append({
            'name': series,
            'data': raw_data[series],
        })

    return {
        'chart': {
            'type': 'area'
        },
        'title': {
            'text': 'Messages sent'
        },
        'subtitle': {
            'text': 'per month, by category'
        },
        'colors': ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#ffff33', '#a65628', '#f781bf', '#999999'],
        'xAxis': {
            'categories': [timespan[0].strftime('%Y-%m') for timespan in timespans],
            'tickmarkPlacement': 'on',
            'title': {
                'enabled': False,
            },
        },
        'yAxis': {
            'title': {
                'text': 'Messages sent'
            },
        },
        'tooltip': {
            'shared': True,
            'valueSuffix': ' messages'
        },
        'plotOptions': {
            'area': {
                'stacking': 'normal',
                'lineWidth': 1,
            }
        },
        'series': series_data,
    }


class ScatterPlotSeries(object):

    def __init__(self, name, thread_filter, message_filter, color):
        self.name = name
        self.thread_filter = thread_filter
        self.message_filter = message_filter
        self.color = color


def build_message_scatterplot(wxp, series_list):

    def _day_of_year(timestamp):
        return int((timestamp - beginning_of_2015).total_seconds() / (60 * 60 * 24))

    def _hour_of_day(timestamp):
        return round(timestamp.hour + (timestamp.minute / 60.0), 2)

    series_output = []
    for series in series_list:
        # Start with the blank structure
        series_output.append({
            'name': series.name,
            'color': series.color,
            'data': [],
        })
        for thread in filter(series.thread_filter, wxp.threads):
            for message in filter(series.message_filter, filter(lambda message: message.timestamp >= beginning_of_2015 and message.timestamp < beginning_of_2016, thread.messages)):
                series_output[-1]['data'].append([_day_of_year(message.timestamp.astimezone(beijing_time)), _hour_of_day(message.timestamp.astimezone(beijing_time))])

    return {
        'chart': {
            'type': 'scatter',
            'zoomType': 'xy',
        },
        'colors': ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#ffff33', '#a65628', '#f781bf', '#999999'],
        'title': {
            'text': '2015 - All Messages',
        },
        'xAxis': {
            'title': {
                'enabled': True,
                'text': 'Day of Year',
            },
            'tickPositions': [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365],
            # 'startOnTick': True,
            # 'endOnTick': True,
            # 'showLastLabel': True,
        },
        'yAxis': {
            'title': {
                'text': 'Hour of Day (China Standard Time)',
            },
            'min': 0,
            'max': 24,
            'tickPositions': [0, 4, 8, 12, 16, 20, 24],
        },
        'plotOptions': {
            'scatter': {
                'marker': {
                    'radius': 3,
                },
            },
        },
        'series': series_output,
    }


if __name__ == '__main__':
    wxp = Parser('decrypted.db')
    userdata = UserData.initialize(wxp)

    def _chats_in_2015(thread):
        return filter(lambda message: message.timestamp >= beginning_of_2015 and message.timestamp < beginning_of_2016, thread.messages)

    def _sent_chats_in_2015(thread):
        return filter(lambda message: message.sent, _chats_in_2015(thread))

    def _chats_in_2016(thread):
        return filter(lambda message: message.timestamp >= beginning_of_2016 and message.timestamp < beginning_of_2017, thread.messages)

    def _sent_chats_in_2016(thread):
        return filter(lambda message: message.sent, _chats_in_2016(thread))

    total_individual_chats = sum([len(_chats_in_2015(thread)) for thread in wxp.individual_threads])
    individual_sent_messages = sum([len(_sent_chats_in_2015(thread)) for thread in wxp.individual_threads])
    group_sent_messages = sum([len(_sent_chats_in_2015(thread)) for thread in wxp.group_threads])
    total_sent_messages = individual_sent_messages + group_sent_messages

    # Figure out how many people we need
    # to categorize to get to 90% of chats
    cumulative = 0
    to_categorize = []
    for thread in list(reversed(sorted(wxp.individual_threads, key=lambda thread: len(_chats_in_2015(thread))))):
        cumulative += len(_chats_in_2015(thread))
        to_categorize.append(thread)
        if float(cumulative) / total_individual_chats > 0.90:
            break

    for thread in to_categorize:
        if getattr(thread, 'category', None):
            continue
        print thread.contact.display_name
        print
        categories_list = userdata.categories_as_list()
        for i in xrange(0, len(categories_list)):
            print '%4d - %s' % (i, categories_list[i].display_name)
        print

        user_entry = raw_input('Enter a number or name a new category: ').strip()
        if re.compile('\d+').match(user_entry):
            try:
                selected_category_index = int(user_entry)
                if selected_category_index >= 0 and selected_category_index < len(categories_list):
                    selected_category = categories_list[selected_category_index]
                    selected_category.add_thread(thread)
                    userdata.save()
                    continue
            except ValueError:
                pass

        if _slugify(user_entry) in userdata.categories.keys():
            # Matches an existing category by slug
            userdata.categories[_slugify(user_entry)].add_thread(thread)
            userdata.save()
            continue

        # Whole new category
        new_category = Category(user_entry)
        userdata.add_category(new_category)
        new_category.add_thread(thread)
        userdata.save()

    from renderers.highchart import HighchartRenderer
    # print HighchartRenderer(build_sent_by_category_by_month_graph(wxp)).render()
    print HighchartRenderer(build_message_scatterplot(wxp,
                                                      [ScatterPlotSeries('Messages Sent',
                                                                         lambda thread: True,
                                                                         lambda message: message.sent,
                                                                         'rgba(55, 126, 184, .6)'),
                                                       ScatterPlotSeries('Messages Received',
                                                                         lambda thread: not thread.is_group_chat,
                                                                         lambda message: not message.sent,
                                                                         'rgba(77, 175, 74, .6)')])).render()

    # print
    # threads_by_sent = list(reversed(sorted(wxp.individual_threads, key=lambda thread: len(_sent_chats_in_2015(thread)))))
    # for i in xrange(0, 10):
    #     print threads_by_sent[i].contact.display_name, len(_sent_chats_in_2015(threads_by_sent[i])), len(_chats_in_2015(threads_by_sent[i])) - len(_sent_chats_in_2015(threads_by_sent[i]))

    # print
    # threads_by_sent = list(reversed(sorted(wxp.individual_threads, key=lambda thread: len(_sent_chats_in_2016(thread)))))
    # for i in xrange(0, 10):
    #     print threads_by_sent[i].contact.display_name, len(_sent_chats_in_2016(threads_by_sent[i])), len(_chats_in_2016(threads_by_sent[i])) - len(_sent_chats_in_2016(threads_by_sent[i]))

    # by_category = defaultdict(lambda: 0)
    # for thread in wxp.individual_threads:
    #     category_slug = thread.category.slug if getattr(thread, 'category', None) else 'other'
    #     by_category[category_slug] += len(_chats_in_2015(thread))

    # print
    # print 'TOTAL'
    # for category in list(reversed(sorted(by_category, key=lambda x: by_category[x]))):
    #     display_name = 'Other' if category == 'other' else userdata.categories[category].display_name
    #     print display_name, '%.1f%%' % (float(by_category[category]) / float(total_individual_chats) * 100.0)

    # sent_by_category = defaultdict(lambda: 0)
    # for thread in wxp.individual_threads:
    #     category_slug = thread.category.slug if getattr(thread, 'category', None) else 'other'
    #     sent_by_category[category_slug] += len(_sent_chats_in_2015(thread))

    # print
    # print 'SENT'
    # for category in list(reversed(sorted(sent_by_category, key=lambda x: sent_by_category[x]))):
    #     display_name = 'Other' if category == 'other' else userdata.categories[category].display_name
    #     print display_name, '%.1f%%' % (float(sent_by_category[category]) / float(individual_sent_messages) * 100.0)

    # print
    # cumulative = 0
    # people = 0
    # for thread in list(reversed(sorted(wxp.individual_threads, key=lambda thread: len(_chats_in_2015(thread))))):
    #     cumulative += len(_chats_in_2015(thread))
    #     people += 1
    #     if people in [1, 3, 5, 10, 20]:
    #         print '%.1f%% of chatting is with only %d people' % (float(cumulative) / float(total_individual_chats) * 100.0, people)

    # print
    # print '%.1f%% of your sent messages go to groups' % (float(group_sent_messages) / float(total_sent_messages) * 100)
    # print '%.1f%% of your sent messages go to individuals' % (float(individual_sent_messages) / float(total_sent_messages) * 100)
